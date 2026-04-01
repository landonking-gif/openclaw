import "./model-definitions-Bs6ZTaX9.js";
import "./provider-catalog-Cuc-qbe5.js";
import "./onboard-PkFb3ub4.js";
const MISTRAL_MODEL_COMPAT_PATCH = {
	supportsStore: false,
	supportsReasoningEffort: false,
	maxTokensField: "max_tokens"
};
function applyMistralModelCompat(model) {
	const compat = model.compat && typeof model.compat === "object" ? model.compat : void 0;
	if (compat && Object.entries(MISTRAL_MODEL_COMPAT_PATCH).every(([key, value]) => compat[key] === value)) return model;
	return {
		...model,
		compat: {
			...compat,
			...MISTRAL_MODEL_COMPAT_PATCH
		}
	};
}
//#endregion
export { applyMistralModelCompat as n, MISTRAL_MODEL_COMPAT_PATCH as t };
