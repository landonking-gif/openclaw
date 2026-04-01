import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { n as setGoogleChatRuntime } from "../../runtime-BJiRtlfW.js";
import { t as googlechatPlugin } from "../../channel-CohZI622.js";
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
