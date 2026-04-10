import { n as assertWebChannel, p as normalizeE164, w as toWhatsappJid } from "./utils-ozuUQtXc.js";
import { c as loadConfig } from "./io-CHHRUM9X.js";
import "./config-B3X9mknZ.js";
import { i as loadSessionStore, l as saveSessionStore } from "./store-1GMpznZw.js";
import { l as resolveStorePath } from "./paths-BC0JJAKv.js";
import { n as resolveSessionKey, t as deriveSessionKey } from "./session-key-DowUUVMo.js";
import { i as handlePortError, n as describePortOwner, r as ensurePortAvailable, t as PortInUseError } from "./ports-aadA2H0l.js";
import { t as applyTemplate } from "./templating-CTmzydlr.js";
import { t as createDefaultDeps } from "./deps-B7KqEBBz.js";
import { t as waitForever } from "./wait-1t8rTr6d.js";
//#region src/library.ts
let replyRuntimePromise = null;
let promptRuntimePromise = null;
let binariesRuntimePromise = null;
let execRuntimePromise = null;
let whatsappRuntimePromise = null;
function loadReplyRuntime() {
	replyRuntimePromise ??= import("./reply.runtime-C-D0LyzT.js");
	return replyRuntimePromise;
}
function loadPromptRuntime() {
	promptRuntimePromise ??= import("./prompt-DrxuynGM.js");
	return promptRuntimePromise;
}
function loadBinariesRuntime() {
	binariesRuntimePromise ??= import("./binaries-D-gsw6Ia.js");
	return binariesRuntimePromise;
}
function loadExecRuntime() {
	execRuntimePromise ??= import("./exec-lupwnbbV.js");
	return execRuntimePromise;
}
function loadWhatsAppRuntime() {
	whatsappRuntimePromise ??= import("./runtime-whatsapp-boundary-BfneIBvl.js");
	return whatsappRuntimePromise;
}
const getReplyFromConfig = async (...args) => (await loadReplyRuntime()).getReplyFromConfig(...args);
const promptYesNo = async (...args) => (await loadPromptRuntime()).promptYesNo(...args);
const ensureBinary = async (...args) => (await loadBinariesRuntime()).ensureBinary(...args);
const runExec = async (...args) => (await loadExecRuntime()).runExec(...args);
const runCommandWithTimeout = async (...args) => (await loadExecRuntime()).runCommandWithTimeout(...args);
const monitorWebChannel = async (...args) => (await loadWhatsAppRuntime()).monitorWebChannel(...args);
//#endregion
export { PortInUseError, applyTemplate, assertWebChannel, createDefaultDeps, deriveSessionKey, describePortOwner, ensureBinary, ensurePortAvailable, getReplyFromConfig, handlePortError, loadConfig, loadSessionStore, monitorWebChannel, normalizeE164, promptYesNo, resolveSessionKey, resolveStorePath, runCommandWithTimeout, runExec, saveSessionStore, toWhatsappJid, waitForever };
