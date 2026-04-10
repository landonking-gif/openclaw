import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { n as setIrcRuntime, t as ircPlugin } from "../../channel-BCoKc8AM.js";
//#region extensions/irc/index.ts
var irc_default = defineChannelPluginEntry({
	id: "irc",
	name: "IRC",
	description: "IRC channel plugin",
	plugin: ircPlugin,
	setRuntime: setIrcRuntime
});
//#endregion
export { irc_default as default, ircPlugin, setIrcRuntime };
