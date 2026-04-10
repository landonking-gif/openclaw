import { c as loadConfig } from "./io-CHHRUM9X.js";
import "./config-B3X9mknZ.js";
import { t as loadChannelOutboundAdapter } from "./load-Qd8Sud8M.js";
//#region src/cli/send-runtime/imessage.ts
const runtimeSend = { sendMessage: async (to, text, opts = {}) => {
	const outbound = await loadChannelOutboundAdapter("imessage");
	if (!outbound?.sendText) throw new Error("iMessage outbound adapter is unavailable.");
	return await outbound.sendText({
		cfg: opts.config ?? loadConfig(),
		to,
		text,
		mediaUrl: opts.mediaUrl,
		mediaLocalRoots: opts.mediaLocalRoots,
		accountId: opts.accountId,
		replyToId: opts.replyToId
	});
} };
//#endregion
export { runtimeSend };
