import { a as shouldLogVerbose } from "../../globals-DhgSPxVV.js";
import { t as resolveOutboundSendDep } from "../../send-deps-DrkAylXF.js";
import { a as createEmptyChannelResult, i as createAttachedChannelResultAdapter } from "../../channel-send-result-BxSrHwD5.js";
import { b as sendTextMediaPayload, p as resolveSendableOutboundReplyParts } from "../../reply-payload-DFX4yBqp.js";
import "../../runtime-env-Cv7gkvxy.js";
import { a as chunkText } from "../../chunk-Dvt-i5un.js";
import "../../reply-runtime-CZ-vIRHF.js";
import "../../outbound-runtime-CdBArdFa.js";
import { r as resolveWhatsAppOutboundTarget } from "../../runtime-api-CFuFc8eL.js";
import { n as sendPollWhatsApp } from "../../send-Bp5b_vqy.js";
import { n as setWhatsAppRuntime, t as whatsappPlugin } from "../../channel-C2R_gQTx.js";
import { a as updateLastRouteInBackground, i as trackBackgroundTask, t as deliverWebReply } from "../../deliver-reply-D0klnfJW.js";
//#region extensions/whatsapp/src/outbound-adapter.ts
function trimLeadingWhitespace(text) {
	return text?.trimStart() ?? "";
}
const whatsappOutbound = {
	deliveryMode: "gateway",
	chunker: chunkText,
	chunkerMode: "text",
	textChunkLimit: 4e3,
	pollMaxOptions: 12,
	resolveTarget: ({ to, allowFrom, mode }) => resolveWhatsAppOutboundTarget({
		to,
		allowFrom,
		mode
	}),
	sendPayload: async (ctx) => {
		const text = trimLeadingWhitespace(ctx.payload.text);
		const hasMedia = resolveSendableOutboundReplyParts(ctx.payload).hasMedia;
		if (!text && !hasMedia) return createEmptyChannelResult("whatsapp");
		return await sendTextMediaPayload({
			channel: "whatsapp",
			ctx: {
				...ctx,
				payload: {
					...ctx.payload,
					text
				}
			},
			adapter: whatsappOutbound
		});
	},
	...createAttachedChannelResultAdapter({
		channel: "whatsapp",
		sendText: async ({ cfg, to, text, accountId, deps, gifPlayback }) => {
			const normalizedText = trimLeadingWhitespace(text);
			if (!normalizedText) return createEmptyChannelResult("whatsapp");
			return await (resolveOutboundSendDep(deps, "whatsapp") ?? (await import("../../send-CdFah5nh.js")).sendMessageWhatsApp)(to, normalizedText, {
				verbose: false,
				cfg,
				accountId: accountId ?? void 0,
				gifPlayback
			});
		},
		sendMedia: async ({ cfg, to, text, mediaUrl, mediaLocalRoots, mediaReadFile, accountId, deps, gifPlayback }) => {
			const normalizedText = trimLeadingWhitespace(text);
			return await (resolveOutboundSendDep(deps, "whatsapp") ?? (await import("../../send-CdFah5nh.js")).sendMessageWhatsApp)(to, normalizedText, {
				verbose: false,
				cfg,
				mediaUrl,
				mediaLocalRoots,
				mediaReadFile,
				accountId: accountId ?? void 0,
				gifPlayback
			});
		},
		sendPoll: async ({ cfg, to, poll, accountId }) => await sendPollWhatsApp(to, poll, {
			verbose: shouldLogVerbose(),
			accountId: accountId ?? void 0,
			cfg
		})
	})
};
//#endregion
export { deliverWebReply, setWhatsAppRuntime, trackBackgroundTask, updateLastRouteInBackground, whatsappOutbound, whatsappPlugin };
