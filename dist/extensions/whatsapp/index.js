import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { n as setWhatsAppRuntime, t as whatsappPlugin } from "../../channel-C2R_gQTx.js";
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
