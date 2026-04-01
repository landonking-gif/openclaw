import { t as getChatChannelMeta } from "./chat-meta-vnJDD9J6.js";
import { n as describeAccountSnapshot } from "./account-helpers-MFn2d_bl.js";
import { c as createScopedChannelConfigAdapter, m as formatTrimmedAllowFromEntries, t as adaptScopedAccountAccessor } from "./channel-config-helpers-BW7FxcKd.js";
import { n as createChannelPluginBase } from "./core-BIzVA7Id.js";
import { t as createRestrictSendersChannelSecurity } from "./channel-policy-DoPDTANw.js";
import "./runtime-api-Di53CbAR.js";
import { b as resolveIMessageAccount, v as listIMessageAccountIds, y as resolveDefaultIMessageAccountId } from "./monitor-provider-BXPM_9Na.js";
import { n as createIMessageSetupWizardProxy } from "./setup-core-Bne8CdZ9.js";
import { t as IMessageChannelConfigSchema } from "./config-schema-CvenV0jI.js";
//#region extensions/imessage/src/shared.ts
const IMESSAGE_CHANNEL = "imessage";
async function loadIMessageChannelRuntime() {
	return await import("./channel.runtime-KFm5n36R.js");
}
const imessageSetupWizard = createIMessageSetupWizardProxy(async () => (await loadIMessageChannelRuntime()).imessageSetupWizard);
const imessageConfigAdapter = createScopedChannelConfigAdapter({
	sectionKey: IMESSAGE_CHANNEL,
	listAccountIds: listIMessageAccountIds,
	resolveAccount: adaptScopedAccountAccessor(resolveIMessageAccount),
	defaultAccountId: resolveDefaultIMessageAccountId,
	clearBaseFields: [
		"cliPath",
		"dbPath",
		"service",
		"region",
		"name"
	],
	resolveAllowFrom: (account) => account.config.allowFrom,
	formatAllowFrom: (allowFrom) => formatTrimmedAllowFromEntries(allowFrom),
	resolveDefaultTo: (account) => account.config.defaultTo
});
const imessageSecurityAdapter = createRestrictSendersChannelSecurity({
	channelKey: IMESSAGE_CHANNEL,
	resolveDmPolicy: (account) => account.config.dmPolicy,
	resolveDmAllowFrom: (account) => account.config.allowFrom,
	resolveGroupPolicy: (account) => account.config.groupPolicy,
	surface: "iMessage groups",
	openScope: "any member",
	groupPolicyPath: "channels.imessage.groupPolicy",
	groupAllowFromPath: "channels.imessage.groupAllowFrom",
	mentionGated: false,
	policyPathSuffix: "dmPolicy"
});
function createIMessagePluginBase(params) {
	return createChannelPluginBase({
		id: IMESSAGE_CHANNEL,
		meta: {
			...getChatChannelMeta(IMESSAGE_CHANNEL),
			aliases: ["imsg"],
			showConfigured: false
		},
		setupWizard: params.setupWizard,
		capabilities: {
			chatTypes: ["direct", "group"],
			media: true
		},
		reload: { configPrefixes: ["channels.imessage"] },
		configSchema: IMessageChannelConfigSchema,
		config: {
			...imessageConfigAdapter,
			isConfigured: (account) => account.configured,
			describeAccount: (account) => describeAccountSnapshot({
				account,
				configured: account.configured
			})
		},
		security: imessageSecurityAdapter,
		setup: params.setup
	});
}
//#endregion
export { imessageSecurityAdapter as n, imessageSetupWizard as r, createIMessagePluginBase as t };
