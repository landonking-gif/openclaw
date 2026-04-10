import { d as normalizeMessageChannel } from "./message-channel-Bk-oI2vE.js";
import { t as normalizeChatType } from "./chat-type-BjcvDs4y.js";
import { a as resolveChannelEntryMatchWithFallback, n as buildChannelKeyCandidates, r as normalizeChannelSlug } from "./channel-config-DhplD0As.js";
import { n as resolveSessionConversationRef, t as resolveSessionConversation } from "./session-conversation-D7xK_bQI.js";
//#region src/channels/model-overrides.ts
function resolveProviderEntry(modelByChannel, channel) {
	const normalized = normalizeMessageChannel(channel) ?? channel.trim().toLowerCase();
	return modelByChannel?.[normalized] ?? modelByChannel?.[Object.keys(modelByChannel ?? {}).find((key) => {
		return (normalizeMessageChannel(key) ?? key.trim().toLowerCase()) === normalized;
	}) ?? ""];
}
function buildChannelCandidates(params) {
	const normalizedChannel = normalizeMessageChannel(params.channel ?? "") ?? params.channel?.trim().toLowerCase();
	const groupId = params.groupId?.trim();
	const sessionConversation = resolveSessionConversationRef(params.parentSessionKey);
	const groupConversationKind = normalizeChatType(params.groupChatType ?? void 0) === "channel" ? "channel" : sessionConversation?.kind === "channel" ? "channel" : "group";
	const groupConversation = resolveSessionConversation({
		channel: normalizedChannel ?? "",
		kind: groupConversationKind,
		rawId: groupId ?? ""
	});
	const groupChannel = params.groupChannel?.trim();
	const groupSubject = params.groupSubject?.trim();
	const channelBare = groupChannel ? groupChannel.replace(/^#/, "") : void 0;
	const subjectBare = groupSubject ? groupSubject.replace(/^#/, "") : void 0;
	const channelSlug = channelBare ? normalizeChannelSlug(channelBare) : void 0;
	const subjectSlug = subjectBare ? normalizeChannelSlug(subjectBare) : void 0;
	return {
		keys: buildChannelKeyCandidates(groupId, sessionConversation?.rawId, ...groupConversation?.parentConversationCandidates ?? [], ...sessionConversation?.parentConversationCandidates ?? []),
		parentKeys: buildChannelKeyCandidates(groupChannel, channelBare, channelSlug, groupSubject, subjectBare, subjectSlug)
	};
}
function resolveChannelModelOverride(params) {
	const channel = params.channel?.trim();
	if (!channel) return null;
	const modelByChannel = params.cfg.channels?.modelByChannel;
	if (!modelByChannel) return null;
	const providerEntries = resolveProviderEntry(modelByChannel, channel);
	if (!providerEntries) return null;
	const { keys, parentKeys } = buildChannelCandidates(params);
	if (keys.length === 0 && parentKeys.length === 0) return null;
	const match = resolveChannelEntryMatchWithFallback({
		entries: providerEntries,
		keys,
		parentKeys,
		wildcardKey: "*",
		normalizeKey: (value) => value.trim().toLowerCase()
	});
	const raw = match.entry ?? match.wildcardEntry;
	if (typeof raw !== "string") return null;
	const model = raw.trim();
	if (!model) return null;
	return {
		channel: normalizeMessageChannel(channel) ?? channel.trim().toLowerCase(),
		model,
		matchKey: match.matchKey,
		matchSource: match.matchSource
	};
}
//#endregion
export { resolveChannelModelOverride as t };
