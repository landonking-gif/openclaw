import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-xyEt5-6M.js";
import "./media-understanding-BMZhmf1k.js";
//#region extensions/zai/media-understanding-provider.ts
const zaiMediaUnderstandingProvider = {
	id: "zai",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { zaiMediaUnderstandingProvider as t };
