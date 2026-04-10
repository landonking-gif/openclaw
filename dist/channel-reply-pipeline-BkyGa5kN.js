import { r as createReplyPrefixOptions, t as createTypingCallbacks } from "./typing-C0wBbHXZ.js";
//#region src/plugin-sdk/channel-reply-pipeline.ts
function createChannelReplyPipeline(params) {
	return {
		...createReplyPrefixOptions({
			cfg: params.cfg,
			agentId: params.agentId,
			channel: params.channel,
			accountId: params.accountId
		}),
		...params.typingCallbacks ? { typingCallbacks: params.typingCallbacks } : params.typing ? { typingCallbacks: createTypingCallbacks(params.typing) } : {}
	};
}
//#endregion
export { createChannelReplyPipeline as t };
