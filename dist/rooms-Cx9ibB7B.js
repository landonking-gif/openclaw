import { r as normalizeStringEntries } from "./string-normalization-CmGlAIu6.js";
import { i as resolveChannelEntryMatch, n as buildChannelKeyCandidates } from "./channel-config-2E1F20C8.js";
import { i as resolveAllowlistMatchByCandidates } from "./allowlist-match-CRykvb1F.js";
import "./matrix-runtime-heavy-CA1F71Tc.js";
import "./matrix-CWLb8Vwd.js";
import "./runtime-api-D7PTL6Yn.js";
//#region extensions/matrix/src/matrix/monitor/allowlist.ts
function normalizeAllowList(list) {
	return normalizeStringEntries(list);
}
function normalizeMatrixUser(raw) {
	const value = (raw ?? "").trim();
	if (!value) return "";
	if (!value.startsWith("@") || !value.includes(":")) return value.toLowerCase();
	const withoutAt = value.slice(1);
	const splitIndex = withoutAt.indexOf(":");
	if (splitIndex === -1) return value.toLowerCase();
	const localpart = withoutAt.slice(0, splitIndex).toLowerCase();
	const server = withoutAt.slice(splitIndex + 1).toLowerCase();
	if (!server) return value.toLowerCase();
	return `@${localpart}:${server.toLowerCase()}`;
}
function normalizeMatrixUserId(raw) {
	const trimmed = (raw ?? "").trim();
	if (!trimmed) return "";
	const lowered = trimmed.toLowerCase();
	if (lowered.startsWith("matrix:")) return normalizeMatrixUser(trimmed.slice(7));
	if (lowered.startsWith("user:")) return normalizeMatrixUser(trimmed.slice(5));
	return normalizeMatrixUser(trimmed);
}
function normalizeMatrixAllowListEntry(raw) {
	const trimmed = raw.trim();
	if (!trimmed) return "";
	if (trimmed === "*") return trimmed;
	const lowered = trimmed.toLowerCase();
	if (lowered.startsWith("matrix:")) return `matrix:${normalizeMatrixUser(trimmed.slice(7))}`;
	if (lowered.startsWith("user:")) return `user:${normalizeMatrixUser(trimmed.slice(5))}`;
	return normalizeMatrixUser(trimmed);
}
function normalizeMatrixAllowList(list) {
	return normalizeAllowList(list).map((entry) => normalizeMatrixAllowListEntry(entry));
}
function resolveMatrixAllowListMatch(params) {
	const allowList = params.allowList;
	if (allowList.length === 0) return { allowed: false };
	if (allowList.includes("*")) return {
		allowed: true,
		matchKey: "*",
		matchSource: "wildcard"
	};
	const userId = normalizeMatrixUser(params.userId);
	return resolveAllowlistMatchByCandidates({
		allowList,
		candidates: [
			{
				value: userId,
				source: "id"
			},
			{
				value: userId ? `matrix:${userId}` : "",
				source: "prefixed-id"
			},
			{
				value: userId ? `user:${userId}` : "",
				source: "prefixed-user"
			}
		]
	});
}
//#endregion
//#region extensions/matrix/src/matrix/monitor/rooms.ts
function resolveMatrixRoomConfig(params) {
	const rooms = params.rooms ?? {};
	const allowlistConfigured = Object.keys(rooms).length > 0;
	const { entry: matched, key: matchedKey, wildcardEntry, wildcardKey } = resolveChannelEntryMatch({
		entries: rooms,
		keys: buildChannelKeyCandidates(params.roomId, `room:${params.roomId}`, ...params.aliases),
		wildcardKey: "*"
	});
	const resolved = matched ?? wildcardEntry;
	return {
		allowed: resolved ? resolved.enabled !== false && resolved.allow !== false : false,
		allowlistConfigured,
		config: resolved,
		matchKey: matchedKey ?? wildcardKey,
		matchSource: matched ? "direct" : wildcardEntry ? "wildcard" : void 0
	};
}
//#endregion
export { resolveMatrixAllowListMatch as i, normalizeMatrixAllowList as n, normalizeMatrixUserId as r, resolveMatrixRoomConfig as t };
