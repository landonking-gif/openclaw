import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-080_QraJ.js";
import "./media-understanding-Dp_ao2k0.js";
//#region extensions/openrouter/media-understanding-provider.ts
const openrouterMediaUnderstandingProvider = {
	id: "openrouter",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { openrouterMediaUnderstandingProvider as t };
