import { d as resolvePinnedHostnameWithPolicy, i as createPinnedDispatcher, r as closeDispatcher } from "../../ssrf-C8Ew-J28.js";
import { n as writeJsonFileAtomically } from "../../json-store-BphZeuFy.js";
import { n as formatZonedTimestamp } from "../../format-datetime-Lk30PDCv.js";
import { a as ssrfPolicyFromAllowPrivateNetwork, t as assertHttpUrlTargetsPrivateNetwork } from "../../ssrf-policy-nXVGepAD.js";
import "../../ssrf-runtime-VeuSJJww.js";
import { _ as resolveMatrixEnvAccountToken, a as resolveMatrixCredentialsPath, c as resolveMatrixLegacyFlatStoreRoot, d as requiresExplicitMatrixDefaultAccount, f as resolveConfiguredMatrixAccountIds, g as listMatrixEnvAccountIds, h as getMatrixScopedEnvVarNames, i as resolveMatrixCredentialsFilename, l as sanitizeMatrixPathSegment, m as resolveMatrixDefaultOrOnlyAccountId, n as resolveMatrixAccountStorageRoot, o as resolveMatrixHomeserverKey, p as resolveMatrixChannelConfig, r as resolveMatrixCredentialsDir, s as resolveMatrixLegacyFlatStoragePaths, t as hashMatrixAccessToken, u as findMatrixAccountEntry } from "../../storage-paths-BOnyRjh-.js";
import { t as resolveMatrixAccountStringValues } from "../../auth-precedence-BwYXmbgU.js";
import { n as setMatrixRuntime } from "../../runtime-BHaBGlM4.js";
import { f as setMatrixThreadBindingMaxAgeBySessionKey, u as setMatrixThreadBindingIdleTimeoutBySessionKey } from "../../thread-bindings-shared-DkZbi_5Y.js";
//#region extensions/matrix/runtime-api.ts
function chunkTextForOutbound(text, limit) {
	const chunks = [];
	let remaining = text;
	while (remaining.length > limit) {
		const window = remaining.slice(0, limit);
		const splitAt = Math.max(window.lastIndexOf("\n"), window.lastIndexOf(" "));
		const breakAt = splitAt > 0 ? splitAt : limit;
		chunks.push(remaining.slice(0, breakAt).trimEnd());
		remaining = remaining.slice(breakAt).trimStart();
	}
	if (remaining.length > 0 || text.length === 0) chunks.push(remaining);
	return chunks;
}
//#endregion
export { assertHttpUrlTargetsPrivateNetwork, chunkTextForOutbound, closeDispatcher, createPinnedDispatcher, findMatrixAccountEntry, formatZonedTimestamp, getMatrixScopedEnvVarNames, hashMatrixAccessToken, listMatrixEnvAccountIds, requiresExplicitMatrixDefaultAccount, resolveConfiguredMatrixAccountIds, resolveMatrixAccountStorageRoot, resolveMatrixAccountStringValues, resolveMatrixChannelConfig, resolveMatrixCredentialsDir, resolveMatrixCredentialsFilename, resolveMatrixCredentialsPath, resolveMatrixDefaultOrOnlyAccountId, resolveMatrixEnvAccountToken, resolveMatrixHomeserverKey, resolveMatrixLegacyFlatStoragePaths, resolveMatrixLegacyFlatStoreRoot, resolvePinnedHostnameWithPolicy, sanitizeMatrixPathSegment, setMatrixRuntime, setMatrixThreadBindingIdleTimeoutBySessionKey, setMatrixThreadBindingMaxAgeBySessionKey, ssrfPolicyFromAllowPrivateNetwork, writeJsonFileAtomically };
