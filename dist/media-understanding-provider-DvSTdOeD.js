import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-xyEt5-6M.js";
import "./media-understanding-BMZhmf1k.js";
//#region extensions/anthropic/media-understanding-provider.ts
const anthropicMediaUnderstandingProvider = {
	id: "anthropic",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { anthropicMediaUnderstandingProvider as t };
