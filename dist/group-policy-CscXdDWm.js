import { t as adaptScopedAccountAccessor } from "./channel-config-helpers-XkwmfU3s.js";
import { n as resolveChannelGroupRequireMention, r as resolveChannelGroupToolsPolicy } from "./group-policy-DD8wDxR4.js";
import "./channel-policy-XbkOLNBx.js";
import "./directory-runtime-D4u4scXG.js";
import { f as listResolvedDirectoryGroupEntriesFromMapKeys, p as listResolvedDirectoryUserEntriesFromAllowFrom } from "./directory-config-helpers-DG1RRDLI.js";
import { s as resolveWhatsAppAccount } from "./accounts-DI2u75DC.js";
import { i as isWhatsAppGroupJid, o as normalizeWhatsAppTarget } from "./runtime-api-DRi8kZYv2.js";
//#region extensions/whatsapp/src/directory-config.ts
async function listWhatsAppDirectoryPeersFromConfig(params) {
	return listResolvedDirectoryUserEntriesFromAllowFrom({
		...params,
		resolveAccount: adaptScopedAccountAccessor(resolveWhatsAppAccount),
		resolveAllowFrom: (account) => account.allowFrom,
		normalizeId: (entry) => {
			const normalized = normalizeWhatsAppTarget(entry);
			if (!normalized || isWhatsAppGroupJid(normalized)) return null;
			return normalized;
		}
	});
}
async function listWhatsAppDirectoryGroupsFromConfig(params) {
	return listResolvedDirectoryGroupEntriesFromMapKeys({
		...params,
		resolveAccount: adaptScopedAccountAccessor(resolveWhatsAppAccount),
		resolveGroups: (account) => account.groups
	});
}
//#endregion
//#region extensions/whatsapp/src/group-policy.ts
function resolveWhatsAppGroupRequireMention(params) {
	return resolveChannelGroupRequireMention({
		cfg: params.cfg,
		channel: "whatsapp",
		groupId: params.groupId,
		accountId: params.accountId
	});
}
function resolveWhatsAppGroupToolPolicy(params) {
	return resolveChannelGroupToolsPolicy({
		cfg: params.cfg,
		channel: "whatsapp",
		groupId: params.groupId,
		accountId: params.accountId,
		senderId: params.senderId,
		senderName: params.senderName,
		senderUsername: params.senderUsername,
		senderE164: params.senderE164
	});
}
//#endregion
export { listWhatsAppDirectoryPeersFromConfig as i, resolveWhatsAppGroupToolPolicy as n, listWhatsAppDirectoryGroupsFromConfig as r, resolveWhatsAppGroupRequireMention as t };
