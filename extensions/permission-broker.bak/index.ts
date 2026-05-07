import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import {
  readFileSync,
  writeFileSync,
  watchFile,
  existsSync,
  mkdirSync,
  appendFileSync,
} from "node:fs";
import { join, dirname } from "node:path";

// =============================================================================
// Types
// =============================================================================

interface RoleDefinition {
  description: string;
  toolPolicy: "allow-all" | "deny-list";
  canGrant: string[];
  canApprove: boolean;
  canEscalateTo: string | null;
}

interface AgentDefinition {
  role: string;
  manager?: string;
  pool?: string[];
  specialty?: string;
}

interface FilesystemPolicy {
  mode: "workspace-only" | "unrestricted";
  additionalAllowedPaths?: string[];
}

interface MessagingPolicy {
  canInitiate: boolean;
  canReplyTo: string;
  canBroadcast: boolean;
}

interface PermissionsConfig {
  roles: Record<string, RoleDefinition>;
  agents: Record<string, AgentDefinition>;
  toolDenyLists: Record<string, string[]>;
  capabilityDescriptions: Record<string, string>;
  agentPorts: Record<string, number>;
  filesystemPolicy: Record<string, FilesystemPolicy>;
  sessionPolicy: Record<string, string>;
  messagingPolicy: Record<string, MessagingPolicy>;
}

interface Grant {
  id: string;
  agentName: string;
  capability: string;
  grantedBy: string;
  grantedAt: number;
  expiresAt: number;
  reason: string;
}

interface GrantsState {
  grants: Grant[];
}

interface ElevationRequest {
  id: string;
  agentName: string;
  capability: string;
  reason: string;
  durationMinutes: number;
  requestedAt: number;
  status: "pending" | "approved" | "denied";
  decidedBy?: string;
  decidedAt?: number;
  denyReason?: string;
}

interface RequestsState {
  requests: ElevationRequest[];
}

// =============================================================================
// State
// =============================================================================

let permissions: PermissionsConfig;
let grants: GrantsState = { grants: [] };
let requests: RequestsState = { requests: [] };
let pluginDir: string;
let stateDir: string;
let currentAgentName: string;
let currentAgentRole: string;
let auditEnabled = true;
let maxGrantDuration = 480;

// =============================================================================
// Helpers
// =============================================================================

function getAgentName(): string {
  const label = process.env.OPENCLAW_SERVICE_LABEL || "";
  const name = label.replace("ai-final.", "");
  // If no label set (King AI runs without one), check config
  return name && name !== label ? name : "king-ai";
}

function getAgentRole(name: string): string {
  const agentDef = permissions?.agents?.[name];
  if (agentDef) return agentDef.role;
  return "king";
}

function loadPermissions(): void {
  const path = join(pluginDir, "permissions.json");
  if (existsSync(path)) {
    permissions = JSON.parse(readFileSync(path, "utf-8"));
  }
}

function loadGrants(): void {
  const path = join(stateDir, "grants.json");
  try {
    if (existsSync(path)) {
      grants = JSON.parse(readFileSync(path, "utf-8"));
      // Purge expired grants
      const now = Date.now();
      const before = grants.grants.length;
      grants.grants = grants.grants.filter((g) => g.expiresAt > now);
      if (grants.grants.length !== before) {
        saveGrants();
      }
    }
  } catch {
    grants = { grants: [] };
  }
}

function saveGrants(): void {
  const path = join(stateDir, "grants.json");
  writeFileSync(path, JSON.stringify(grants, null, 2));
}

function loadRequests(): void {
  const path = join(stateDir, "requests.json");
  try {
    if (existsSync(path)) {
      requests = JSON.parse(readFileSync(path, "utf-8"));
    }
  } catch {
    requests = { requests: [] };
  }
}

function saveRequests(): void {
  const path = join(stateDir, "requests.json");
  writeFileSync(path, JSON.stringify(requests, null, 2));
}

