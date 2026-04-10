import { a as shouldLogVerbose } from "../../globals-DhgSPxVV.js";
import { t as resolveOutboundSendDep } from "../../send-deps-BWJXv6mY.js";
import { a as createEmptyChannelResult, i as createAttachedChannelResultAdapter } from "../../channel-send-result-DX0z68oP.js";
import { b as sendTextMediaPayload, p as resolveSendableOutboundReplyParts } from "../../reply-payload-CJVpH0Ce.js";
import "../../runtime-env-qZTXn_g8.js";
import { a as chunkText } from "../../chunk-DsMUguiY.js";
import "../../reply-runtime-Ds_SHc8s.js";
import "../../outbound-runtime-B81rFdEK.js";
import { r as resolveWhatsAppOutboundTarget } from "../../runtime-api-DRi8kZYv2.js";
import { n as sendPollWhatsApp } from "../../send-B0wY5mp-.js";
import { n as setWhatsAppRuntime, t as whatsappPlugin } from "../../channel-DNRHYcG8.js";
import { a as updateLastRouteInBackground, i as trackBackgroundTask, t as deliverWebReply } from "../../deliver-reply-be0CD13c.js";
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
			return await (resolveOutboundSendDep(deps, "whatsapp") ?? (await import("../../send-TVMpv53u.js")).sendMessageWhatsApp)(to, normalizedText, {
				verbose: false,
				cfg,
				accountId: accountId ?? void 0,
				gifPlayback
			});
		},
		sendMedia: async ({ cfg, to, text, mediaUrl, mediaLocalRoots, mediaReadFile, accountId, deps, gifPlayback }) => {
			const normalizedText = trimLeadingWhitespace(text);
			return await (resolveOutboundSendDep(deps, "whatsapp") ?? (await import("../../send-TVMpv53u.js")).sendMessageWhatsApp)(to, normalizedText, {
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
