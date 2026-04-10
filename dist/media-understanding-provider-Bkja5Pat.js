import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-080_QraJ.js";
import "./media-understanding-Dp_ao2k0.js";
//#region extensions/anthropic/media-understanding-provider.ts
const anthropicMediaUnderstandingProvider = {
	id: "anthropic",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { anthropicMediaUnderstandingProvider as t };