function auditLog(
  action: string,
  details: Record<string, unknown>,
  logger?: { info?: (...args: unknown[]) => void },
): void {
  if (!auditEnabled) return;
  const entry = {
    timestamp: new Date().toISOString(),
    agent: currentAgentName,
    role: currentAgentRole,
    action,
    ...details,
  };
  try {
    const path = join(stateDir, "audit.jsonl");
    appendFileSync(path, JSON.stringify(entry) + "\n");
  } catch {
    // Audit logging is best-effort
  }
}

function hasActiveGrant(agentName: string, capability: string): boolean {
  const now = Date.now();
  return grants.grants.some(
    (g) =>
      g.agentName === agentName &&
      g.capability === capability &&
      g.expiresAt > now,
  );
}

function getManagerForAgent(agentName: string): string | null {
  const agentDef = permissions?.agents?.[agentName];
  return agentDef?.manager || null;
}

function isManagerOf(managerName: string, workerName: string): boolean {
  const agentDef = permissions?.agents?.[workerName];
  return agentDef?.manager === managerName;
}

function canAgentGrant(granterName: string, targetName: string): boolean {
  const granterRole = getAgentRole(granterName);
  const targetRole = getAgentRole(targetName);
  const roleDef = permissions?.roles?.[granterRole];

  if (!roleDef?.canGrant?.length) return false;
  if (!roleDef.canGrant.includes(targetRole)) return false;

  // Managers can only grant to their own workers
  if (granterRole === "manager") {
    return isManagerOf(granterName, targetName);
  }

  // King can grant to anyone
  return granterRole === "king";
}

function canAgentApprove(agentName: string): boolean {
  const role = getAgentRole(agentName);
  return permissions?.roles?.[role]?.canApprove === true;
}

// Map tool names to the capability they require
function toolToCapability(toolName: string): string | null {
  const normalized = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");

  // Shell execution tools
  if (
    ["exec", "bash", "shell", "terminal", "run_command"].includes(normalized)
  ) {
    return "exec";
  }

  // Cross-agent messaging tools
  if (
    ["sessions_send", "message_send", "messagesend"].includes(normalized)
  ) {
    return "sessions_send";
  }

  // Broadcast
  if (["broadcast"].includes(normalized)) {
    return "broadcast";
  }

  // Elevated operations
  if (["elevated_exec", "sudo", "elevatedexec"].includes(normalized)) {
    return "elevated";
  }

  return null;
}

function isToolDenied(
  agentName: string,
  role: string,
  toolName: string,
): { denied: boolean; reason?: string } {
  const roleDef = permissions?.roles?.[role];
  if (!roleDef) return { denied: false };
  if (roleDef.toolPolicy === "allow-all") return { denied: false };

  const denyList = permissions?.toolDenyLists?.[role] || [];
  if (denyList.length === 0) return { denied: false };

  const normalized = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");

  // Check if tool name directly matches deny list
  const directMatch = denyList.some(
    (denied) => normalized === denied || normalized.includes(denied),
  );

  if (!directMatch) return { denied: false };

  // Check if there's an active grant for the required capability
  const capability = toolToCapability(toolName);
  if (capability && hasActiveGrant(agentName, capability)) {
    return { denied: false };
  }

  // Also check by direct tool name
  if (hasActiveGrant(agentName, normalized)) {
    return { denied: false };
  }

  return {
    denied: true,
    reason: `Permission denied: '${role}' role cannot use '${toolName}'. Use the request_elevation tool to request temporary access from your manager.`,
  };
}

