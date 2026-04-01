import { a as hasConfiguredSecretInput, i as coerceSecretRef, l as normalizeSecretInputString } from "./types.secrets-DuSPmmWB.js";
import { l as resolveDefaultSecretProviderAlias } from "./ref-contract-CxEAy2bI.js";
import { _ as normalizeAccountId } from "./session-key-4QR94Oth.js";
import { n as resolveAccountWithDefaultFallback } from "./account-core-OC3vTo_t.js";
import { i as tryReadSecretFileSync } from "./secret-file-CJy1G8b5.js";
import "./core-BIzVA7Id.js";
import "./routing-plyUTpqn.js";
import "./secret-input-5Z_M9SDk.js";
import "./config-runtime-DmPX4R_k.js";
import "./provider-auth-BtnejrKb.js";
import { c as resolveTelegramAccountConfig, i as mergeTelegramAccountConfig, o as resolveDefaultTelegramAccountId } from "./accounts-Dmlv188W.js";
//#region extensions/telegram/src/account-inspect.ts
function inspectTokenFile(pathValue) {
	const tokenFile = typeof pathValue === "string" ? pathValue.trim() : "";
	if (!tokenFile) return null;
	const token = tryReadSecretFileSync(tokenFile, "Telegram bot token", { rejectSymlink: true });
	return {
		token: token ?? "",
		tokenSource: "tokenFile",
		tokenStatus: token ? "available" : "configured_unavailable"
	};
}
function canResolveEnvSecretRefInReadOnlyPath(params) {
	const providerConfig = params.cfg.secrets?.providers?.[params.provider];
	if (!providerConfig) return params.provider === resolveDefaultSecretProviderAlias(params.cfg, "env");
	if (providerConfig.source !== "env") return false;
	const allowlist = providerConfig.allowlist;
	return !allowlist || allowlist.includes(params.id);
}
function inspectTokenValue(params) {
	const ref = coerceSecretRef(params.value, params.cfg.secrets?.defaults);
	if (ref?.source === "env") {
		if (!canResolveEnvSecretRefInReadOnlyPath({
			cfg: params.cfg,
			provider: ref.provider,
			id: ref.id
		})) return {
			token: "",
			tokenSource: "env",
			tokenStatus: "configured_unavailable"
		};
		const envValue = process.env[ref.id];
		if (envValue && envValue.trim()) return {
			token: envValue.trim(),
			tokenSource: "env",
			tokenStatus: "available"
		};
		return {
			token: "",
			tokenSource: "env",
			tokenStatus: "configured_unavailable"
		};
	}
	const token = normalizeSecretInputString(params.value);
	if (token) return {
		token,
		tokenSource: "config",
		tokenStatus: "available"
	};
	if (hasConfiguredSecretInput(params.value, params.cfg.secrets?.defaults)) return {
		token: "",
		tokenSource: "config",
		tokenStatus: "configured_unavailable"
	};
	return null;
}
function inspectTelegramAccountPrimary(params) {
	const accountId = normalizeAccountId(params.accountId);
	const merged = mergeTelegramAccountConfig(params.cfg, accountId);
	const enabled = params.cfg.channels?.telegram?.enabled !== false && merged.enabled !== false;
	const accountConfig = resolveTelegramAccountConfig(params.cfg, accountId);
	const accountTokenFile = inspectTokenFile(accountConfig?.tokenFile);
	if (accountTokenFile) return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: accountTokenFile.token,
		tokenSource: accountTokenFile.tokenSource,
		tokenStatus: accountTokenFile.tokenStatus,
		configured: accountTokenFile.tokenStatus !== "missing",
		config: merged
	};
	const accountToken = inspectTokenValue({
		cfg: params.cfg,
		value: accountConfig?.botToken
	});
	if (accountToken) return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: accountToken.token,
		tokenSource: accountToken.tokenSource,
		tokenStatus: accountToken.tokenStatus,
		configured: accountToken.tokenStatus !== "missing",
		config: merged
	};
	const channelTokenFile = inspectTokenFile(params.cfg.channels?.telegram?.tokenFile);
	if (channelTokenFile) return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: channelTokenFile.token,
		tokenSource: channelTokenFile.tokenSource,
		tokenStatus: channelTokenFile.tokenStatus,
		configured: channelTokenFile.tokenStatus !== "missing",
		config: merged
	};
	const channelToken = inspectTokenValue({
		cfg: params.cfg,
		value: params.cfg.channels?.telegram?.botToken
	});
	if (channelToken) return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: channelToken.token,
		tokenSource: channelToken.tokenSource,
		tokenStatus: channelToken.tokenStatus,
		configured: channelToken.tokenStatus !== "missing",
		config: merged
	};
	const envToken = accountId === "default" ? (params.envToken ?? process.env.TELEGRAM_BOT_TOKEN)?.trim() : "";
	if (envToken) return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: envToken,
		tokenSource: "env",
		tokenStatus: "available",
		configured: true,
		config: merged
	};
	return {
		accountId,
		enabled,
		name: merged.name?.trim() || void 0,
		token: "",
		tokenSource: "none",
		tokenStatus: "missing",
		configured: false,
		config: merged
	};
}
function inspectTelegramAccount(params) {
	return resolveAccountWithDefaultFallback({
		accountId: params.accountId,
		normalizeAccountId,
		resolvePrimary: (accountId) => inspectTelegramAccountPrimary({
			cfg: params.cfg,
			accountId,
			envToken: params.envToken
		}),
		hasCredential: (account) => account.tokenSource !== "none",
		resolveDefaultAccountId: () => resolveDefaultTelegramAccountId(params.cfg)
	});
}
//#endregion
export { inspectTelegramAccount as t };
