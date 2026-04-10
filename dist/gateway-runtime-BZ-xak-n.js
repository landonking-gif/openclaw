import "./method-scopes-DOxx6FV1.js";
import "./operator-approvals-client-jXzo5gTe.js";
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
