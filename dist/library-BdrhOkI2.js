import { n as assertWebChannel, p as normalizeE164, w as toWhatsappJid } from "./utils-ozuUQtXc.js";
import { c as loadConfig } from "./io-D4TfzS5d.js";
import "./config-XFKRjuRh.js";
import { i as loadSessionStore, l as saveSessionStore } from "./store-Cs-WFRag.js";
import { l as resolveStorePath } from "./paths-sf4ch2Nw.js";
import { n as resolveSessionKey, t as deriveSessionKey } from "./session-key-C2EnQbn1.js";
import { i as handlePortError, n as describePortOwner, r as ensurePortAvailable, t as PortInUseError } from "./ports-DAmuSUhy.js";
import { t as applyTemplate } from "./templating-COPCaPgV.js";
import { t as createDefaultDeps } from "./deps-Dna2WkmV.js";
import { t as waitForever } from "./wait-DL4VA3Kd.js";
//#region src/library.ts
let replyRuntimePromise = null;
let promptRuntimePromise = null;
let binariesRuntimePromise = null;
let execRuntimePromise = null;
let whatsappRuntimePromise = null;
function loadReplyRuntime() {
	replyRuntimePromise ??= import("./reply.runtime-Cf9GmMsP.js");
	return replyRuntimePromise;
}
function loadPromptRuntime() {
	promptRuntimePromise ??= import("./prompt-DklKo6o_.js");
	return promptRuntimePromise;
}
function loadBinariesRuntime() {
	binariesRuntimePromise ??= import("./binaries-CjUO_dXI.js");
	return binariesRuntimePromise;
}
function loadExecRuntime() {
	execRuntimePromise ??= import("./exec-lupwnbbV.js");
	return execRuntimePromise;
}
function loadWhatsAppRuntime() {
	whatsappRuntimePromise ??= import("./runtime-whatsapp-boundary-S6f0zqLg.js");
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
