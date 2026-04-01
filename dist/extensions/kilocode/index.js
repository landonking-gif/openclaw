import { t as defineSingleProviderPluginEntry } from "../../provider-entry-Dqynn4v9.js";
import { a as createKilocodeWrapper, c as isProxyReasoningUnsupported } from "../../provider-stream-CJZgrFLB.js";
import { s as KILOCODE_DEFAULT_MODEL_REF } from "../../provider-models-Cp2JA_r9.js";
import { n as buildKilocodeProviderWithDiscovery } from "../../provider-catalog-CUVpJkox.js";
import { t as applyKilocodeConfig } from "../../onboard-DgQFHvbW.js";
var kilocode_default = defineSingleProviderPluginEntry({
	id: "kilocode",
	name: "Kilo Gateway Provider",
	description: "Bundled Kilo Gateway provider plugin",
	provider: {
		label: "Kilo Gateway",
		docsPath: "/providers/kilocode",
		auth: [{
			methodId: "api-key",
			label: "Kilo Gateway API key",
			hint: "API key (OpenRouter-compatible)",
			optionKey: "kilocodeApiKey",
			flagName: "--kilocode-api-key",
			envVar: "KILOCODE_API_KEY",
			promptMessage: "Enter Kilo Gateway API key",
			defaultModel: KILOCODE_DEFAULT_MODEL_REF,
			applyConfig: (cfg) => applyKilocodeConfig(cfg)
		}],
		catalog: { buildProvider: buildKilocodeProviderWithDiscovery },
		capabilities: {
			geminiThoughtSignatureSanitization: true,
			geminiThoughtSignatureModelHints: ["gemini"]
		},
		wrapStreamFn: (ctx) => {
			const thinkingLevel = ctx.modelId === "kilo/auto" || isProxyReasoningUnsupported(ctx.modelId) ? void 0 : ctx.thinkingLevel;
			return createKilocodeWrapper(ctx.streamFn, thinkingLevel);
		},
		isCacheTtlEligible: (ctx) => ctx.modelId.startsWith("anthropic/")
	}
});
//#endregion
export { kilocode_default as default };
