import { n as DEFAULT_MODEL, r as DEFAULT_PROVIDER } from "./defaults-BwiMD7ye.js";
import { a as resolveAgentDir, p as resolveAgentWorkspaceDir } from "./agent-scope-jbts6oCz.js";
import { d as ensureAgentWorkspace } from "./workspace-BUc4RCkE.js";
import { S as resolveThinkingDefault } from "./model-selection-D90MGDui.js";
import { i as loadSessionStore, l as saveSessionStore } from "./store-Cs-WFRag.js";
import "./sessions-B4aC8Aau.js";
import { l as resolveStorePath, r as resolveSessionFilePath } from "./paths-sf4ch2Nw.js";
import { n as resolveAgentIdentity } from "./identity-BHQcyOKA.js";
import { t as runEmbeddedPiAgent } from "./pi-embedded-DrlfOZ8s.js";
import { n as resolveAgentTimeoutMs } from "./content-blocks-tjcQEIr2.js";
//#region src/extensionAPI.ts
if (process.env.VITEST !== "true" && process.env.OPENCLAW_SUPPRESS_EXTENSION_API_WARNING !== "1") process.emitWarning("openclaw/extension-api is deprecated. Migrate to api.runtime.agent.* or focused openclaw/plugin-sdk/<subpath> imports. See https://docs.openclaw.ai/plugins/sdk-migration", {
	code: "OPENCLAW_EXTENSION_API_DEPRECATED",
	detail: "This compatibility bridge is temporary. Bundled plugins should use the injected plugin runtime instead of importing host-side agent helpers directly. Migration guide: https://docs.openclaw.ai/plugins/sdk-migration"
});
//#endregion
export { DEFAULT_MODEL, DEFAULT_PROVIDER, ensureAgentWorkspace, loadSessionStore, resolveAgentDir, resolveAgentIdentity, resolveAgentTimeoutMs, resolveAgentWorkspaceDir, resolveSessionFilePath, resolveStorePath, resolveThinkingDefault, runEmbeddedPiAgent, saveSessionStore };
