import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-xyEt5-6M.js";
import "./media-understanding-BMZhmf1k.js";
//#region extensions/minimax/media-understanding-provider.ts
const minimaxMediaUnderstandingProvider = {
	id: "minimax",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
const minimaxPortalMediaUnderstandingProvider = {
	id: "minimax-portal",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { minimaxPortalMediaUnderstandingProvider as n, minimaxMediaUnderstandingProvider as t };
