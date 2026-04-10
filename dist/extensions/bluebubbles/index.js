import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { t as bluebubblesPlugin } from "../../channel-9Egw69zj.js";
import { n as setBlueBubblesRuntime } from "../../runtime-A8MY7fOY.js";
//#region extensions/bluebubbles/index.ts
var bluebubbles_default = defineChannelPluginEntry({
	id: "bluebubbles",
	name: "BlueBubbles",
	description: "BlueBubbles channel plugin (macOS app)",
	plugin: bluebubblesPlugin,
	setRuntime: setBlueBubblesRuntime
});
//#endregion
export { bluebubblesPlugin, bluebubbles_default as default, setBlueBubblesRuntime };
