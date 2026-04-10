import { n as resolveMoonshotThinkingType, t as createMoonshotThinkingWrapper } from "../../moonshot-thinking-stream-wrappers-Bcn6-E6S.js";
import { t as defineSingleProviderPluginEntry } from "../../provider-entry-DiXcMexm.js";
import "../../provider-moonshot-CEbMSP5A.js";
import { a as buildMoonshotProvider, i as applyMoonshotNativeStreamingUsageCompat } from "../../provider-catalog-rCq73uz_.js";
import { n as applyMoonshotConfig, r as applyMoonshotConfigCn, t as MOONSHOT_DEFAULT_MODEL_REF } from "../../onboard-HvkVvD3a.js";
import "../../api-e2HoI0fW.js";
import { r as moonshotMediaUnderstandingProvider } from "../../media-understanding-provider-BRM6I_fi.js";
import { n as createKimiWebSearchProvider } from "../../kimi-web-search-provider-DWj4cdOA.js";
var moonshot_default = defineSingleProviderPluginEntry({
	id: "moonshot",
	name: "Moonshot Provider",
	description: "Bundled Moonshot provider plugin",
	provider: {
		label: "Moonshot",
		docsPath: "/providers/moonshot",
		auth: [{
			methodId: "api-key",
			label: "Kimi API key (.ai)",
			hint: "Kimi K2.5 + Kimi",
			optionKey: "moonshotApiKey",
			flagName: "--moonshot-api-key",
			envVar: "MOONSHOT_API_KEY",
			promptMessage: "Enter Moonshot API key",
			defaultModel: MOONSHOT_DEFAULT_MODEL_REF,
			applyConfig: (cfg) => applyMoonshotConfig(cfg),
			wizard: { groupLabel: "Moonshot AI (Kimi K2.5)" }
		}, {
			methodId: "api-key-cn",
			label: "Kimi API key (.cn)",
			hint: "Kimi K2.5 + Kimi",
			optionKey: "moonshotApiKey",
			flagName: "--moonshot-api-key",
			envVar: "MOONSHOT_API_KEY",
			promptMessage: "Enter Moonshot API key (.cn)",
			defaultModel: MOONSHOT_DEFAULT_MODEL_REF,
			applyConfig: (cfg) => applyMoonshotConfigCn(cfg),
			wizard: { groupLabel: "Moonshot AI (Kimi K2.5)" }
		}],
		catalog: {
			buildProvider: buildMoonshotProvider,
			allowExplicitBaseUrl: true
		},
		applyNativeStreamingUsageCompat: ({ providerConfig }) => applyMoonshotNativeStreamingUsageCompat(providerConfig),
		wrapStreamFn: (ctx) => {
			const thinkingType = resolveMoonshotThinkingType({
				configuredThinking: ctx.extraParams?.thinking,
				thinkingLevel: ctx.thinkingLevel
			});
			return createMoonshotThinkingWrapper(ctx.streamFn, thinkingType);
		}
	},
	register(api) {
		api.registerMediaUnderstandingProvider(moonshotMediaUnderstandingProvider);
		api.registerWebSearchProvider(createKimiWebSearchProvider());
	}
});
//#endregion
export { moonshot_default as default };
