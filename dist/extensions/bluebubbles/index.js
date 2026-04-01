import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { t as bluebubblesPlugin } from "../../channel-C-JWOKP2.js";
import { n as setBlueBubblesRuntime } from "../../runtime-DJTF2IDc.js";
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
