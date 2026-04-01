import { t as hasControlCommand } from "./command-detection-Cv1SSnoN.js";
import { n as resolveInboundDebounceMs, t as createInboundDebouncer } from "./inbound-debounce-D23i2H8K.js";
import "./mentions-CKo0BqYA.js";
import "./direct-dm-BO6pMN7j.js";
import "./session-envelope-BQdZf0Rn.js";
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
