import { r as describeWebhookAccountSnapshot } from "./account-helpers-DaxrMp_H.js";
import { c as createScopedChannelConfigAdapter } from "./channel-config-helpers-XkwmfU3s.js";
import { v as LineChannelConfigSchema } from "./runtime-api-FmVHcb64.js";
import { i as resolveLineAccount, r as resolveDefaultLineAccountId, t as listLineAccountIds } from "./accounts-hntrjtFa.js";
import { r as hasLineCredentials } from "./setup-surface-CR5xmR1o.js";
//#region extensions/line/src/config-adapter.ts
function normalizeLineAllowFrom(entry) {
	return entry.replace(/^line:(?:user:)?/i, "");
}
const lineChannelPluginCommon = {
	meta: {
		id: "line",
		label: "LINE",
		selectionLabel: "LINE (Messaging API)",
		detailLabel: "LINE Bot",
		docsPath: "/channels/line",
		docsLabel: "line",
		blurb: "LINE Messaging API bot for Japan/Taiwan/Thailand markets.",
		systemImage: "message.fill",
		quickstartAllowFrom: true
	},
	capabilities: {
		chatTypes: ["direct", "group"],
		reactions: false,
		threads: false,
		media: true,
		nativeCommands: false,
		blockStreaming: true
	},
	reload: { configPrefixes: ["channels.line"] },
	configSchema: LineChannelConfigSchema,
	config: {
		...createScopedChannelConfigAdapter({
			sectionKey: "line",
			listAccountIds: listLineAccountIds,
			resolveAccount: (cfg, accountId) => resolveLineAccount({
				cfg,
				accountId: accountId ?? void 0
			}),
			defaultAccountId: resolveDefaultLineAccountId,
			clearBaseFields: [
				"channelSecret",
				"tokenFile",
				"secretFile"
			],
			resolveAllowFrom: (account) => account.config.allowFrom,
			formatAllowFrom: (allowFrom) => allowFrom.map((entry) => String(entry).trim()).filter(Boolean).map(normalizeLineAllowFrom)
		}),
		isConfigured: (account) => hasLineCredentials(account),
		describeAccount: (account) => describeWebhookAccountSnapshot({
			account,
			configured: hasLineCredentials(account),
			extra: { tokenSource: account.tokenSource ?? void 0 }
		})
	}
};
//#endregion
export { lineChannelPluginCommon as t };
