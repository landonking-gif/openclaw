import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { n as setSynologyRuntime, t as synologyChatPlugin } from "../../channel-BnLlcceF.js";
//#region extensions/synology-chat/index.ts
var synology_chat_default = defineChannelPluginEntry({
	id: "synology-chat",
	name: "Synology Chat",
	description: "Native Synology Chat channel plugin for OpenClaw",
	plugin: synologyChatPlugin,
	setRuntime: setSynologyRuntime
});
//#endregion
export { synology_chat_default as default, setSynologyRuntime, synologyChatPlugin };
