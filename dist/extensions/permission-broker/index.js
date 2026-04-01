import { appendFileSync, existsSync, mkdirSync, readFileSync, watchFile, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
//#region extensions/permission-broker/index.ts
const RISKY_PATTERNS = [
	{
		pattern: /rm\s+(-rf?|--recursive)\s+[\/~]/i,
		risk: 90,
		label: "Recursive delete on root/home"
	},
	{
		pattern: /rm\s+-rf?\s+\*/i,
		risk: 80,
		label: "Wildcard deletion"
	},
	{
		pattern: />\s*\/dev\//i,
		risk: 70,
		label: "Write to device file"
	},
	{
		pattern: /mkfs|fdisk|dd\s+if=/i,
		risk: 95,
		label: "Disk formatting/raw write"
	},
	{
		pattern: /password|secret|api_key|token|credential/i,
		risk: 60,
		label: "Credential reference"
	},
	{
		pattern: /\.env|\.pem|\.key|id_rsa/i,
		risk: 50,
		label: "Secret file access"
	},
	{
		pattern: /curl.*-H.*[Aa]uthorization/i,
		risk: 55,
		label: "Auth header in request"
	},
	{
		pattern: /curl\s+(-X\s+POST|--data)\s+.*https?:\/\/(?!localhost)/i,
		risk: 65,
		label: "External data POST"
	},
	{
		pattern: /wget\s+.*-O\s*-\s*\|/i,
		risk: 70,
		label: "Remote code pipe"
	},
	{
		pattern: /nc\s+-l|netcat|ncat/i,
		risk: 75,
		label: "Netcat listener"
	},
	{
		pattern: /sudo\s/i,
		risk: 80,
		label: "Sudo command"
	},
	{
		pattern: /chmod\s+[0-7]*7[0-7]*/i,
		risk: 40,
		label: "World-writable permission"
	},
	{
		pattern: /chown\s+root/i,
		risk: 70,
		label: "Change ownership to root"
	},
	{
		pattern: /launchctl|systemctl|service\s+(start|stop|restart)/i,
		risk: 60,
		label: "Service management"
	},
	{
		pattern: /brew\s+(install|uninstall|remove)/i,
		risk: 30,
		label: "Package management"
	},
	{
		pattern: /npm\s+(install|uninstall)\s+-g/i,
		risk: 40,
		label: "Global npm install"
	},
	{
		pattern: /pip\s+install(?!\s+--user)/i,
		risk: 35,
		label: "System pip install"
	},
	{
		pattern: /DROP\s+(TABLE|DATABASE|INDEX)/i,
		risk: 85,
		label: "Database DROP"
	},
	{
		pattern: /TRUNCATE\s+TABLE/i,
		risk: 80,
		label: "Table truncation"
	},
	{
		pattern: /DELETE\s+FROM\s+\w+\s*(;|\s*$)/i,
		risk: 75,
		label: "Unfiltered DELETE"
	},
	{
		pattern: /ALTER\s+TABLE.*DROP/i,
		risk: 65,
		label: "Column drop"
	},
	{
		pattern: /sendmail|mail\s+-s|smtp|gmail/i,
		risk: 50,
		label: "Email sending"
	},
	{
		pattern: /git\s+push\s+(--force|origin\s+main)/i,
		risk: 60,
		label: "Force push / push to main"
	},
	{
		pattern: /kill\s+-9/i,
		risk: 55,
		label: "Force kill process"
	},
	{
		pattern: /docker\s+rm\s+-f/i,
		risk: 50,
		label: "Force remove container"
	},
	{
		pattern: /pkill|killall/i,
		risk: 45,
		label: "Bulk process kill"
	}
];
const RISKY_TOOLS = new Set([
	"exec",
	"bash",
	"shell",
	"terminal",
	"run_command",
	"elevated_exec",
	"sudo",
	"broadcast",
	"message_send"
]);
let permissions;
let grants = { grants: [] };
let requests = { requests: [] };
let pluginDir;
let stateDir;
let currentAgentName;
let currentAgentRole;
let auditEnabled = true;
let maxGrantDuration = 480;
function getAgentName() {
	return (process.env.OPENCLAW_SERVICE_LABEL || "").replace(/^(ai-final\.|army\.)/, "") || "king-ai";
}
function getAgentRole(name) {
	const agentDef = permissions?.agents?.[name];
	if (agentDef) return agentDef.role;
	return "king";
}
function loadPermissions() {
	const path = join(pluginDir, "permissions.json");
	if (existsSync(path)) permissions = JSON.parse(readFileSync(path, "utf-8"));
}
function loadGrants() {
	const path = join(stateDir, "grants.json");
	try {
		if (existsSync(path)) {
			grants = JSON.parse(readFileSync(path, "utf-8"));
			const now = Date.now();
			const before = grants.grants.length;
			grants.grants = grants.grants.filter((g) => g.expiresAt > now);
			if (grants.grants.length !== before) saveGrants();
		}
	} catch {
		grants = { grants: [] };
	}
}
function saveGrants() {
	writeFileSync(join(stateDir, "grants.json"), JSON.stringify(grants, null, 2));
}
function loadRequests() {
	const path = join(stateDir, "requests.json");
	try {
		if (existsSync(path)) requests = JSON.parse(readFileSync(path, "utf-8"));
	} catch {
		requests = { requests: [] };
	}
}
function saveRequests() {
	writeFileSync(join(stateDir, "requests.json"), JSON.stringify(requests, null, 2));
}
function auditLog(action, details) {
	if (!auditEnabled) return;
	const entry = {
		timestamp: (/* @__PURE__ */ new Date()).toISOString(),
		agent: currentAgentName,
		role: currentAgentRole,
		action,
		...details
	};
	try {
		appendFileSync(join(stateDir, "audit.jsonl"), JSON.stringify(entry) + "\n");
	} catch {}
}
function hasActiveGrant(agentName, capability) {
	const now = Date.now();
	return grants.grants.some((g) => g.agentName === agentName && g.capability === capability && g.expiresAt > now);
}
function getManagerForAgent(agentName) {
	return permissions?.agents?.[agentName]?.manager || null;
}
function isManagerOf(managerName, workerName) {
	return permissions?.agents?.[workerName]?.manager === managerName;
}
function canAgentGrant(granterName, targetName) {
	const granterRole = getAgentRole(granterName);
	const targetRole = getAgentRole(targetName);
	const roleDef = permissions?.roles?.[granterRole];
	if (!roleDef?.canGrant?.length || !roleDef.canGrant.includes(targetRole)) return false;
	if (granterRole === "manager") return isManagerOf(granterName, targetName);
	return granterRole === "king";
}
function canAgentApprove(agentName) {
	const role = getAgentRole(agentName);
	return permissions?.roles?.[role]?.canApprove === true;
}
function toolToCapability(toolName) {
	const n = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");
	if ([
		"exec",
		"bash",
		"shell",
		"terminal",
		"run_command"
	].includes(n)) return "exec";
	if ([
		"sessions_send",
		"message_send",
		"messagesend"
	].includes(n)) return "sessions_send";
	if (["broadcast"].includes(n)) return "broadcast";
	if ([
		"elevated_exec",
		"sudo",
		"elevatedexec"
	].includes(n)) return "elevated";
	return null;
}
function isToolDenied(agentName, role, toolName) {
	const roleDef = permissions?.roles?.[role];
	if (!roleDef || roleDef.toolPolicy === "allow-all") return { denied: false };
	const denyList = permissions?.toolDenyLists?.[role] || [];
	if (denyList.length === 0) return { denied: false };
	const n = toolName.toLowerCase().replace(/[^a-z0-9_]/g, "");
	if (!denyList.some((d) => n === d || n.includes(d))) return { denied: false };
	const capability = toolToCapability(toolName);
	if (capability && hasActiveGrant(agentName, capability)) return { denied: false };
	if (hasActiveGrant(agentName, n)) return { denied: false };
	return {
		denied: true,
		reason: `Permission denied: '${role}' role cannot use '${toolName}'. Use request_elevation to request temporary access.`
	};
}
function isPathAllowed(agentName, role, targetPath) {
	const policy = permissions?.filesystemPolicy?.[role];
	if (!policy || policy.mode === "unrestricted") return true;
	const allowed = [process.env.OPENCLAW_STATE_DIR || "", ...policy.additionalAllowedPaths || []];
	for (const prefix of allowed) if (prefix && targetPath.startsWith(prefix)) return true;
	if (hasActiveGrant(agentName, "fs_unrestricted")) return true;
	return false;
}
function assessRisk(toolName, params) {
	const factors = [];
	let maxRisk = 0;
	if (RISKY_TOOLS.has(toolName.toLowerCase())) {
		maxRisk = Math.max(maxRisk, 30);
		factors.push(`Risky tool: ${toolName}`);
	}
	const allParams = JSON.stringify(params);
	for (const { pattern, risk, label } of RISKY_PATTERNS) if (pattern.test(allParams)) {
		maxRisk = Math.max(maxRisk, risk);
		factors.push(label);
	}
	let level;
	if (maxRisk >= 80) level = "critical";
	else if (maxRisk >= 60) level = "high";
	else if (maxRisk >= 30) level = "medium";
	else level = "low";
	let recommendation;
	if (level === "critical") recommendation = "human-required";
	else if (level === "high") recommendation = "king-review";
	else if (level === "medium") recommendation = "manager-review";
	else recommendation = "auto-approve";
	return {
		level,
		score: maxRisk,
		factors,
		recommendation,
		timestamp: (/* @__PURE__ */ new Date()).toISOString()
	};
}
function register(api) {
	pluginDir = dirname(api.source);
	stateDir = join(pluginDir, "state");
	if (!existsSync(stateDir)) mkdirSync(stateDir, { recursive: true });
	const pCfg = api.pluginConfig ?? {};
	auditEnabled = pCfg.auditLogEnabled !== false;
	maxGrantDuration = pCfg.maxGrantDurationMinutes || 480;
	loadPermissions();
	loadGrants();
	loadRequests();
	currentAgentName = getAgentName();
	currentAgentRole = getAgentRole(currentAgentName);
	api.logger.info?.(`permission-broker: loaded for agent=${currentAgentName} role=${currentAgentRole}`);
	try {
		watchFile(join(stateDir, "grants.json"), { interval: 2e3 }, () => {
			try {
				loadGrants();
			} catch {}
		});
		watchFile(join(stateDir, "requests.json"), { interval: 2e3 }, () => {
			try {
				loadRequests();
			} catch {}
		});
	} catch {}
	api.on("before_tool_call", async (event) => {
		const { toolName, params } = event;
		if ([
			"request_elevation",
			"approve_elevation",
			"deny_elevation",
			"check_permissions",
			"list_elevation_requests",
			"revoke_grant",
			"assess_risk"
		].includes(toolName)) return;
		loadGrants();
		const check = isToolDenied(currentAgentName, currentAgentRole, toolName);
		if (check.denied) {
			auditLog("TOOL_BLOCKED", {
				toolName,
				params,
				reason: check.reason
			});
			return {
				block: true,
				blockReason: check.reason
			};
		}
		if (RISKY_TOOLS.has(toolName.toLowerCase()) || toolToCapability(toolName) === "exec") {
			const risk = assessRisk(toolName, params);
			auditLog("RISK_ASSESSED", {
				toolName,
				risk
			});
			if (currentAgentRole === "worker" && (risk.level === "high" || risk.level === "critical")) return {
				block: true,
				blockReason: `Risk assessment BLOCKED: ${risk.level} risk (score ${risk.score}/100). Factors: ${risk.factors.join(", ")}. This requires ${risk.recommendation}. Use request_elevation with details about why this operation is safe.`
			};
			if (currentAgentRole === "manager" && risk.level === "critical") auditLog("RISK_WARNING_MANAGER", {
				toolName,
				risk
			});
		}
		if (currentAgentRole === "worker") {
			if ([
				"read",
				"write",
				"edit",
				"apply_patch",
				"cat",
				"head",
				"tail",
				"grep",
				"create",
				"mkdir"
			].includes(toolName)) {
				const targetPath = params.path || params.filePath || params.file || params.dir || params.directory || "";
				if (targetPath && !isPathAllowed(currentAgentName, currentAgentRole, targetPath)) {
					auditLog("FS_BLOCKED", {
						toolName,
						targetPath
					});
					return {
						block: true,
						blockReason: `Permission denied: worker '${currentAgentName}' can only access files within its workspace. Use request_elevation with capability 'fs_unrestricted' for broader access.`
					};
				}
			}
		}
		if (currentAgentRole === "worker" && (toolName === "sessions_send" || toolName === "message_send")) {
			const target = params.target || params.to || "";
			const manager = getManagerForAgent(currentAgentName);
			if (manager && !target.includes(manager) && !hasActiveGrant(currentAgentName, "sessions_send")) {
				auditLog("MSG_BLOCKED", {
					toolName,
					target,
					allowedManager: manager
				});
				return {
					block: true,
					blockReason: `Permission denied: worker '${currentAgentName}' can only send messages to manager '${manager}'.`
				};
			}
		}
		auditLog("TOOL_ALLOWED", { toolName });
	}, { priority: 100 });
	api.on("after_tool_call", async (event) => {
		auditLog("TOOL_COMPLETED", {
			toolName: event.toolName,
			durationMs: event.durationMs,
			error: event.error || null
		});
	});
	api.on("message_sending", async (event) => {
		if (currentAgentRole !== "worker") return;
		if (event.metadata?.broadcast) {
			auditLog("BROADCAST_BLOCKED", { to: event.to });
			return { cancel: true };
		}
	});
	api.registerTool({
		name: "assess_risk",
		description: "Assess the risk level of a command or operation before executing it. Returns risk score, factors, and recommendation.",
		parameters: {
			type: "object",
			properties: {
				command: {
					type: "string",
					description: "The command or operation to assess"
				},
				tool_name: {
					type: "string",
					description: "The tool that would execute this command (e.g., 'exec', 'bash')"
				}
			},
			required: ["command"]
		},
		execute: async (args) => {
			const risk = assessRisk(args.tool_name || "exec", {
				command: args.command,
				content: args.command
			});
			const lines = [
				`## Risk Assessment`,
				``,
				`| Property | Value |`,
				`|----------|-------|`,
				`| **Level** | ${risk.level.toUpperCase()} |`,
				`| **Score** | ${risk.score}/100 |`,
				`| **Recommendation** | ${risk.recommendation} |`,
				``
			];
			if (risk.factors.length > 0) {
				lines.push(`### Risk Factors`);
				for (const f of risk.factors) lines.push(`- ${f}`);
			} else lines.push(`No risk factors detected.`);
			return lines.join("\n");
		}
	});
	api.registerTool({
		name: "request_elevation",
		description: "Request temporary elevated permissions from your manager (or King AI if you are a manager).",
		parameters: {
			type: "object",
			properties: {
				capability: {
					type: "string",
					description: "The capability to request: exec, sessions_send, fs_unrestricted, elevated, web_search, web_fetch, broadcast",
					enum: [
						"exec",
						"sessions_send",
						"fs_unrestricted",
						"elevated",
						"web_search",
						"web_fetch",
						"broadcast"
					]
				},
				reason: {
					type: "string",
					description: "Detailed explanation of why this permission is needed"
				},
				duration_minutes: {
					type: "number",
					description: `How long the permission is needed (default: 30, max: ${maxGrantDuration})`
				}
			},
			required: ["capability", "reason"]
		},
		execute: async (args) => {
			if (currentAgentRole === "king") return "King AI has full unrestricted permissions — no elevation needed.";
			const durationMinutes = Math.min(args.duration_minutes || 30, maxGrantDuration);
			const approver = currentAgentRole === "worker" ? getManagerForAgent(currentAgentName) || "king-ai" : "king-ai";
			loadGrants();
			if (hasActiveGrant(currentAgentName, args.capability)) {
				const grant = grants.grants.find((g) => g.agentName === currentAgentName && g.capability === args.capability);
				const remaining = grant ? Math.round((grant.expiresAt - Date.now()) / 6e4) : 0;
				return `Already have '${args.capability}' permission (${remaining} minutes remaining).`;
			}
			const risk = assessRisk(args.capability, {
				reason: args.reason,
				capability: args.capability
			});
			loadRequests();
			const request = {
				id: `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
				agentName: currentAgentName,
				capability: args.capability,
				reason: args.reason,
				durationMinutes,
				requestedAt: Date.now(),
				status: "pending",
				riskAssessment: risk
			};
			requests.requests.push(request);
			saveRequests();
			auditLog("ELEVATION_REQUESTED", {
				requestId: request.id,
				capability: args.capability,
				reason: args.reason,
				approver,
				durationMinutes,
				riskAssessment: risk
			});
			const approverPort = permissions?.agentPorts?.[approver];
			if (approverPort) try {
				await fetch(`http://localhost:${approverPort}/api/v1/notify`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						type: "elevation_request",
						from: currentAgentName,
						request
					}),
					signal: AbortSignal.timeout(3e3)
				}).catch(() => {});
			} catch {}
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
				`Waiting for **${approver}** to approve.`
			].join("\n");
		}
	});
	api.registerTool({
		name: "approve_elevation",
		description: "Approve a pending elevation request. Managers approve their workers; King approves all.",
		parameters: {
			type: "object",
			properties: {
				request_id: {
					type: "string",
					description: "The request ID to approve"
				},
				duration_minutes: {
					type: "number",
					description: `Override duration (max: ${maxGrantDuration})`
				}
			},
			required: ["request_id"]
		},
		execute: async (args) => {
			if (!canAgentApprove(currentAgentName)) return `Permission denied: '${currentAgentRole}' cannot approve requests.`;
			loadRequests();
			const request = requests.requests.find((r) => r.id === args.request_id && r.status === "pending");
			if (!request) {
				const pending = requests.requests.filter((r) => r.status === "pending");
				return `Request '${args.request_id}' not found or already processed.\n\nPending:\n${pending.map((r) => `  - ${r.id}: ${r.agentName} wants '${r.capability}'`).join("\n") || "  (none)"}`;
			}
			if (!canAgentGrant(currentAgentName, request.agentName)) return `Cannot approve: '${request.agentName}' is not in your jurisdiction.`;
			if (request.riskAssessment && request.riskAssessment.level === "critical" && currentAgentRole !== "king") return `Cannot approve: request has CRITICAL risk assessment (score ${request.riskAssessment.score}/100). Factors: ${request.riskAssessment.factors.join(", ")}. This requires King AI approval. Escalate via request_elevation.`;
			const duration = Math.min(args.duration_minutes || request.durationMinutes || 30, maxGrantDuration);
			const now = Date.now();
			loadGrants();
			const grant = {
				id: `grant-${now}-${Math.random().toString(36).slice(2, 8)}`,
				agentName: request.agentName,
				capability: request.capability,
				grantedBy: currentAgentName,
				grantedAt: now,
				expiresAt: now + duration * 60 * 1e3,
				reason: request.reason
			};
			grants.grants.push(grant);
			saveGrants();
			request.status = "approved";
			request.decidedBy = currentAgentName;
			request.decidedAt = now;
			saveRequests();
			auditLog("ELEVATION_APPROVED", {
				requestId: args.request_id,
				grantId: grant.id,
				agent: request.agentName,
				capability: request.capability,
				duration
			});
			return [
				`## Elevation Approved`,
				``,
				`| Field | Value |`,
				`|-------|-------|`,
				`| **Grant ID** | ${grant.id} |`,
				`| **Agent** | ${request.agentName} |`,
				`| **Capability** | ${request.capability} |`,
				`| **Duration** | ${duration} minutes |`,
				`| **Expires** | ${new Date(grant.expiresAt).toISOString()} |`
			].join("\n");
		}
	});
	api.registerTool({
		name: "deny_elevation",
		description: "Deny a pending elevation request with a reason.",
		parameters: {
			type: "object",
			properties: {
				request_id: {
					type: "string",
					description: "Request ID to deny"
				},
				reason: {
					type: "string",
					description: "Reason for denial"
				}
			},
			required: ["request_id", "reason"]
		},
		execute: async (args) => {
			if (!canAgentApprove(currentAgentName)) return "Permission denied: only managers and King AI can deny requests.";
			loadRequests();
			const request = requests.requests.find((r) => r.id === args.request_id && r.status === "pending");
			if (!request) return `Request '${args.request_id}' not found or already processed.`;
			request.status = "denied";
			request.decidedBy = currentAgentName;
			request.decidedAt = Date.now();
			request.denyReason = args.reason;
			saveRequests();
			auditLog("ELEVATION_DENIED", {
				requestId: args.request_id,
				agent: request.agentName,
				capability: request.capability,
				reason: args.reason
			});
			return `Denied '${args.request_id}' from '${request.agentName}' for '${request.capability}'. Reason: ${args.reason}`;
		}
	});
	api.registerTool({
		name: "revoke_grant",
		description: "Revoke an active grant immediately.",
		parameters: {
			type: "object",
			properties: { grant_id: {
				type: "string",
				description: "Grant ID to revoke"
			} },
			required: ["grant_id"]
		},
		execute: async (args) => {
			if (!canAgentApprove(currentAgentName)) return "Permission denied: only managers and King AI can revoke.";
			loadGrants();
			const idx = grants.grants.findIndex((g) => g.id === args.grant_id);
			if (idx === -1) return `Grant '${args.grant_id}' not found or expired.`;
			const grant = grants.grants[idx];
			if (currentAgentRole === "manager" && grant.grantedBy !== currentAgentName && !isManagerOf(currentAgentName, grant.agentName)) return `Cannot revoke: not your grant and '${grant.agentName}' is not your worker.`;
			grants.grants.splice(idx, 1);
			saveGrants();
			auditLog("GRANT_REVOKED", {
				grantId: args.grant_id,
				agent: grant.agentName,
				capability: grant.capability
			});
			return `Revoked: '${grant.agentName}' no longer has '${grant.capability}'.`;
		}
	});
	api.registerTool({
		name: "check_permissions",
		description: "Check current permissions, active grants, and pending requests for self or another agent.",
		parameters: {
			type: "object",
			properties: { agent_name: {
				type: "string",
				description: "Optional: check another agent (managers/King only)"
			} }
		},
		execute: async (args) => {
			const targetName = args.agent_name || currentAgentName;
			if (targetName !== currentAgentName && currentAgentRole === "worker") return "Permission denied: workers can only check their own permissions.";
			loadGrants();
			loadRequests();
			const role = getAgentRole(targetName);
			const denyList = permissions?.toolDenyLists?.[role] || [];
			const activeGrants = grants.grants.filter((g) => g.agentName === targetName && g.expiresAt > Date.now());
			const pendingReqs = requests.requests.filter((r) => r.agentName === targetName && r.status === "pending");
			const manager = getManagerForAgent(targetName);
			const lines = [
				`## Permissions: ${targetName}`,
				"",
				`| Property | Value |`,
				`|----------|-------|`,
				`| **Role** | ${role} |`,
				`| **Manager** | ${manager || "(top level)"} |`,
				""
			];
			if (denyList.length > 0) {
				lines.push("### Denied Capabilities");
				for (const cap of denyList) {
					const granted = activeGrants.find((g) => g.capability === cap);
					if (granted) {
						const rem = Math.round((granted.expiresAt - Date.now()) / 6e4);
						lines.push(`- ~~${cap}~~ → **GRANTED** (${rem}m left, by ${granted.grantedBy})`);
					} else lines.push(`- **${cap}** → BLOCKED`);
				}
				lines.push("");
			}
			if (activeGrants.length > 0) {
				lines.push(`### Active Grants (${activeGrants.length})`);
				for (const g of activeGrants) {
					const rem = Math.round((g.expiresAt - Date.now()) / 6e4);
					lines.push(`- ${g.id}: **${g.capability}** — ${rem}m left`);
				}
				lines.push("");
			}
			if (pendingReqs.length > 0) {
				lines.push(`### Pending Requests (${pendingReqs.length})`);
				for (const r of pendingReqs) {
					const age = Math.round((Date.now() - r.requestedAt) / 6e4);
					lines.push(`- ${r.id}: **${r.capability}** — ${age}m ago — ${r.reason}`);
				}
			}
			return lines.join("\n");
		}
	});
	api.registerTool({
		name: "list_elevation_requests",
		description: "List pending elevation requests you can approve/deny.",
		parameters: {
			type: "object",
			properties: { status: {
				type: "string",
				enum: [
					"pending",
					"approved",
					"denied",
					"all"
				],
				description: "Filter by status (default: pending)"
			} }
		},
		execute: async (args) => {
			if (!canAgentApprove(currentAgentName)) return "Permission denied: only managers and King AI can list requests.";
			loadRequests();
			const statusFilter = args.status || "pending";
			let filtered = requests.requests;
			if (statusFilter !== "all") filtered = filtered.filter((r) => r.status === statusFilter);
			if (currentAgentRole === "manager") {
				const pool = permissions?.agents?.[currentAgentName]?.pool || [];
				filtered = filtered.filter((r) => pool.includes(r.agentName));
			}
			if (filtered.length === 0) return `No ${statusFilter} requests.`;
			const lines = [`## Elevation Requests (${statusFilter})`, ""];
			for (const r of filtered) {
				const age = Math.round((Date.now() - r.requestedAt) / 6e4);
				lines.push(`### ${r.id}`);
				lines.push(`| Field | Value |`);
				lines.push(`|-------|-------|`);
				lines.push(`| **Agent** | ${r.agentName} |`);
				lines.push(`| **Capability** | ${r.capability} |`);
				lines.push(`| **Reason** | ${r.reason} |`);
				lines.push(`| **Duration** | ${r.durationMinutes}m |`);
				lines.push(`| **Requested** | ${age}m ago |`);
				if (r.riskAssessment) lines.push(`| **Risk** | ${r.riskAssessment.level.toUpperCase()} (${r.riskAssessment.score}/100) |`);
				lines.push(`| **Status** | ${r.status} |`);
				if (r.status === "pending") {
					lines.push("");
					lines.push(`→ approve_elevation request_id="${r.id}"`);
					lines.push(`→ deny_elevation request_id="${r.id}" reason="..."`);
				}
				lines.push("");
			}
			return lines.join("\n");
		}
	});
	auditLog("PLUGIN_LOADED", {
		role: currentAgentRole,
		denyList: permissions?.toolDenyLists?.[currentAgentRole] || []
	});
}
//#endregion
export { register as default };
