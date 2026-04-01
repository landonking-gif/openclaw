import { a as probeSlack, c as sendMessageSlack, i as monitorSlackProvider, n as listSlackDirectoryGroupsLive, o as resolveSlackChannelAllowlist, r as listSlackDirectoryPeersLive, s as resolveSlackUserAllowlist, t as handleSlackAction } from "./slack-runtime-surface-CC5njJtr.js";
import "./slack-BgEG-JXj.js";
//#region src/plugins/runtime/runtime-slack-ops.runtime.ts
const runtimeSlackOps = {
	listDirectoryGroupsLive: listSlackDirectoryGroupsLive,
	listDirectoryPeersLive: listSlackDirectoryPeersLive,
	probeSlack,
	resolveChannelAllowlist: resolveSlackChannelAllowlist,
	resolveUserAllowlist: resolveSlackUserAllowlist,
	sendMessageSlack,
	monitorSlackProvider,
	handleSlackAction
};
//#endregion
export { runtimeSlackOps };
