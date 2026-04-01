import { t as definePluginEntry } from "../../plugin-entry-C2JEeAkR.js";
import { t as buildOpenAICodexCliBackend } from "../../cli-backend-BrLjUnZe.js";
import { t as buildOpenAIImageGenerationProvider } from "../../image-generation-provider-Do42ysCG.js";
import { n as openaiCodexMediaUnderstandingProvider, r as openaiMediaUnderstandingProvider } from "../../media-understanding-provider-BztTkmn5.js";
import { t as buildOpenAICodexProviderPlugin } from "../../openai-codex-provider-CX1_eZQN.js";
import { t as buildOpenAIProvider } from "../../openai-provider-CeVnZVd4.js";
import { t as buildOpenAISpeechProvider } from "../../speech-provider-DsB727C5.js";
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
