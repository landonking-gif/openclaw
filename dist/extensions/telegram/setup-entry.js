import { a as defineSetupPluginEntry } from "../../core-BD-JWpum.js";
import { n as telegramSetupAdapter, t as telegramSetupWizard } from "../../setup-surface-Dd0CXvl5.js";
import { t as createTelegramPluginBase } from "../../shared-DB1p37D7.js";
//#region extensions/telegram/src/channel.setup.ts
const telegramSetupPlugin = { ...createTelegramPluginBase({
	setupWizard: telegramSetupWizard,
	setup: telegramSetupAdapter
}) };
//#endregion
//#region extensions/telegram/setup-entry.ts
var setup_entry_default = defineSetupPluginEntry(telegramSetupPlugin);
//#endregion
export { setup_entry_default as default, telegramSetupPlugin };
