import { n as resolveGlobalSingleton } from "./global-singleton-BuWJMSMa.js";
import { c as registerListener, s as notifyListeners } from "./heartbeat-visibility-y99mIlg-.js";
//#region src/infra/agent-events.ts
const AGENT_EVENT_STATE_KEY = Symbol.for("openclaw.agentEvents.state");
function getAgentEventState() {
	return resolveGlobalSingleton(AGENT_EVENT_STATE_KEY, () => ({
		seqByRun: /* @__PURE__ */ new Map(),
		listeners: /* @__PURE__ */ new Set(),
		runContextById: /* @__PURE__ */ new Map()
	}));
}
function registerAgentRunContext(runId, context) {
	if (!runId) return;
	const state = getAgentEventState();
	const existing = state.runContextById.get(runId);
	if (!existing) {
		state.runContextById.set(runId, { ...context });
		return;
	}
	if (context.sessionKey && existing.sessionKey !== context.sessionKey) existing.sessionKey = context.sessionKey;
	if (context.verboseLevel && existing.verboseLevel !== context.verboseLevel) existing.verboseLevel = context.verboseLevel;
	if (context.isControlUiVisible !== void 0) existing.isControlUiVisible = context.isControlUiVisible;
	if (context.isHeartbeat !== void 0 && existing.isHeartbeat !== context.isHeartbeat) existing.isHeartbeat = context.isHeartbeat;
}
function getAgentRunContext(runId) {
	return getAgentEventState().runContextById.get(runId);
}
function clearAgentRunContext(runId) {
	getAgentEventState().runContextById.delete(runId);
}
function emitAgentEvent(event) {
	const state = getAgentEventState();
	const nextSeq = (state.seqByRun.get(event.runId) ?? 0) + 1;
	state.seqByRun.set(event.runId, nextSeq);
	const context = state.runContextById.get(event.runId);
	const isControlUiVisible = context?.isControlUiVisible ?? true;
	const eventSessionKey = typeof event.sessionKey === "string" && event.sessionKey.trim() ? event.sessionKey : void 0;
	const sessionKey = isControlUiVisible ? eventSessionKey ?? context?.sessionKey : void 0;
	const enriched = {
		...event,
		sessionKey,
		seq: nextSeq,
		ts: Date.now()
	};
	notifyListeners(state.listeners, enriched);
}
function onAgentEvent(listener) {
	return registerListener(getAgentEventState().listeners, listener);
}
//#endregion
export { registerAgentRunContext as a, onAgentEvent as i, emitAgentEvent as n, getAgentRunContext as r, clearAgentRunContext as t };
