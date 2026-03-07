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
  riskAssessment?: RiskAssessment;
}

interface RequestsState {
  requests: ElevationRequest[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// NEW: Risk Assessment Engine (ported from mother-harness approval-service.ts)
// ═══════════════════════════════════════════════════════════════════════════════

interface RiskAssessment {
  level: "low" | "medium" | "high" | "critical";
  score: number; // 0-100
  factors: string[];
  recommendation: "auto-approve" | "manager-review" | "king-review" | "human-required";
  timestamp: string;
}

const RISKY_PATTERNS: Array<{ pattern: RegExp; risk: number; label: string }> = [
  // Filesystem destruction
  { pattern: /rm\s+(-rf?|--recursive)\s+[\/~]/i, risk: 90, label: "Recursive delete on root/home" },
  { pattern: /rm\s+-rf?\s+\*/i, risk: 80, label: "Wildcard deletion" },
  { pattern: />\s*\/dev\//i, risk: 70, label: "Write to device file" },
  { pattern: /mkfs|fdisk|dd\s+if=/i, risk: 95, label: "Disk formatting/raw write" },

  // Credential/secret exposure
  { pattern: /password|secret|api_key|token|credential/i, risk: 60, label: "Credential reference" },
  { pattern: /\.env|\.pem|\.key|id_rsa/i, risk: 50, label: "Secret file access" },
  { pattern: /curl.*-H.*[Aa]uthorization/i, risk: 55, label: "Auth header in request" },

  // Network exfiltration
  { pattern: /curl\s+(-X\s+POST|--data)\s+.*https?:\/\/(?!localhost)/i, risk: 65, label: "External data POST" },
  { pattern: /wget\s+.*-O\s*-\s*\|/i, risk: 70, label: "Remote code pipe" },
  { pattern: /nc\s+-l|netcat|ncat/i, risk: 75, label: "Netcat listener" },

  // Privilege escalation
  { pattern: /sudo\s/i, risk: 80, label: "Sudo command" },
  { pattern: /chmod\s+[0-7]*7[0-7]*/i, risk: 40, label: "World-writable permission" },
  { pattern: /chown\s+root/i, risk: 70, label: "Change ownership to root" },

  // System modification
  { pattern: /launchctl|systemctl|service\s+(start|stop|restart)/i, risk: 60, label: "Service management" },
  { pattern: /brew\s+(install|uninstall|remove)/i, risk: 30, label: "Package management" },
  { pattern: /npm\s+(install|uninstall)\s+-g/i, risk: 40, label: "Global npm install" },
  { pattern: /pip\s+install(?!\s+--user)/i, risk: 35, label: "System pip install" },

  // Database operations
  { pattern: /DROP\s+(TABLE|DATABASE|INDEX)/i, risk: 85, label: "Database DROP" },
  { pattern: /TRUNCATE\s+TABLE/i, risk: 80, label: "Table truncation" },
  { pattern: /DELETE\s+FROM\s+\w+\s*(;|\s*$)/i, risk: 75, label: "Unfiltered DELETE" },
  { pattern: /ALTER\s+TABLE.*DROP/i, risk: 65, label: "Column drop" },

  // External communication
  { pattern: /sendmail|mail\s+-s|smtp|gmail/i, risk: 50, label: "Email sending" },
  { pattern: /git\s+push\s+(--force|origin\s+main)/i, risk: 60, label: "Force push / push to main" },

  // Process/container management
  { pattern: /kill\s+-9/i, risk: 55, label: "Force kill process" },
  { pattern: /docker\s+rm\s+-f/i, risk: 50, label: "Force remove container" },
  { pattern: /pkill|killall/i, risk: 45, label: "Bulk process kill" },
];

// Risky tool names that warrant elevated review
const RISKY_TOOLS = new Set([
  "exec", "bash", "shell", "terminal", "run_command",
  "elevated_exec", "sudo",
  "broadcast", "message_send",
]);

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
  // Strip any prefix (e.g., "ai-final." or "army.")
  const name = label.replace(/^(ai-final\.|army\.)/, "");
  return name || "king-ai";
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
      const now = Date.now();
      const before = grants.grants.length;
      grants.grants = grants.grants.filter((g) => g.expiresAt > now);
      if (grants.grants.length !== before) saveGrants();
    }
  } catch { grants = { grants: [] }; }
}

