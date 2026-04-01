import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { n as setIrcRuntime, t as ircPlugin } from "../../channel-YWoOCmNt.js";
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
