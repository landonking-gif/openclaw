import { t as getChatChannelMeta } from "../../chat-meta-vnJDD9J6.js";
import { n as createApproverRestrictedNativeApprovalAdapter } from "../../approval-runtime-BxXp_f2n.js";
import { n as buildDmGroupAccountAllowlistAdapter } from "../../allowlist-config-edit-gP6F_9gi.js";
import "../../telegram-core-D76sgmbe.js";
import { r as listTelegramAccountIds, s as resolveTelegramAccount } from "../../accounts-B0QkT0Pt.js";
import { i as isTelegramExecApprovalClientEnabled, n as isTelegramExecApprovalApprover, r as isTelegramExecApprovalAuthorizedSender, s as resolveTelegramExecApprovalTarget, t as getTelegramExecApprovalApprovers } from "../../exec-approvals-Cd3HMwip.js";
import { i as telegramConfigAdapter } from "../../shared-DB1p37D7.js";
//#region extensions/telegram/test-support.ts
const telegramNativeApprovalAdapter = createApproverRestrictedNativeApprovalAdapter({
	channel: "telegram",
	channelLabel: "Telegram",
	listAccountIds: listTelegramAccountIds,
	hasApprovers: ({ cfg, accountId }) => getTelegramExecApprovalApprovers({
		cfg,
		accountId
	}).length > 0,
	isExecAuthorizedSender: ({ cfg, accountId, senderId }) => isTelegramExecApprovalAuthorizedSender({
		cfg,
		accountId,
		senderId
	}),
	isPluginAuthorizedSender: ({ cfg, accountId, senderId }) => isTelegramExecApprovalApprover({
		cfg,
		accountId,
		senderId
	}),
	isNativeDeliveryEnabled: ({ cfg, accountId }) => isTelegramExecApprovalClientEnabled({
		cfg,
		accountId
	}),
	resolveNativeDeliveryMode: ({ cfg, accountId }) => resolveTelegramExecApprovalTarget({
		cfg,
		accountId
	}),
	requireMatchingTurnSourceChannel: true
});
const telegramCommandTestPlugin = {
	id: "telegram",
	meta: getChatChannelMeta("telegram"),
	capabilities: {
		chatTypes: [
			"direct",
			"group",
			"channel",
			"thread"
		],
		reactions: true,
		threads: true,
		media: true,
		polls: true,
		nativeCommands: true,
		blockStreaming: true
	},
	config: telegramConfigAdapter,
	auth: telegramNativeApprovalAdapter.auth,
	pairing: { idLabel: "telegramUserId" },
	allowlist: buildDmGroupAccountAllowlistAdapter({
		channelId: "telegram",
		resolveAccount: resolveTelegramAccount,
		normalize: ({ cfg, accountId, values }) => telegramConfigAdapter.formatAllowFrom({
			cfg,
			accountId,
			allowFrom: values
		}),
		resolveDmAllowFrom: (account) => account.config.allowFrom,
		resolveGroupAllowFrom: (account) => account.config.groupAllowFrom,
		resolveDmPolicy: (account) => account.config.dmPolicy,
		resolveGroupPolicy: (account) => account.config.groupPolicy
	})
};
//#endregion
export { telegramCommandTestPlugin };
