import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { t as zaloPlugin } from "../../channel-CLcL2fqs.js";
import { n as setZaloRuntime } from "../../runtime-s_uMFQkd.js";
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
