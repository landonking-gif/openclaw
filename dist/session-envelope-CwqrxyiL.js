import { o as readSessionUpdatedAt } from "./store-1GMpznZw.js";
import "./sessions-BHlzEkJZ.js";
import { l as resolveStorePath } from "./paths-BC0JJAKv.js";
import { a as resolveEnvelopeFormatOptions } from "./envelope-DNDo43dW.js";
//#region src/channels/session-envelope.ts
function resolveInboundSessionEnvelopeContext(params) {
	const storePath = resolveStorePath(params.cfg.session?.store, { agentId: params.agentId });
	return {
		storePath,
		envelopeOptions: resolveEnvelopeFormatOptions(params.cfg),
		previousTimestamp: readSessionUpdatedAt({
			storePath,
			sessionKey: params.sessionKey
		})
	};
}
//#endregion
export { resolveInboundSessionEnvelopeContext as t };
