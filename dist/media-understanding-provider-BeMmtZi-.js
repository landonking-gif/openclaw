import { n as describeImagesWithModel, t as describeImageWithModel } from "./image-runtime-xyEt5-6M.js";
import "./media-understanding-BMZhmf1k.js";
//#region extensions/openrouter/media-understanding-provider.ts
const openrouterMediaUnderstandingProvider = {
	id: "openrouter",
	capabilities: ["image"],
	describeImage: describeImageWithModel,
	describeImages: describeImagesWithModel
};
//#endregion
export { openrouterMediaUnderstandingProvider as t };
