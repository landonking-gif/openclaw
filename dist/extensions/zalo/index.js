import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { t as zaloPlugin } from "../../channel-DaDqfk8V.js";
import { n as setZaloRuntime } from "../../runtime-B8yeGyKW.js";
//#region extensions/zalo/index.ts
var zalo_default = defineChannelPluginEntry({
	id: "zalo",
	name: "Zalo",
	description: "Zalo channel plugin",
	plugin: zaloPlugin,
	setRuntime: setZaloRuntime
});
//#endregion
export { zalo_default as default, setZaloRuntime, zaloPlugin };
