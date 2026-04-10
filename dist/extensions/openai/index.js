import { t as definePluginEntry } from "../../plugin-entry-Bmh88Dqj.js";
import { t as buildOpenAICodexCliBackend } from "../../cli-backend-Dtixus31.js";
import { t as buildOpenAIImageGenerationProvider } from "../../image-generation-provider-VdfSW55L.js";
import { n as openaiCodexMediaUnderstandingProvider, r as openaiMediaUnderstandingProvider } from "../../media-understanding-provider-DGy0CyJl.js";
import { t as buildOpenAICodexProviderPlugin } from "../../openai-codex-provider-DHXssTBQ.js";
import { t as buildOpenAIProvider } from "../../openai-provider-BFw_WMRt.js";
import { t as buildOpenAISpeechProvider } from "../../speech-provider-BMk_dhkG.js";
//#region extensions/openai/index.ts
var openai_default = definePluginEntry({
	id: "openai",
	name: "OpenAI Provider",
	description: "Bundled OpenAI provider plugins",
	register(api) {
		api.registerCliBackend(buildOpenAICodexCliBackend());
		api.registerProvider(buildOpenAIProvider());
		api.registerProvider(buildOpenAICodexProviderPlugin());
		api.registerSpeechProvider(buildOpenAISpeechProvider());
		api.registerMediaUnderstandingProvider(openaiMediaUnderstandingProvider);
		api.registerMediaUnderstandingProvider(openaiCodexMediaUnderstandingProvider);
		api.registerImageGenerationProvider(buildOpenAIImageGenerationProvider());
	}
});
//#endregion
export { openai_default as default };