function isPathAllowed(agentName: string, role: string, targetPath: string): boolean {
  const policy = permissions?.filesystemPolicy?.[role];
  if (!policy || policy.mode === "unrestricted") return true;

  // workspace-only: allow agent dir + /tmp + additional paths
  const agentDir = process.env.OPENCLAW_STATE_DIR || "";
  const allowed = [agentDir, ...(policy.additionalAllowedPaths || [])];

  // Check if path falls within any allowed prefix
  for (const prefix of allowed) {
    if (prefix && targetPath.startsWith(prefix)) return true;
  }

  // Check for active fs_unrestricted grant
  if (hasActiveGrant(agentName, "fs_unrestricted")) return true;

  return false;
}

// =============================================================================
// Plugin Registration
// =============================================================================

export default function register(api: OpenClawPluginApi) {
  pluginDir = dirname(api.source);
  stateDir = join(pluginDir, "state");

  if (!existsSync(stateDir)) {
    mkdirSync(stateDir, { recursive: true });
  }

  // Read plugin config
  const pCfg = (api.pluginConfig ?? {}) as Record<string, unknown>;
  auditEnabled = pCfg.auditLogEnabled !== false;
  maxGrantDuration = (pCfg.maxGrantDurationMinutes as number) || 480;

  // Load state
  loadPermissions();
  loadGrants();
  loadRequests();

  currentAgentName = getAgentName();
  currentAgentRole = getAgentRole(currentAgentName);

  api.logger.info?.(
    `permission-broker: loaded for agent=${currentAgentName} role=${currentAgentRole}`,
  );

  // Watch for changes to grants file (other processes may update it)
  try {
    watchFile(join(stateDir, "grants.json"), { interval: 2000 }, () => {
      try {
        loadGrants();
      } catch { /* handled in loadGrants */ }
    });
  } catch { /* watchFile may fail in some environments */ }

  // Watch for changes to requests file
  try {
    watchFile(join(stateDir, "requests.json"), { interval: 2000 }, () => {
      try {
        loadRequests();
      } catch { /* handled in loadRequests */ }
    });
  } catch { /* watchFile may fail in some environments */ }

  // ===========================================================================
  // HOOK: before_tool_call — PRIMARY PERMISSION ENFORCEMENT
  // ===========================================================================
  api.on(
    "before_tool_call",
    async (event, ctx) => {
      const { toolName, params } = event;

      // Permission broker's own tools are always allowed
      const brokerTools = [
        "request_elevation",
        "approve_elevation",
        "deny_elevation",
        "check_permissions",
        "list_elevation_requests",
        "revoke_grant",
      ];
      if (brokerTools.includes(toolName)) return;

      // Reload grants to pick up cross-process changes
      loadGrants();

      // --- Tool deny list check ---
      const check = isToolDenied(currentAgentName, currentAgentRole, toolName);
      if (check.denied) {
        auditLog("TOOL_BLOCKED", {
          toolName,
          params,
          reason: check.reason,
        });
        api.logger.warn?.(
          `permission-broker: BLOCKED '${toolName}' for ${currentAgentName} (${currentAgentRole})`,
        );
        return { block: true, blockReason: check.reason };
      }

      // --- Filesystem sandboxing for workers ---
      if (currentAgentRole === "worker") {
        const fileTools = [
          "read",
          "write",
          "edit",
          "apply_patch",
          "cat",
          "head",
          "tail",
          "grep",
          "create",
          "mkdir",
        ];
        if (fileTools.includes(toolName)) {
          const targetPath = (params.path ||
            params.filePath ||
            params.file ||
            params.dir ||
            params.directory ||
            "") as string;
          if (targetPath && !isPathAllowed(currentAgentName, currentAgentRole, targetPath)) {
            const reason = `Permission denied: worker '${currentAgentName}' can only access files within its workspace (${process.env.OPENCLAW_STATE_DIR || "agent dir"}). Use request_elevation with capability 'fs_unrestricted' to request broader access.`;
            auditLog("FS_BLOCKED", {
              toolName,
              targetPath,
              agentDir: process.env.OPENCLAW_STATE_DIR,
            });
            return { block: true, blockReason: reason };
          }
        }
      }

      // --- Cross-agent messaging restriction for workers ---
      if (
        currentAgentRole === "worker" &&
        (toolName === "sessions_send" || toolName === "message_send")
      ) {
        const target = (params.target || params.to || "") as string;
        const manager = getManagerForAgent(currentAgentName);

        // Workers can only message their manager (unless grant active)
        if (manager && !target.includes(manager)) {
          if (!hasActiveGrant(currentAgentName, "sessions_send")) {
            auditLog("MSG_BLOCKED", {
              toolName,
              target,
              allowedManager: manager,
            });
            return {
              block: true,
              blockReason: `Permission denied: worker '${currentAgentName}' can only send messages to manager '${manager}'. Use request_elevation with capability 'sessions_send' for broader messaging access.`,
            };
          }
        }
      }

      auditLog("TOOL_ALLOWED", { toolName });
    },
    { priority: 100 },
  );

  // ===========================================================================
  // HOOK: after_tool_call — AUDIT LOGGING
  // ===========================================================================
  api.on("after_tool_call", async (event) => {
    auditLog("TOOL_COMPLETED", {
      toolName: event.toolName,
      durationMs: event.durationMs,
      error: event.error || null,
    });
  });

  // ===========================================================================
  // HOOK: message_sending — RESTRICT WORKER BROADCAST
  // ===========================================================================
  api.on("message_sending", async (event, ctx) => {
    if (currentAgentRole !== "worker") return;

    // Workers cannot broadcast
    const meta = event.metadata as Record<string, unknown> | undefined;
    if (meta?.broadcast) {
      auditLog("BROADCAST_BLOCKED", { to: event.to });
      return { cancel: true };
    }
  });

  // ===========================================================================
  // TOOL: request_elevation
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "request_elevation",
      description:
        "Request temporary elevated permissions from your manager (or from King AI if you are a manager). Specify the capability you need, why you need it, and for how long.",
      parameters: {
        type: "object" as const,
        properties: {
          capability: {
            type: "string",
            description:
              "The capability to request. Options: 'exec' (shell commands), 'sessions_send' (cross-agent messaging), 'fs_unrestricted' (filesystem beyond workspace), 'elevated' (elevated operations), 'web_search', 'web_fetch', 'broadcast'",
            enum: [
              "exec",
              "sessions_send",
              "fs_unrestricted",
              "elevated",
              "web_search",
              "web_fetch",
              "broadcast",
            ],
          },
          reason: {
            type: "string",
            description:
              "Detailed explanation of why this permission is needed for the current task",
          },
          duration_minutes: {
            type: "number",
            description: `How long the permission is needed in minutes (default: 30, max: ${maxGrantDuration})`,
          },
        },
        required: ["capability", "reason"],
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        const capability = params.capability as string;
        const reason = params.reason as string;
        const durationMinutes = Math.min(
          (params.duration_minutes as number) || 30,
          maxGrantDuration,
        );

        // King doesn't need elevation
        if (currentAgentRole === "king") {
          return {
            content: [
              {
                type: "text" as const,
                text: "King AI has full unrestricted permissions — no elevation needed.",
              },
            ],
          };
        }

        // Determine approver
        const approver =
          currentAgentRole === "worker"
            ? getManagerForAgent(currentAgentName) || "king-ai"
            : "king-ai";

        // Check if already granted
        loadGrants();
        if (hasActiveGrant(currentAgentName, capability)) {
          const grant = grants.grants.find(
            (g) =>
              g.agentName === currentAgentName && g.capability === capability,
          );
          const remaining = grant
            ? Math.round((grant.expiresAt - Date.now()) / 60000)
            : 0;
          return {
            content: [
              {
                type: "text" as const,
                text: `You already have '${capability}' permission (${remaining} minutes remaining). No request needed.`,
              },
            ],
          };
        }

        // Create the request
        loadRequests();
        const request: ElevationRequest = {
          id: `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          agentName: currentAgentName,
          capability,
          reason,
          durationMinutes,
          requestedAt: Date.now(),
          status: "pending",
        };
        requests.requests.push(request);
        saveRequests();

        auditLog("ELEVATION_REQUESTED", {
          requestId: request.id,
          capability,
          reason,
          approver,
          durationMinutes,
        });

        // Best-effort HTTP notification to the approver
        const approverPort = permissions?.agentPorts?.[approver];
        if (approverPort) {
          try {
            await fetch(`http://localhost:${approverPort}/api/v1/notify`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                type: "elevation_request",
                from: currentAgentName,
                request,
                durationMinutes,
              }),
              signal: AbortSignal.timeout(3000),
            }).catch(() => {});
          } catch {
            // Notification is best-effort; the approver also polls requests.json
          }
        }

        return {
          content: [
            {
              type: "text" as const,
              text: [
                "## Elevation Request Submitted",
                "",
                `| Field | Value |`,
                `|-------|-------|`,
                `| **Request ID** | \`${request.id}\` |`,
                `| **Capability** | ${capability} |`,
                `| **Reason** | ${reason} |`,
                `| **Approver** | ${approver} |`,
                `| **Duration** | ${durationMinutes} minutes |`,
                `| **Status** | pending |`,
                "",
                `Waiting for **${approver}** to approve. The capability will become available once approved.`,
                `Use \`check_permissions\` to check status.`,
              ].join("\n"),
            },
          ],
        };
      },
    }),
    { names: ["request_elevation"] },
  );

  // ===========================================================================
  // TOOL: approve_elevation
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "approve_elevation",
      description:
        "Approve a pending permission elevation request from a subordinate agent. Only managers and King AI can use this tool. Managers can only approve requests from their own workers, and only for capabilities they themselves possess.",
      parameters: {
        type: "object" as const,
        properties: {
          request_id: {
            type: "string",
            description: "The request ID to approve (from list_elevation_requests)",
          },
          duration_minutes: {
            type: "number",
            description: `Override the requested duration (max: ${maxGrantDuration} minutes)`,
          },
        },
        required: ["request_id"],
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        if (!canAgentApprove(currentAgentName)) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Permission denied: '${currentAgentRole}' role cannot approve elevation requests. Only managers and King AI can approve.`,
              },
            ],
          };
        }

        const requestId = params.request_id as string;
        const durationOverride = params.duration_minutes as number | undefined;

        loadRequests();
        const request = requests.requests.find(
          (r) => r.id === requestId && r.status === "pending",
        );
        if (!request) {
          const pending = requests.requests.filter(
            (r) => r.status === "pending",
          );
          return {
            content: [
              {
                type: "text" as const,
                text: `Request '${requestId}' not found or already processed.\n\nPending requests:\n${
                  pending
                    .map(
                      (r) =>
                        `  - ${r.id}: ${r.agentName} wants '${r.capability}' — ${r.reason}`,
                    )
                    .join("\n") || "  (none)"
                }`,
              },
            ],
          };
        }

        // Verify this agent can grant to the requestor
        if (!canAgentGrant(currentAgentName, request.agentName)) {
          if (currentAgentRole === "manager") {
            return {
              content: [
                {
                  type: "text" as const,
                  text: `Cannot approve: '${request.agentName}' is not in your worker pool. Only their manager or King AI can approve this. Consider using request_elevation to escalate to King AI.`,
                },
              ],
            };
          }
          return {
            content: [
              {
                type: "text" as const,
                text: `Cannot approve: you don't have permission to grant capabilities to '${request.agentName}'.`,
              },
            ],
          };
        }

        // Verify the approver has the capability themselves
        const approverDenyList =
          permissions?.toolDenyLists?.[currentAgentRole] || [];
        const capabilityDenied = approverDenyList.some((d) =>
          d === request.capability || toolToCapability(d) === request.capability,
        );
        if (
          capabilityDenied &&
          !hasActiveGrant(currentAgentName, request.capability)
        ) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Cannot approve: you don't have '${request.capability}' permission yourself. You cannot grant capabilities you don't possess. Use request_elevation to request it from King AI first, then approve this request.`,
              },
            ],
          };
        }

        const duration = Math.min(
          durationOverride || request.durationMinutes || 30,
          maxGrantDuration,
        );
        const now = Date.now();

        // Create the grant
        loadGrants();
        const grant: Grant = {
          id: `grant-${now}-${Math.random().toString(36).slice(2, 8)}`,
          agentName: request.agentName,
          capability: request.capability,
          grantedBy: currentAgentName,
          grantedAt: now,
          expiresAt: now + duration * 60 * 1000,
          reason: request.reason,
        };
        grants.grants.push(grant);
        saveGrants();

        // Update request status
        request.status = "approved";
        request.decidedBy = currentAgentName;
        request.decidedAt = now;
        saveRequests();

        auditLog("ELEVATION_APPROVED", {
          requestId,
          grantId: grant.id,
          agent: request.agentName,
          capability: request.capability,
          durationMinutes: duration,
        });

        return {
          content: [
            {
              type: "text" as const,
              text: [
                "## Elevation Approved",
                "",
                `| Field | Value |`,
                `|-------|-------|`,
                `| **Grant ID** | \`${grant.id}\` |`,
                `| **Agent** | ${request.agentName} |`,
                `| **Capability** | ${request.capability} |`,
                `| **Duration** | ${duration} minutes |`,
                `| **Expires** | ${new Date(grant.expiresAt).toISOString()} |`,
                "",
                `'${request.agentName}' can now use '${request.capability}' for ${duration} minutes.`,
              ].join("\n"),
            },
          ],
        };
      },
    }),
    { names: ["approve_elevation"] },
  );

  // ===========================================================================
  // TOOL: deny_elevation
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "deny_elevation",
      description:
        "Deny a pending permission elevation request. Provide a reason for the denial.",
      parameters: {
        type: "object" as const,
        properties: {
          request_id: {
            type: "string",
            description: "The request ID to deny",
          },
          reason: {
            type: "string",
            description: "Why the request is being denied",
          },
        },
        required: ["request_id", "reason"],
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        if (!canAgentApprove(currentAgentName)) {
          return {
            content: [
              {
                type: "text" as const,
                text: "Permission denied: only managers and King AI can deny elevation requests.",
              },
            ],
          };
        }

        const requestId = params.request_id as string;
        const reason = params.reason as string;

        loadRequests();
        const request = requests.requests.find(
          (r) => r.id === requestId && r.status === "pending",
        );
        if (!request) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Request '${requestId}' not found or already processed.`,
              },
            ],
          };
        }

        request.status = "denied";
        request.decidedBy = currentAgentName;
        request.decidedAt = Date.now();
        request.denyReason = reason;
        saveRequests();

        auditLog("ELEVATION_DENIED", {
          requestId,
          agent: request.agentName,
          capability: request.capability,
          reason,
        });

        return {
          content: [
            {
              type: "text" as const,
              text: `Denied request '${requestId}' from '${request.agentName}' for '${request.capability}'.\nReason: ${reason}`,
            },
          ],
        };
      },
    }),
    { names: ["deny_elevation"] },
  );

  // ===========================================================================
  // TOOL: revoke_grant
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "revoke_grant",
      description:
        "Revoke an active permission grant immediately. Managers can revoke grants they issued; King AI can revoke any grant.",
      parameters: {
        type: "object" as const,
        properties: {
          grant_id: {
            type: "string",
            description: "The grant ID to revoke",
          },
        },
        required: ["grant_id"],
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        if (!canAgentApprove(currentAgentName)) {
          return {
            content: [
              {
                type: "text" as const,
                text: "Permission denied: only managers and King AI can revoke grants.",
              },
            ],
          };
        }

        const grantId = params.grant_id as string;

        loadGrants();
        const idx = grants.grants.findIndex((g) => g.id === grantId);
        if (idx === -1) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Grant '${grantId}' not found or already expired.`,
              },
            ],
          };
        }

        const grant = grants.grants[idx];

        // Managers can only revoke grants they issued (or for their workers)
        if (
          currentAgentRole === "manager" &&
          grant.grantedBy !== currentAgentName &&
          !isManagerOf(currentAgentName, grant.agentName)
        ) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Cannot revoke: this grant was issued by '${grant.grantedBy}' and '${grant.agentName}' is not in your pool.`,
              },
            ],
          };
        }

        grants.grants.splice(idx, 1);
        saveGrants();

        auditLog("GRANT_REVOKED", {
          grantId,
          agent: grant.agentName,
          capability: grant.capability,
          revokedBy: currentAgentName,
        });

        return {
          content: [
            {
              type: "text" as const,
              text: `Revoked grant '${grantId}': '${grant.agentName}' no longer has '${grant.capability}' permission.`,
            },
          ],
        };
      },
    }),
    { names: ["revoke_grant"] },
  );

  // ===========================================================================
  // TOOL: check_permissions
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "check_permissions",
      description:
        "Check current permissions, active grants, and pending requests. Workers can only check their own permissions; managers and King can check any agent.",
      parameters: {
        type: "object" as const,
        properties: {
          agent_name: {
            type: "string",
            description:
              "Optional: check another agent's permissions (managers/King only)",
          },
        },
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        const targetName =
          (params.agent_name as string) || currentAgentName;

        // Workers can only check their own
        if (targetName !== currentAgentName && currentAgentRole === "worker") {
          return {
            content: [
              {
                type: "text" as const,
                text: "Permission denied: workers can only check their own permissions.",
              },
            ],
          };
        }

        loadGrants();
        loadRequests();

        const role = getAgentRole(targetName);
        const roleDef = permissions?.roles?.[role];
        const denyList = permissions?.toolDenyLists?.[role] || [];
        const activeGrants = grants.grants.filter(
          (g) => g.agentName === targetName && g.expiresAt > Date.now(),
        );
        const pendingReqs = requests.requests.filter(
          (r) => r.agentName === targetName && r.status === "pending",
        );
        const manager = getManagerForAgent(targetName);

        const lines: string[] = [
          `## Permissions Report: ${targetName}`,
          "",
          `| Property | Value |`,
          `|----------|-------|`,
          `| **Role** | ${role} |`,
          `| **Manager** | ${manager || "(none — top level)"} |`,
          `| **Policy** | ${roleDef?.toolPolicy || "unknown"} |`,
          `| **Can Approve** | ${roleDef?.canApprove ? "yes" : "no"} |`,
          "",
        ];

        if (denyList.length > 0) {
          lines.push("### Denied Capabilities");
          lines.push("");
          for (const cap of denyList) {
            const granted = activeGrants.find((g) => g.capability === cap);
            if (granted) {
              const remaining = Math.round(
                (granted.expiresAt - Date.now()) / 60000,
              );
              lines.push(
                `- ~~${cap}~~ → **TEMPORARILY GRANTED** (${remaining}m remaining, by ${granted.grantedBy})`,
              );
            } else {
              lines.push(`- **${cap}** → BLOCKED`);
            }
          }
          lines.push("");
        } else {
          lines.push("### All capabilities allowed");
          lines.push("");
        }

        if (activeGrants.length > 0) {
          lines.push(`### Active Grants (${activeGrants.length})`);
          lines.push("");
          for (const g of activeGrants) {
            const remaining = Math.round(
              (g.expiresAt - Date.now()) / 60000,
            );
            lines.push(
              `- \`${g.id}\`: **${g.capability}** — ${remaining}m remaining (granted by ${g.grantedBy})`,
            );
          }
          lines.push("");
        }

        if (pendingReqs.length > 0) {
          lines.push(`### Pending Requests (${pendingReqs.length})`);
          lines.push("");
          for (const r of pendingReqs) {
            const age = Math.round((Date.now() - r.requestedAt) / 60000);
            lines.push(
              `- \`${r.id}\`: **${r.capability}** — requested ${age}m ago — ${r.reason}`,
            );
          }
        }

        return {
          content: [{ type: "text" as const, text: lines.join("\n") }],
        };
      },
    }),
    { names: ["check_permissions"] },
  );

  // ===========================================================================
  // TOOL: list_elevation_requests
  // ===========================================================================
  api.registerTool(
    () => ({
      name: "list_elevation_requests",
      description:
        "List pending elevation requests that you can approve or deny. Managers see requests from their own workers; King AI sees all requests.",
      parameters: {
        type: "object" as const,
        properties: {
          status: {
            type: "string",
            description: "Filter by status (default: pending)",
            enum: ["pending", "approved", "denied", "all"],
          },
        },
      },
      async execute(_toolId: string, params: Record<string, unknown>) {
        if (!canAgentApprove(currentAgentName)) {
          return {
            content: [
              {
                type: "text" as const,
                text: "Permission denied: only managers and King AI can list elevation requests.",
              },
            ],
          };
        }

        loadRequests();
        const statusFilter = (params.status as string) || "pending";

        let filtered = requests.requests;
        if (statusFilter !== "all") {
          filtered = filtered.filter((r) => r.status === statusFilter);
        }

        // Managers only see requests from their pool
        if (currentAgentRole === "manager") {
          const agentDef = permissions?.agents?.[currentAgentName];
          const pool = agentDef?.pool || [];
          filtered = filtered.filter((r) => pool.includes(r.agentName));
        }

        if (filtered.length === 0) {
          return {
            content: [
              {
                type: "text" as const,
                text: `No ${statusFilter} elevation requests${currentAgentRole === "manager" ? " from your workers" : ""}.`,
              },
            ],
          };
        }

        const lines: string[] = [
          `## Elevation Requests (${statusFilter})`,
          "",
        ];

        for (const r of filtered) {
          const age = Math.round((Date.now() - r.requestedAt) / 60000);
          lines.push(`### \`${r.id}\``);
          lines.push("");
          lines.push(`| Field | Value |`);
          lines.push(`|-------|-------|`);
          lines.push(`| **Agent** | ${r.agentName} |`);
          lines.push(`| **Capability** | ${r.capability} |`);
          lines.push(`| **Reason** | ${r.reason} |`);
          lines.push(`| **Duration Requested** | ${r.durationMinutes}m |`);
          lines.push(`| **Requested** | ${age} minutes ago |`);
          lines.push(`| **Status** | ${r.status} |`);
          if (r.decidedBy) {
            lines.push(
              `| **Decided by** | ${r.decidedBy} at ${new Date(r.decidedAt!).toISOString()} |`,
            );
          }
          if (r.denyReason) {
            lines.push(`| **Deny reason** | ${r.denyReason} |`);
          }
          lines.push("");
          if (r.status === "pending") {
            lines.push(
              `→ Use \`approve_elevation\` with request_id="${r.id}" to approve`,
            );
            lines.push(
              `→ Use \`deny_elevation\` with request_id="${r.id}" to deny`,
            );
            lines.push("");
          }
        }

        return {
          content: [{ type: "text" as const, text: lines.join("\n") }],
        };
      },
    }),
    { names: ["list_elevation_requests"] },
  );

  // Log plugin initialization to audit
  auditLog("PLUGIN_LOADED", {
    role: currentAgentRole,
    denyList: permissions?.toolDenyLists?.[currentAgentRole] || [],
  });
}
