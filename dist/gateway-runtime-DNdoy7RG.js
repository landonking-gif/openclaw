import "./method-scopes-ByMTuU41.js";
import "./operator-approvals-client-2rrv0NIn.js";
//#region src/gateway/channel-status-patches.ts
function createConnectedChannelStatusPatch(at = Date.now()) {
	return {
		connected: true,
		lastConnectedAt: at,
		lastEventAt: at
	};
}
//#endregion
export { createConnectedChannelStatusPatch as t };
