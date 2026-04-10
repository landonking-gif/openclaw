import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-080_QraJ.js";
import "./media-understanding-Dp_ao2k0.js";
//#region extensions/zai/media-understanding-provider.ts
const zaiMediaUnderstandingProvider = {
	id: "zai",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { zaiMediaUnderstandingProvider as t };
