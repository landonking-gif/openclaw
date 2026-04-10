import { l as getExecApprovalReplyMetadata } from "./exec-approval-reply-Dh5fPINs.js";
import { r as resolveApprovalRequestOriginTarget } from "./exec-approval-session-target-B-Xxpasz.js";
import { n as createApproverRestrictedNativeApprovalAdapter, t as resolveApprovalApprovers } from "./approval-runtime-BxXp_f2n.js";
import { n as listDiscordAccountIds, o as resolveDiscordAccount } from "./accounts-ISdL18DD.js";
import { n as parseDiscordTarget } from "./runtime-api-Bipri5cw.js";
import { t as inspectDiscordAccount } from "./account-inspect-BxPSJpel.js";
import { Container } from "@buape/carbon";
//#region extensions/discord/src/exec-approvals.ts
function normalizeDiscordApproverId(value) {
	const trimmed = value.trim();
	if (!trimmed) return;
	if (/^\d+$/.test(trimmed)) return trimmed;
	try {
		const target = parseDiscordTarget(trimmed);
		return target?.kind === "user" ? target.id : void 0;
	} catch {
		return;
	}
}
function resolveDiscordOwnerApprovers(cfg) {
	const ownerAllowFrom = cfg.commands?.ownerAllowFrom;
	if (!Array.isArray(ownerAllowFrom) || ownerAllowFrom.length === 0) return [];
	return resolveApprovalApprovers({
		explicit: ownerAllowFrom,
		normalizeApprover: (value) => normalizeDiscordApproverId(String(value))
	});
}
function getDiscordExecApprovalApprovers(params) {
	return resolveApprovalApprovers({
		explicit: params.configOverride?.approvers ?? resolveDiscordAccount(params).config.execApprovals?.approvers ?? resolveDiscordOwnerApprovers(params.cfg),
		normalizeApprover: (value) => normalizeDiscordApproverId(String(value))
	});
}
function isDiscordExecApprovalClientEnabled(params) {
	const config = params.configOverride ?? resolveDiscordAccount(params).config.execApprovals;
	return Boolean(config?.enabled && getDiscordExecApprovalApprovers({
		cfg: params.cfg,
		accountId: params.accountId,
		configOverride: params.configOverride
	}).length > 0);
}
function isDiscordExecApprovalApprover(params) {
	const senderId = params.senderId?.trim();
	if (!senderId) return false;
	return getDiscordExecApprovalApprovers({
		cfg: params.cfg,
		accountId: params.accountId,
		configOverride: params.configOverride
	}).includes(senderId);
}
function shouldSuppressLocalDiscordExecApprovalPrompt(params) {
	return isDiscordExecApprovalClientEnabled(params) && getExecApprovalReplyMetadata(params.payload) !== null;
}
//#endregion
//#region extensions/discord/src/approval-native.ts
function extractDiscordChannelId(sessionKey) {
	if (!sessionKey) return null;
	const match = sessionKey.match(/discord:(?:channel|group):(\d+)/);
	return match ? match[1] : null;
}
function extractDiscordSessionKind(sessionKey) {
	if (!sessionKey) return null;
	const match = sessionKey.match(/discord:(channel|group|dm):/);
	if (!match) return null;
	return match[1];
}
function normalizeDiscordOriginChannelId(value) {
	if (!value) return null;
	const trimmed = value.trim();
	if (!trimmed) return null;
	const prefixed = trimmed.match(/^(?:channel|group):(\d+)$/i);
	if (prefixed) return prefixed[1];
	return /^\d+$/.test(trimmed) ? trimmed : null;
}
function resolveDiscordOriginTarget(params) {
	const sessionKind = extractDiscordSessionKind(params.request.request.sessionKey?.trim() || null);
	return resolveApprovalRequestOriginTarget({
		cfg: params.cfg,
		request: params.request,
		channel: "discord",
		accountId: params.accountId,
		resolveTurnSourceTarget: (request) => {
			const turnSourceChannel = request.request.turnSourceChannel?.trim().toLowerCase() || "";
			const rawTurnSourceTo = request.request.turnSourceTo?.trim() || "";
			const turnSourceTo = normalizeDiscordOriginChannelId(rawTurnSourceTo);
			const hasExplicitOriginTarget = /^(?:channel|group):/i.test(rawTurnSourceTo);
			if (turnSourceChannel !== "discord" || !turnSourceTo || sessionKind === "dm") return null;
			return hasExplicitOriginTarget || sessionKind === "channel" || sessionKind === "group" ? { to: turnSourceTo } : null;
		},
		resolveSessionTarget: (sessionTarget) => {
			if (sessionKind === "dm") return null;
			const targetTo = normalizeDiscordOriginChannelId(sessionTarget.to);
			return targetTo ? { to: targetTo } : null;
		},
		targetsMatch: (a, b) => a.to === b.to,
		resolveFallbackTarget: (request) => {
			if (sessionKind === "dm") return null;
			const legacyChannelId = extractDiscordChannelId(request.request.sessionKey?.trim() || null);
			return legacyChannelId ? { to: legacyChannelId } : null;
		}
	});
}
function resolveDiscordApproverDmTargets(params) {
	return getDiscordExecApprovalApprovers({
		cfg: params.cfg,
		accountId: params.accountId,
		configOverride: params.configOverride
	}).map((approver) => ({ to: String(approver) }));
}
function createDiscordNativeApprovalAdapter(configOverride) {
	return createApproverRestrictedNativeApprovalAdapter({
		channel: "discord",
		channelLabel: "Discord",
		listAccountIds: listDiscordAccountIds,
		hasApprovers: ({ cfg, accountId }) => getDiscordExecApprovalApprovers({
			cfg,
			accountId,
			configOverride
		}).length > 0,
		isExecAuthorizedSender: ({ cfg, accountId, senderId }) => isDiscordExecApprovalApprover({
			cfg,
			accountId,
			senderId,
			configOverride
		}),
		isNativeDeliveryEnabled: ({ cfg, accountId }) => isDiscordExecApprovalClientEnabled({
			cfg,
			accountId,
			configOverride
		}),
		resolveNativeDeliveryMode: ({ cfg, accountId }) => configOverride?.target ?? resolveDiscordAccount({
			cfg,
			accountId
		}).config.execApprovals?.target ?? "dm",
		resolveOriginTarget: ({ cfg, accountId, request }) => resolveDiscordOriginTarget({
			cfg,
			accountId,
			request
		}),
		resolveApproverDmTargets: ({ cfg, accountId }) => resolveDiscordApproverDmTargets({
			cfg,
			accountId,
			configOverride
		}),
		notifyOriginWhenDmOnly: true
	});
}
const discordNativeApprovalAdapter = createDiscordNativeApprovalAdapter();
//#endregion
//#region extensions/discord/src/ui.ts
const DEFAULT_DISCORD_ACCENT_COLOR = "#5865F2";
function normalizeDiscordAccentColor(raw) {
	const trimmed = (raw ?? "").trim();
	if (!trimmed) return null;
	const normalized = trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
	if (!/^#[0-9a-fA-F]{6}$/.test(normalized)) return null;
	return normalized.toUpperCase();
}
function resolveDiscordAccentColor(params) {
	return normalizeDiscordAccentColor(inspectDiscordAccount({
		cfg: params.cfg,
		accountId: params.accountId
	}).config.ui?.components?.accentColor) ?? DEFAULT_DISCORD_ACCENT_COLOR;
}
var DiscordUiContainer = class extends Container {
	constructor(params) {
		const accentColor = normalizeDiscordAccentColor(params.accentColor) ?? resolveDiscordAccentColor({
			cfg: params.cfg,
			accountId: params.accountId
		});
		super(params.components, {
			accentColor,
			spoiler: params.spoiler
		});
	}
};
//#endregion
export { isDiscordExecApprovalApprover as a, getDiscordExecApprovalApprovers as i, createDiscordNativeApprovalAdapter as n, isDiscordExecApprovalClientEnabled as o, discordNativeApprovalAdapter as r, shouldSuppressLocalDiscordExecApprovalPrompt as s, DiscordUiContainer as t };
