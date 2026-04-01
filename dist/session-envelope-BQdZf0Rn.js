import { o as readSessionUpdatedAt } from "./store-Cs-WFRag.js";
import "./sessions-B4aC8Aau.js";
import { l as resolveStorePath } from "./paths-sf4ch2Nw.js";
import { a as resolveEnvelopeFormatOptions } from "./envelope-C6ShMImc.js";
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
