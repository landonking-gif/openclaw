import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { b as setMSTeamsRuntime } from "../../graph-users-DJzu37Kx.js";
import { t as msteamsPlugin } from "../../channel-Cqu5HQzZ.js";
//#region extensions/msteams/index.ts
var msteams_default = defineChannelPluginEntry({
	id: "msteams",
	name: "Microsoft Teams",
	description: "Microsoft Teams channel plugin (Bot Framework)",
	plugin: msteamsPlugin,
	setRuntime: setMSTeamsRuntime
});
//#endregion
export { msteams_default as default, msteamsPlugin, setMSTeamsRuntime };
