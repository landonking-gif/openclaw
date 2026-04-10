import { t as hasControlCommand } from "./command-detection-B6HG7hjh.js";
import { n as resolveInboundDebounceMs, t as createInboundDebouncer } from "./inbound-debounce-B4rdabE3.js";
import "./mentions-BxianbEx.js";
import "./direct-dm-DB_czfqF.js";
import "./session-envelope-CwqrxyiL.js";
//#region src/channels/inbound-debounce-policy.ts
function shouldDebounceTextInbound(params) {
	if (params.allowDebounce === false) return false;
	if (params.hasMedia) return false;
	const text = params.text?.trim() ?? "";
	if (!text) return false;
	return !hasControlCommand(text, params.cfg, params.commandOptions);
}
function createChannelInboundDebouncer(params) {
	const debounceMs = resolveInboundDebounceMs({
		cfg: params.cfg,
		channel: params.channel,
		overrideMs: params.debounceMsOverride
	});
	const { cfg: _cfg, channel: _channel, debounceMsOverride: _override, ...rest } = params;
	return {
		debounceMs,
		debouncer: createInboundDebouncer({
			debounceMs,
			...rest
		})
	};
}
//#endregion
export { shouldDebounceTextInbound as n, createChannelInboundDebouncer as t };
