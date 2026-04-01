import "./message-channel-ChfElmW5.js";
import "./bindings-BfSMa75q.js";
import "./resolve-route-BmwWWdj5.js";
import "./base-session-key-kQVo8bkB.js";
//#region src/infra/outbound/thread-id.ts
function normalizeOutboundThreadId(value) {
	if (value == null) return;
	if (typeof value === "number") {
		if (!Number.isFinite(value)) return;
		return String(Math.trunc(value));
	}
	const trimmed = value.trim();
	return trimmed ? trimmed : void 0;
}
//#endregion
export { normalizeOutboundThreadId as t };
