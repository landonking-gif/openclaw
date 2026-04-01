import { t as defineSingleProviderPluginEntry } from "../../provider-entry-Dqynn4v9.js";
import { i as SYNTHETIC_DEFAULT_MODEL_REF } from "../../models-OP_KT-xF.js";
import { t as applySyntheticConfig } from "../../onboard--aIO_uXd.js";
import { t as buildSyntheticProvider } from "../../provider-catalog-4IqYML3M.js";
var synthetic_default = defineSingleProviderPluginEntry({
	id: "synthetic",
	name: "Synthetic Provider",
	description: "Bundled Synthetic provider plugin",
	provider: {
		label: "Synthetic",
		docsPath: "/providers/synthetic",
		auth: [{
			methodId: "api-key",
			label: "Synthetic API key",
			hint: "Anthropic-compatible (multi-model)",
			optionKey: "syntheticApiKey",
			flagName: "--synthetic-api-key",
			envVar: "SYNTHETIC_API_KEY",
			promptMessage: "Enter Synthetic API key",
			defaultModel: SYNTHETIC_DEFAULT_MODEL_REF,
			applyConfig: (cfg) => applySyntheticConfig(cfg)
		}],
		catalog: { buildProvider: buildSyntheticProvider }
	}
});
//#endregion
export { synthetic_default as default };
