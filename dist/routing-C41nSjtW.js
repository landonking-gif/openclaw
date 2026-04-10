import "./message-channel-Bk-oI2vE.js";
import "./bindings-BJgxRdGK.js";
import "./resolve-route-Dm396btS.js";
import "./base-session-key-Cd49jftS.js";
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
