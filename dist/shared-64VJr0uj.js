import { t as getChatChannelMeta } from "./chat-meta-vnJDD9J6.js";
import { n as describeAccountSnapshot } from "./account-helpers-MFn2d_bl.js";
import { c as createScopedChannelConfigAdapter, t as adaptScopedAccountAccessor } from "./channel-config-helpers-BW7FxcKd.js";
import { n as createChannelPluginBase } from "./core-BIzVA7Id.js";
import { t as formatAllowFromLowercase } from "./allow-from-BhbznJsc.js";
import { a as resolveDefaultDiscordAccountId, n as listDiscordAccountIds, o as resolveDiscordAccount } from "./accounts-CKf6hS8T.js";
import "./runtime-api-DrFQma7F.js";
import { t as inspectDiscordAccount } from "./account-inspect-D8LITQJy.js";
import { n as createDiscordSetupWizardProxy } from "./setup-core-QtucFPWx.js";
import { t as DiscordChannelConfigSchema } from "./config-schema-DygI5eGI.js";
//#region extensions/discord/src/shared.ts
const DISCORD_CHANNEL = "discord";
async function loadDiscordChannelRuntime() {
	return await import("./channel.runtime-DxF4caTO.js");
}
const discordSetupWizard = createDiscordSetupWizardProxy(async () => (await loadDiscordChannelRuntime()).discordSetupWizard);
const discordConfigAdapter = createScopedChannelConfigAdapter({
	sectionKey: DISCORD_CHANNEL,
	listAccountIds: listDiscordAccountIds,
	resolveAccount: adaptScopedAccountAccessor(resolveDiscordAccount),
	inspectAccount: adaptScopedAccountAccessor(inspectDiscordAccount),
	defaultAccountId: resolveDefaultDiscordAccountId,
	clearBaseFields: ["token", "name"],
	resolveAllowFrom: (account) => account.config.dm?.allowFrom,
	formatAllowFrom: (allowFrom) => formatAllowFromLowercase({ allowFrom }),
	resolveDefaultTo: (account) => account.config.defaultTo
});
function createDiscordPluginBase(params) {
	return createChannelPluginBase({
		id: DISCORD_CHANNEL,
		setupWizard: discordSetupWizard,
		meta: { ...getChatChannelMeta(DISCORD_CHANNEL) },
		capabilities: {
			chatTypes: [
				"direct",
				"channel",
				"thread"
			],
			polls: true,
			reactions: true,
			threads: true,
			media: true,
			nativeCommands: true
		},
		streaming: { blockStreamingCoalesceDefaults: {
			minChars: 1500,
			idleMs: 1e3
		} },
		reload: { configPrefixes: ["channels.discord"] },
		configSchema: DiscordChannelConfigSchema,
		config: {
			...discordConfigAdapter,
			isConfigured: (account) => Boolean(account.token?.trim()),
			describeAccount: (account) => describeAccountSnapshot({
				account,
				configured: Boolean(account.token?.trim()),
				extra: { tokenSource: account.tokenSource }
			})
		},
		setup: params.setup
	});
}
//#endregion
export { discordConfigAdapter as n, createDiscordPluginBase as t };
