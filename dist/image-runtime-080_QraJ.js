import { n as createLazyRuntimeMethodBinder, r as createLazyRuntimeModule } from "./lazy-runtime-WMlTFWAj.js";
//#region src/media-understanding/image-runtime.ts
const bindImageRuntime = createLazyRuntimeMethodBinder(createLazyRuntimeModule(() => import("./image-Dmh2r_Zl.js")));
const describeImageWithModel = bindImageRuntime((runtime) => runtime.describeImageWithModel);
const describeImagesWithModel = bindImageRuntime((runtime) => runtime.describeImagesWithModel);
//#endregion
export { describeImagesWithModel as n, describeImageWithModel as t };
