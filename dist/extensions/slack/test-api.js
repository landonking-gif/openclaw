import { o as sendMessageSlack } from "../../reply-blocks-8x28WweT.js";
import { i as createSlackActions, n as setSlackRuntime, r as slackOutbound, t as slackPlugin } from "../../channel-3A6qw5rF.js";
import { s as createSlackMonitorContext, t as prepareSlackMessage } from "../../prepare-BX2P9kUy.js";
//#region extensions/slack/src/monitor/message-handler/prepare.test-helpers.ts
function createInboundSlackTestContext(params) {
	return createSlackMonitorContext({
		cfg: params.cfg,
		accountId: "default",
		botToken: "token",
		app: { client: params.appClient ?? {} },
		runtime: {},
		botUserId: "B1",
		teamId: "T1",
		apiAppId: "A1",
		historyLimit: 0,
		sessionScope: "per-sender",
		mainKey: "main",
		dmEnabled: true,
		dmPolicy: "open",
		allowFrom: [],
		allowNameMatching: false,
		groupDmEnabled: true,
		groupDmChannels: [],
		defaultRequireMention: params.defaultRequireMention ?? true,
		channelsConfig: params.channelsConfig,
		groupPolicy: "open",
		useAccessGroups: false,
		reactionMode: "off",
		reactionAllowlist: [],
		replyToMode: params.replyToMode ?? "off",
		threadHistoryScope: "thread",
		threadInheritParent: false,
		slashCommand: {
			enabled: false,
			name: "openclaw",
			sessionPrefix: "slack:slash",
			ephemeral: true
		},
		textLimit: 4e3,
		ackReactionScope: "group-mentions",
		typingReaction: "",
		mediaMaxBytes: 1024,
		removeAckAfterReply: false
	});
}
//#endregion
export { createInboundSlackTestContext, createSlackActions, prepareSlackMessage, sendMessageSlack, setSlackRuntime, slackOutbound, slackPlugin };
