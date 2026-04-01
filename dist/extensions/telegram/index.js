import { i as defineChannelPluginEntry } from "../../core-BIzVA7Id.js";
import { n as setTelegramRuntime, t as telegramPlugin } from "../../channel-DnrW2zsi.js";
//#region extensions/telegram/index.ts
var telegram_default = defineChannelPluginEntry({
	id: "telegram",
	name: "Telegram",
	description: "Telegram channel plugin",
	plugin: telegramPlugin,
	setRuntime: setTelegramRuntime
});
//#endregion
export { telegram_default as default, setTelegramRuntime, telegramPlugin };
