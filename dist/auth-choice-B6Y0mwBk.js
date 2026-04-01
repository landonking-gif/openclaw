import { n as ensureAuthProfileStore } from "./store-y1lXgzE3.js";
import "./auth-profiles-CukZID_h.js";
import { g as resolveDefaultModelForAgent } from "./model-selection-D90MGDui.js";
import { n as listProfilesForProvider } from "./profiles-D9gga32V.js";
import { t as resolveEnvApiKey } from "./model-auth-env-CwoWLO_7.js";
import { a as hasUsableCustomProviderApiKey } from "./model-auth-CRn7ZlFJ.js";
import { r as loadModelCatalog } from "./model-catalog-nHjzoQYp.js";
import { t as buildProviderAuthRecoveryHint } from "./provider-auth-guidance-CtnlJITQ.js";
import { r as normalizeLegacyOnboardAuthChoice } from "./auth-choice-legacy-VnjAKx-8.js";
import { t as applyAuthChoiceLoadedPluginProvider } from "./provider-auth-choice-CAArMa7r.js";
import { n as applyAuthChoiceApiProviders, r as normalizeApiKeyTokenProviderAuthChoice } from "./provider-auth-choice-preference-CMBP4b1D.js";
//#region src/commands/auth-choice.apply.oauth.ts
async function applyAuthChoiceOAuth(_params) {
	return null;
}
//#endregion
//#region src/commands/auth-choice.apply.ts
async function applyAuthChoice(params) {
	const normalizedProviderAuthChoice = normalizeApiKeyTokenProviderAuthChoice({
		authChoice: normalizeLegacyOnboardAuthChoice(params.authChoice, {
			config: params.config,
			env: params.env
		}) ?? params.authChoice,
		tokenProvider: params.opts?.tokenProvider,
		config: params.config,
		env: params.env
	});
	const normalizedParams = normalizedProviderAuthChoice === params.authChoice ? params : {
		...params,
		authChoice: normalizedProviderAuthChoice
	};
	const handlers = [
		applyAuthChoiceLoadedPluginProvider,
		applyAuthChoiceOAuth,
		applyAuthChoiceApiProviders
	];
	for (const handler of handlers) {
		const result = await handler(normalizedParams);
		if (result) return result;
	}
	return { config: normalizedParams.config };
}
//#endregion
//#region src/commands/auth-choice.model-check.ts
async function warnIfModelConfigLooksOff(config, prompter, options) {
	const ref = resolveDefaultModelForAgent({
		cfg: config,
		agentId: options?.agentId
	});
	const warnings = [];
	const catalog = await loadModelCatalog({
		config,
		useCache: false
	});
	if (catalog.length > 0) {
		if (!catalog.some((entry) => entry.provider === ref.provider && entry.id === ref.model)) warnings.push(`Model not found: ${ref.provider}/${ref.model}. Update agents.defaults.model or run /models list.`);
	}
	const hasProfile = listProfilesForProvider(ensureAuthProfileStore(options?.agentDir), ref.provider).length > 0;
	const envKey = resolveEnvApiKey(ref.provider);
	const hasCustomKey = hasUsableCustomProviderApiKey(config, ref.provider);
	if (!hasProfile && !envKey && !hasCustomKey) warnings.push(`No auth configured for provider "${ref.provider}". The agent may fail until credentials are added. ${buildProviderAuthRecoveryHint({
		provider: ref.provider,
		config,
		includeEnvVar: true
	})}`);
	if (warnings.length > 0) await prompter.note(warnings.join("\n"), "Model check");
}
//#endregion
export { applyAuthChoice as n, warnIfModelConfigLooksOff as t };
