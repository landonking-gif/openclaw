import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-080_QraJ.js";
import { t as transcribeOpenAiCompatibleAudio } from "./media-understanding-Dp_ao2k0.js";
import { n as OPENAI_DEFAULT_AUDIO_TRANSCRIPTION_MODEL } from "./default-models-CHGDqexP.js";
//#region extensions/openai/media-understanding-provider.ts
const DEFAULT_OPENAI_AUDIO_BASE_URL = "https://api.openai.com/v1";
async function transcribeOpenAiAudio(params) {
	return await transcribeOpenAiCompatibleAudio({
		...params,
		defaultBaseUrl: DEFAULT_OPENAI_AUDIO_BASE_URL,
		defaultModel: OPENAI_DEFAULT_AUDIO_TRANSCRIPTION_MODEL
	});
}
const openaiMediaUnderstandingProvider = {
	id: "openai",
	capabilities: ["image", "audio"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel,
	transcribeAudio: transcribeOpenAiAudio
};
const openaiCodexMediaUnderstandingProvider = {
	id: "openai-codex",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { transcribeOpenAiAudio as i, openaiCodexMediaUnderstandingProvider as n, openaiMediaUnderstandingProvider as r, DEFAULT_OPENAI_AUDIO_BASE_URL as t };