function saveGrants(): void {
  writeFileSync(join(stateDir, "grants.json"), JSON.stringify(grants, null, 2));
}

function loadRequests(): void {
  const path = join(stateDir, "requests.json");
  try {
    if (existsSync(path)) {
      requests = JSON.parse(readFileSync(path, "utf-8"));
    }
  } catch { requests = { requests: [] }; }
}

function saveRequests(): void {
  writeFileSync(join(stateDir, "requests.json"), JSON.stringify(requests, null, 2));
}

function auditLog(action: string, details: Record<string, unknown>): void {
  if (!auditEnabled) return;
  const entry = {
    timestamp: new Date().toISOString(),
    agent: currentAgentName,
    role: currentAgentRole,
    action,
    ...details,
  };
  try {
    appendFileSync(join(stateDir, "audit.jsonl"), JSON.stringify(entry) + "\n");
  } catch { /* best-effort */ }
}

function hasActiveGrant(agentName: string, capability: string): boolean {
  const now = Date.now();
  return grants.grants.some(
    (g) => g.agentName === agentName && g.capability === capability && g.expiresAt > now,
  );
}

function getManagerForAgent(agentName: string): string | null {
  return permissions?.agents?.[agentName]?.manager || null;
}

function isManagerOf(managerName: string, workerName: string): boolean {
  return permissions?.agents?.[workerName]?.manager === managerName;
}

function canAgentGrant(granterName: string, targetName: string): boolean {
  const granterRole = getAgentRole(granterName);
  const targetRole = getAgentRole(targetName);
  const roleDef = permissions?.roles?.[granterRole];
  if (!roleDef?.canGrant?.length || !roleDef.canGrant.includes(targetRole)) return false;
  if (granterRole === "manager") return isManagerOf(granterName, targetName);
  return granterRole === "king";
}

function canAgentApprove(agentName: string): boolean {
  const role = getAgentRole(agentName);
  return permissions?.roles?.[role]?.canApprove === true;
}

function toolToCapability(toolName: string): string | null {
  const n = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");
  if (["exec", "bash", "shell", "terminal", "run_command"].includes(n)) return "exec";
  if (["sessions_send", "message_send", "messagesend"].includes(n)) return "sessions_send";
  if (["broadcast"].includes(n)) return "broadcast";
  if (["elevated_exec", "sudo", "elevatedexec"].includes(n)) return "elevated";
  return null;
}

function isToolDenied(agentName: string, role: string, toolName: string): { denied: boolean; reason?: string } {
  const roleDef = permissions?.roles?.[role];
  if (!roleDef || roleDef.toolPolicy === "allow-all") return { denied: false };
  const denyList = permissions?.toolDenyLists?.[role] || [];
  if (denyList.length === 0) return { denied: false };
  const n = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");
  const directMatch = denyList.some((d) => n === d || n.includes(d));
  if (!directMatch) return { denied: false };
  const capability = toolToCapability(toolName);
  if (capability && hasActiveGrant(agentName, capability)) return { denied: false };
  if (hasActiveGrant(agentName, n)) return { denied: false };
  return {
    denied: true,
    reason: `Permission denied: '${role}' role cannot use '${toolName}'. Use request_elevation to request temporary access.`,
  };
}

