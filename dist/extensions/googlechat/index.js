import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { n as setGoogleChatRuntime } from "../../runtime-BKTNsiz5.js";
import { t as googlechatPlugin } from "../../channel-BFThTuPi.js";
//#region extensions/googlechat/index.ts
var googlechat_default = defineChannelPluginEntry({
	id: "googlechat",
	name: "Google Chat",
	description: "OpenClaw Google Chat channel plugin",
	plugin: googlechatPlugin,
	setRuntime: setGoogleChatRuntime
});
//#endregion
export { googlechat_default as default, googlechatPlugin, setGoogleChatRuntime };
