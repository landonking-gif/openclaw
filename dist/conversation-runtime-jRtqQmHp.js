import { u as resolveAgentIdFromSessionKey } from "./session-key-4QR94Oth.js";
import "./pairing-store-CGyjsUKG.js";
import "./session-binding-service-Be6fDk2D.js";
import "./conversation-binding-C-7uP0Wn.js";
import { n as deriveLastRoutePolicy } from "./resolve-route-BmwWWdj5.js";
import "./session-BZIY3yKW.js";
import { n as resolveConfiguredBinding } from "./binding-registry-DdY9fQW7.js";
import "./dm-policy-shared-DPpYfcGE.js";
import { t as ensureConfiguredBindingTargetReady } from "./binding-targets-DxJ6e-7a.js";
import "./pairing-labels-bvC1YaDR.js";
//#region src/channels/plugins/binding-routing.ts
function resolveConfiguredBindingConversationRef(params) {
	if ("conversation" in params) return params.conversation;
	return {
		channel: params.channel,
		accountId: params.accountId,
		conversationId: params.conversationId,
		parentConversationId: params.parentConversationId
	};
}
function resolveConfiguredBindingRoute(params) {
	const bindingResolution = resolveConfiguredBinding({
		cfg: params.cfg,
		conversation: resolveConfiguredBindingConversationRef(params)
	}) ?? null;
	if (!bindingResolution) return {
		bindingResolution: null,
		route: params.route
	};
	const boundSessionKey = bindingResolution.statefulTarget.sessionKey.trim();
	if (!boundSessionKey) return {
		bindingResolution,
		route: params.route
	};
	const boundAgentId = resolveAgentIdFromSessionKey(boundSessionKey) || bindingResolution.statefulTarget.agentId;
	return {
		bindingResolution,
		boundSessionKey,
		boundAgentId,
		route: {
			...params.route,
			sessionKey: boundSessionKey,
			agentId: boundAgentId,
			lastRoutePolicy: deriveLastRoutePolicy({
				sessionKey: boundSessionKey,
				mainSessionKey: params.route.mainSessionKey
			}),
			matchedBy: "binding.channel"
		}
	};
}
async function ensureConfiguredBindingRouteReady(params) {
	return await ensureConfiguredBindingTargetReady(params);
}
//#endregion
//#region src/channels/session-meta.ts
let inboundSessionRuntimePromise = null;
function loadInboundSessionRuntime() {
	inboundSessionRuntimePromise ??= import("./inbound.runtime-CS0Vm9SJ.js");
	return inboundSessionRuntimePromise;
}
async function recordInboundSessionMetaSafe(params) {
	const runtime = await loadInboundSessionRuntime();
	const storePath = runtime.resolveStorePath(params.cfg.session?.store, { agentId: params.agentId });
	try {
		await runtime.recordSessionMetaFromInbound({
			storePath,
			sessionKey: params.sessionKey,
			ctx: params.ctx
		});
	} catch (err) {
		params.onError?.(err);
	}
}
//#endregion
//#region src/channels/thread-binding-id.ts
function resolveThreadBindingConversationIdFromBindingId(params) {
	const bindingId = params.bindingId?.trim();
	if (!bindingId) return;
	const prefix = `${params.accountId}:`;
	if (!bindingId.startsWith(prefix)) return;
	return bindingId.slice(prefix.length).trim() || void 0;
}
//#endregion
export { resolveConfiguredBindingRoute as i, recordInboundSessionMetaSafe as n, ensureConfiguredBindingRouteReady as r, resolveThreadBindingConversationIdFromBindingId as t };
