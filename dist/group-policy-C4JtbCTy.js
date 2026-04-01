import { t as adaptScopedAccountAccessor } from "./channel-config-helpers-BW7FxcKd.js";
import { n as resolveChannelGroupRequireMention, r as resolveChannelGroupToolsPolicy } from "./group-policy-C6p_uQdV.js";
import "./channel-policy-DoPDTANw.js";
import "./directory-runtime-BHJ45McI.js";
import { f as listResolvedDirectoryGroupEntriesFromMapKeys, p as listResolvedDirectoryUserEntriesFromAllowFrom } from "./directory-config-helpers-CvCnMuoD.js";
import { s as resolveWhatsAppAccount } from "./accounts-BFq5S8nr.js";
import { i as isWhatsAppGroupJid, o as normalizeWhatsAppTarget } from "./runtime-api-CFuFc8eL.js";
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
