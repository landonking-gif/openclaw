import { n as DEFAULT_MODEL, r as DEFAULT_PROVIDER } from "./defaults-BwiMD7ye.js";
import { a as resolveAgentDir, p as resolveAgentWorkspaceDir } from "./agent-scope-jbts6oCz.js";
import { d as ensureAgentWorkspace } from "./workspace-BUc4RCkE.js";
import { S as resolveThinkingDefault } from "./model-selection-D90MGDui.js";
import { i as loadSessionStore, l as saveSessionStore } from "./store-1GMpznZw.js";
import "./sessions-BHlzEkJZ.js";
import { l as resolveStorePath, r as resolveSessionFilePath } from "./paths-BC0JJAKv.js";
import { n as resolveAgentIdentity } from "./identity-xhqJmrDg.js";
import { t as runEmbeddedPiAgent } from "./pi-embedded-Hk8nEay3.js";
import { n as resolveAgentTimeoutMs } from "./content-blocks-D3E1sFJ7.js";
//#region src/extensionAPI.ts
if (process.env.VITEST !== "true" && process.env.OPENCLAW_SUPPRESS_EXTENSION_API_WARNING !== "1") process.emitWarning("openclaw/extension-api is deprecated. Migrate to api.runtime.agent.* or focused openclaw/plugin-sdk/<subpath> imports. See https://docs.openclaw.ai/plugins/sdk-migration", {
	code: "OPENCLAW_EXTENSION_API_DEPRECATED",
	detail: "This compatibility bridge is temporary. Bundled plugins should use the injected plugin runtime instead of importing host-side agent helpers directly. Migration guide: https://docs.openclaw.ai/plugins/sdk-migration"
});
//#endregion
export { DEFAULT_MODEL, DEFAULT_PROVIDER, ensureAgentWorkspace, loadSessionStore, resolveAgentDir, resolveAgentIdentity, resolveAgentTimeoutMs, resolveAgentWorkspaceDir, resolveSessionFilePath, resolveStorePath, resolveThinkingDefault, runEmbeddedPiAgent, saveSessionStore };
