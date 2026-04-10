import { i as defineChannelPluginEntry } from "../../core-BD-JWpum.js";
import { n as setWhatsAppRuntime, t as whatsappPlugin } from "../../channel-DNRHYcG8.js";
//#region extensions/whatsapp/index.ts
var whatsapp_default = defineChannelPluginEntry({
	id: "whatsapp",
	name: "WhatsApp",
	description: "WhatsApp channel plugin",
	plugin: whatsappPlugin,
	setRuntime: setWhatsAppRuntime
});
//#endregion
export { whatsapp_default as default, setWhatsAppRuntime, whatsappPlugin };