function isPathAllowed(agentName: string, role: string, targetPath: string): boolean {
  const policy = permissions?.filesystemPolicy?.[role];
  if (!policy || policy.mode === "unrestricted") return true;
  const agentDir = process.env.OPENCLAW_STATE_DIR || "";
  const allowed = [agentDir, ...(policy.additionalAllowedPaths || [])];
  for (const prefix of allowed) {
    if (prefix && targetPath.startsWith(prefix)) return true;
  }
  if (hasActiveGrant(agentName, "fs_unrestricted")) return true;
  return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// NEW: Risk Assessment Functions
// ═══════════════════════════════════════════════════════════════════════════════

function assessRisk(toolName: string, params: Record<string, unknown>): RiskAssessment {
  const factors: string[] = [];
  let maxRisk = 0;

  // Check if tool itself is risky
  if (RISKY_TOOLS.has(toolName.toLowerCase())) {
    maxRisk = Math.max(maxRisk, 30);
    factors.push(`Risky tool: ${toolName}`);
  }

  // Check all string params against risky patterns
  const allParams = JSON.stringify(params);
  for (const { pattern, risk, label } of RISKY_PATTERNS) {
    if (pattern.test(allParams)) {
      maxRisk = Math.max(maxRisk, risk);
      factors.push(label);
    }
  }

  // Determine risk level
  let level: RiskAssessment["level"];
  if (maxRisk >= 80) level = "critical";
  else if (maxRisk >= 60) level = "high";
  else if (maxRisk >= 30) level = "medium";
  else level = "low";

  // Determine recommendation
  let recommendation: RiskAssessment["recommendation"];
  if (level === "critical") recommendation = "human-required";
  else if (level === "high") recommendation = "king-review";
  else if (level === "medium") recommendation = "manager-review";
  else recommendation = "auto-approve";

  return {
    level,
    score: maxRisk,
    factors,
    recommendation,
    timestamp: new Date().toISOString(),
  };
}

// =============================================================================
// Plugin Registration
// =============================================================================

export default function register(api: OpenClawPluginApi) {
  pluginDir = dirname(api.source);
  stateDir = join(pluginDir, "state");
  if (!existsSync(stateDir)) mkdirSync(stateDir, { recursive: true });

  const pCfg = (api.pluginConfig ?? {}) as Record<string, unknown>;
  auditEnabled = pCfg.auditLogEnabled !== false;
  maxGrantDuration = (pCfg.maxGrantDurationMinutes as number) || 480;

  loadPermissions();
  loadGrants();
  loadRequests();

  currentAgentName = getAgentName();
  currentAgentRole = getAgentRole(currentAgentName);

  api.logger.info?.(`permission-broker: loaded for agent=${currentAgentName} role=${currentAgentRole}`);

  // Watch for cross-process grant/request changes
  try {
    watchFile(join(stateDir, "grants.json"), { interval: 2000 }, () => { try { loadGrants(); } catch {} });
    watchFile(join(stateDir, "requests.json"), { interval: 2000 }, () => { try { loadRequests(); } catch {} });
  } catch {}

  // ===========================================================================
  // HOOK: before_tool_call — PRIMARY PERMISSION + RISK ENFORCEMENT
  // ===========================================================================
  api.on("before_tool_call", async (event) => {
    const { toolName, params } = event;

    // Permission broker's own tools are always allowed
    const brokerTools = [
      "request_elevation", "approve_elevation", "deny_elevation",
      "check_permissions", "list_elevation_requests", "revoke_grant",
      "assess_risk",
    ];
    if (brokerTools.includes(toolName)) return;

    loadGrants();

    // --- Tool deny list check ---
    const check = isToolDenied(currentAgentName, currentAgentRole, toolName);
    if (check.denied) {
      auditLog("TOOL_BLOCKED", { toolName, params, reason: check.reason });
      return { block: true, blockReason: check.reason };
    }

    // --- NEW: Risk assessment for exec-class tools ---
    if (RISKY_TOOLS.has(toolName.toLowerCase()) || toolToCapability(toolName) === "exec") {
      const risk = assessRisk(toolName, params as Record<string, unknown>);
      auditLog("RISK_ASSESSED", { toolName, risk });

      // For workers: block high/critical risk even with grants
      if (currentAgentRole === "worker" && (risk.level === "high" || risk.level === "critical")) {
        return {
          block: true,
          blockReason: `Risk assessment BLOCKED: ${risk.level} risk (score ${risk.score}/100). Factors: ${risk.factors.join(", ")}. This requires ${risk.recommendation}. Use request_elevation with details about why this operation is safe.`,
        };
      }

      // For managers: warn on critical, block nothing (they have authority)
      if (currentAgentRole === "manager" && risk.level === "critical") {
        auditLog("RISK_WARNING_MANAGER", { toolName, risk });
        // Don't block, but log prominently
      }
    }

    // --- Filesystem sandboxing for workers ---
    if (currentAgentRole === "worker") {
      const fileTools = ["read", "write", "edit", "apply_patch", "cat", "head", "tail", "grep", "create", "mkdir"];
      if (fileTools.includes(toolName)) {
        const targetPath = (params.path || params.filePath || params.file || params.dir || params.directory || "") as string;
        if (targetPath && !isPathAllowed(currentAgentName, currentAgentRole, targetPath)) {
          auditLog("FS_BLOCKED", { toolName, targetPath });
          return {
            block: true,
            blockReason: `Permission denied: worker '${currentAgentName}' can only access files within its workspace. Use request_elevation with capability 'fs_unrestricted' for broader access.`,
          };
        }
      }
    }

    // --- Cross-agent messaging restriction for workers ---
    if (currentAgentRole === "worker" && (toolName === "sessions_send" || toolName === "message_send")) {
      const target = (params.target || params.to || "") as string;
      const manager = getManagerForAgent(currentAgentName);
      if (manager && !target.includes(manager) && !hasActiveGrant(currentAgentName, "sessions_send")) {
        auditLog("MSG_BLOCKED", { toolName, target, allowedManager: manager });
        return {
          block: true,
          blockReason: `Permission denied: worker '${currentAgentName}' can only send messages to manager '${manager}'.`,
        };
      }
    }

    auditLog("TOOL_ALLOWED", { toolName });
  }, { priority: 100 });

  // ===========================================================================
  // HOOK: after_tool_call — AUDIT LOGGING
  // ===========================================================================
  api.on("after_tool_call", async (event) => {
    auditLog("TOOL_COMPLETED", { toolName: event.toolName, durationMs: event.durationMs, error: event.error || null });
  });

  // ===========================================================================
  // HOOK: message_sending — RESTRICT WORKER BROADCAST
  // ===========================================================================
  api.on("message_sending", async (event) => {
    if (currentAgentRole !== "worker") return;
    const meta = event.metadata as Record<string, unknown> | undefined;
    if (meta?.broadcast) {
      auditLog("BROADCAST_BLOCKED", { to: event.to });
      return { cancel: true };
    }
  });

  // ===========================================================================
  // TOOL: assess_risk — NEW: On-demand risk assessment
  // ===========================================================================
  api.registerTool({
    name: "assess_risk",
    description: "Assess the risk level of a command or operation before executing it. Returns risk score, factors, and recommendation.",
    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "The command or operation to assess",
        },
        tool_name: {
          type: "string",
          description: "The tool that would execute this command (e.g., 'exec', 'bash')",
        },
      },
      required: ["command"],
    },
    execute: async (args: { command: string; tool_name?: string }) => {
      const risk = assessRisk(args.tool_name || "exec", { command: args.command, content: args.command });
      const lines = [
        `## Risk Assessment`,
        ``,
        `| Property | Value |`,
        `|----------|-------|`,
        `| **Level** | ${risk.level.toUpperCase()} |`,
        `| **Score** | ${risk.score}/100 |`,
        `| **Recommendation** | ${risk.recommendation} |`,
        ``,
      ];
      if (risk.factors.length > 0) {
        lines.push(`### Risk Factors`);
        for (const f of risk.factors) lines.push(`- ${f}`);
      } else {
        lines.push(`No risk factors detected.`);
      }
      return lines.join("\n");
    },
  });

  // ===========================================================================
  // TOOL: request_elevation
  // ===========================================================================
  api.registerTool({
    name: "request_elevation",
    description: "Request temporary elevated permissions from your manager (or King AI if you are a manager).",
    parameters: {
      type: "object",
      properties: {
        capability: {
          type: "string",
          description: "The capability to request: exec, sessions_send, fs_unrestricted, elevated, web_search, web_fetch, broadcast",
          enum: ["exec", "sessions_send", "fs_unrestricted", "elevated", "web_search", "web_fetch", "broadcast"],
        },
        reason: {
          type: "string",
          description: "Detailed explanation of why this permission is needed",
        },
        duration_minutes: {
          type: "number",
          description: `How long the permission is needed (default: 30, max: ${maxGrantDuration})`,
        },
      },
      required: ["capability", "reason"],
    },
    execute: async (args: { capability: string; reason: string; duration_minutes?: number }) => {
      if (currentAgentRole === "king") {
        return "King AI has full unrestricted permissions — no elevation needed.";
      }

      const durationMinutes = Math.min(args.duration_minutes || 30, maxGrantDuration);
      const approver = currentAgentRole === "worker"
        ? getManagerForAgent(currentAgentName) || "king-ai"
        : "king-ai";

      loadGrants();
      if (hasActiveGrant(currentAgentName, args.capability)) {
        const grant = grants.grants.find((g) => g.agentName === currentAgentName && g.capability === args.capability);
        const remaining = grant ? Math.round((grant.expiresAt - Date.now()) / 60000) : 0;
        return `Already have '${args.capability}' permission (${remaining} minutes remaining).`;
      }

      // Perform risk assessment on the reason
      const risk = assessRisk(args.capability, { reason: args.reason, capability: args.capability });

      loadRequests();
      const request: ElevationRequest = {
        id: `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        agentName: currentAgentName,
        capability: args.capability,
        reason: args.reason,
        durationMinutes,
        requestedAt: Date.now(),
        status: "pending",
        riskAssessment: risk,
      };
      requests.requests.push(request);
      saveRequests();

      auditLog("ELEVATION_REQUESTED", {
        requestId: request.id,
        capability: args.capability,
        reason: args.reason,
        approver,
        durationMinutes,
        riskAssessment: risk,
      });

      // Notify approver
      const approverPort = permissions?.agentPorts?.[approver];
      if (approverPort) {
        try {
          await fetch(`http://localhost:${approverPort}/api/v1/notify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: "elevation_request", from: currentAgentName, request }),
            signal: AbortSignal.timeout(3000),
          }).catch(() => {});
        } catch {}
      }

      return [
        `## Elevation Request Submitted`,
        ``,
        `| Field | Value |`,
        `|-------|-------|`,
        `| **Request ID** | ${request.id} |`,
        `| **Capability** | ${args.capability} |`,
        `| **Reason** | ${args.reason} |`,
        `| **Approver** | ${approver} |`,
        `| **Duration** | ${durationMinutes} minutes |`,
        `| **Risk Level** | ${risk.level.toUpperCase()} (${risk.score}/100) |`,
        `| **Status** | pending |`,
        ``,
        `Waiting for **${approver}** to approve.`,
      ].join("\n");
    },
  });

  // ===========================================================================
  // TOOL: approve_elevation
  // ===========================================================================
  api.registerTool({
    name: "approve_elevation",
    description: "Approve a pending elevation request. Managers approve their workers; King approves all.",
    parameters: {
      type: "object",
      properties: {
        request_id: { type: "string", description: "The request ID to approve" },
        duration_minutes: { type: "number", description: `Override duration (max: ${maxGrantDuration})` },
      },
      required: ["request_id"],
    },
    execute: async (args: { request_id: string; duration_minutes?: number }) => {
      if (!canAgentApprove(currentAgentName)) {
        return `Permission denied: '${currentAgentRole}' cannot approve requests.`;
      }

      loadRequests();
      const request = requests.requests.find((r) => r.id === args.request_id && r.status === "pending");
      if (!request) {
        const pending = requests.requests.filter((r) => r.status === "pending");
        return `Request '${args.request_id}' not found or already processed.\n\nPending:\n${pending.map((r) => `  - ${r.id}: ${r.agentName} wants '${r.capability}'`).join("\n") || "  (none)"}`;
      }

      if (!canAgentGrant(currentAgentName, request.agentName)) {
        return `Cannot approve: '${request.agentName}' is not in your jurisdiction.`;
      }

      // Check risk assessment — warn on high risk
      if (request.riskAssessment && request.riskAssessment.level === "critical" && currentAgentRole !== "king") {
        return `Cannot approve: request has CRITICAL risk assessment (score ${request.riskAssessment.score}/100). Factors: ${request.riskAssessment.factors.join(", ")}. This requires King AI approval. Escalate via request_elevation.`;
      }

      const duration = Math.min(args.duration_minutes || request.durationMinutes || 30, maxGrantDuration);
      const now = Date.now();

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

      request.status = "approved";
      request.decidedBy = currentAgentName;
      request.decidedAt = now;
      saveRequests();

      auditLog("ELEVATION_APPROVED", { requestId: args.request_id, grantId: grant.id, agent: request.agentName, capability: request.capability, duration });

      return [
        `## Elevation Approved`,
        ``,
        `| Field | Value |`,
        `|-------|-------|`,
        `| **Grant ID** | ${grant.id} |`,
        `| **Agent** | ${request.agentName} |`,
        `| **Capability** | ${request.capability} |`,
        `| **Duration** | ${duration} minutes |`,
        `| **Expires** | ${new Date(grant.expiresAt).toISOString()} |`,
      ].join("\n");
    },
  });

  // ===========================================================================
  // TOOL: deny_elevation
  // ===========================================================================
  api.registerTool({
    name: "deny_elevation",
    description: "Deny a pending elevation request with a reason.",
    parameters: {
      type: "object",
      properties: {
        request_id: { type: "string", description: "Request ID to deny" },
        reason: { type: "string", description: "Reason for denial" },
      },
      required: ["request_id", "reason"],
    },
    execute: async (args: { request_id: string; reason: string }) => {
      if (!canAgentApprove(currentAgentName)) {
        return "Permission denied: only managers and King AI can deny requests.";
      }

      loadRequests();
      const request = requests.requests.find((r) => r.id === args.request_id && r.status === "pending");
      if (!request) return `Request '${args.request_id}' not found or already processed.`;

      request.status = "denied";
      request.decidedBy = currentAgentName;
      request.decidedAt = Date.now();
      request.denyReason = args.reason;
      saveRequests();

      auditLog("ELEVATION_DENIED", { requestId: args.request_id, agent: request.agentName, capability: request.capability, reason: args.reason });

      return `Denied '${args.request_id}' from '${request.agentName}' for '${request.capability}'. Reason: ${args.reason}`;
    },
  });

  // ===========================================================================
  // TOOL: revoke_grant
  // ===========================================================================
  api.registerTool({
    name: "revoke_grant",
    description: "Revoke an active grant immediately.",
    parameters: {
      type: "object",
      properties: {
        grant_id: { type: "string", description: "Grant ID to revoke" },
      },
      required: ["grant_id"],
    },
    execute: async (args: { grant_id: string }) => {
      if (!canAgentApprove(currentAgentName)) return "Permission denied: only managers and King AI can revoke.";
      loadGrants();
      const idx = grants.grants.findIndex((g) => g.id === args.grant_id);
      if (idx === -1) return `Grant '${args.grant_id}' not found or expired.`;
      const grant = grants.grants[idx];
      if (currentAgentRole === "manager" && grant.grantedBy !== currentAgentName && !isManagerOf(currentAgentName, grant.agentName)) {
        return `Cannot revoke: not your grant and '${grant.agentName}' is not your worker.`;
      }
      grants.grants.splice(idx, 1);
      saveGrants();
      auditLog("GRANT_REVOKED", { grantId: args.grant_id, agent: grant.agentName, capability: grant.capability });
      return `Revoked: '${grant.agentName}' no longer has '${grant.capability}'.`;
    },
  });

  // ===========================================================================
  // TOOL: check_permissions
  // ===========================================================================
  api.registerTool({
    name: "check_permissions",
    description: "Check current permissions, active grants, and pending requests for self or another agent.",
    parameters: {
      type: "object",
      properties: {
        agent_name: { type: "string", description: "Optional: check another agent (managers/King only)" },
      },
    },
    execute: async (args: { agent_name?: string }) => {
      const targetName = args.agent_name || currentAgentName;
      if (targetName !== currentAgentName && currentAgentRole === "worker") {
        return "Permission denied: workers can only check their own permissions.";
      }

      loadGrants();
      loadRequests();

      const role = getAgentRole(targetName);
      const denyList = permissions?.toolDenyLists?.[role] || [];
      const activeGrants = grants.grants.filter((g) => g.agentName === targetName && g.expiresAt > Date.now());
      const pendingReqs = requests.requests.filter((r) => r.agentName === targetName && r.status === "pending");
      const manager = getManagerForAgent(targetName);

      const lines: string[] = [
        `## Permissions: ${targetName}`,
        "",
        `| Property | Value |`,
        `|----------|-------|`,
        `| **Role** | ${role} |`,
        `| **Manager** | ${manager || "(top level)"} |`,
        "",
      ];

      if (denyList.length > 0) {
        lines.push("### Denied Capabilities");
        for (const cap of denyList) {
          const granted = activeGrants.find((g) => g.capability === cap);
          if (granted) {
            const rem = Math.round((granted.expiresAt - Date.now()) / 60000);
            lines.push(`- ~~${cap}~~ → **GRANTED** (${rem}m left, by ${granted.grantedBy})`);
          } else {
            lines.push(`- **${cap}** → BLOCKED`);
          }
        }
        lines.push("");
      }

      if (activeGrants.length > 0) {
        lines.push(`### Active Grants (${activeGrants.length})`);
        for (const g of activeGrants) {
          const rem = Math.round((g.expiresAt - Date.now()) / 60000);
          lines.push(`- ${g.id}: **${g.capability}** — ${rem}m left`);
        }
        lines.push("");
      }

      if (pendingReqs.length > 0) {
        lines.push(`### Pending Requests (${pendingReqs.length})`);
        for (const r of pendingReqs) {
          const age = Math.round((Date.now() - r.requestedAt) / 60000);
          lines.push(`- ${r.id}: **${r.capability}** — ${age}m ago — ${r.reason}`);
        }
      }

      return lines.join("\n");
    },
  });

  // ===========================================================================
  // TOOL: list_elevation_requests
  // ===========================================================================
  api.registerTool({
    name: "list_elevation_requests",
    description: "List pending elevation requests you can approve/deny.",
    parameters: {
      type: "object",
      properties: {
        status: { type: "string", enum: ["pending", "approved", "denied", "all"], description: "Filter by status (default: pending)" },
      },
    },
    execute: async (args: { status?: string }) => {
      if (!canAgentApprove(currentAgentName)) return "Permission denied: only managers and King AI can list requests.";

      loadRequests();
      const statusFilter = args.status || "pending";
      let filtered = requests.requests;
      if (statusFilter !== "all") filtered = filtered.filter((r) => r.status === statusFilter);

      // Managers only see their pool
      if (currentAgentRole === "manager") {
        const pool = permissions?.agents?.[currentAgentName]?.pool || [];
        filtered = filtered.filter((r) => pool.includes(r.agentName));
      }

      if (filtered.length === 0) return `No ${statusFilter} requests.`;

      const lines: string[] = [`## Elevation Requests (${statusFilter})`, ""];
      for (const r of filtered) {
        const age = Math.round((Date.now() - r.requestedAt) / 60000);
        lines.push(`### ${r.id}`);
        lines.push(`| Field | Value |`);
        lines.push(`|-------|-------|`);
        lines.push(`| **Agent** | ${r.agentName} |`);
        lines.push(`| **Capability** | ${r.capability} |`);
        lines.push(`| **Reason** | ${r.reason} |`);
        lines.push(`| **Duration** | ${r.durationMinutes}m |`);
        lines.push(`| **Requested** | ${age}m ago |`);
        if (r.riskAssessment) {
          lines.push(`| **Risk** | ${r.riskAssessment.level.toUpperCase()} (${r.riskAssessment.score}/100) |`);
        }
        lines.push(`| **Status** | ${r.status} |`);
        if (r.status === "pending") {
          lines.push("");
          lines.push(`→ approve_elevation request_id="${r.id}"`);
          lines.push(`→ deny_elevation request_id="${r.id}" reason="..."`);
        }
        lines.push("");
      }
      return lines.join("\n");
    },
  });

  // Log init
  auditLog("PLUGIN_LOADED", { role: currentAgentRole, denyList: permissions?.toolDenyLists?.[currentAgentRole] || [] });
}
