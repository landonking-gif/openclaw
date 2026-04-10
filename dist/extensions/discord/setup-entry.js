import { a as defineSetupPluginEntry } from "../../core-BD-JWpum.js";
import { r as discordSetupAdapter } from "../../setup-core-pbKR1fA2.js";
import { t as createDiscordPluginBase } from "../../shared-i9d7FdhR.js";
//#region extensions/discord/src/channel.setup.ts
const discordSetupPlugin = { ...createDiscordPluginBase({ setup: discordSetupAdapter }) };
//#endregion
//#region extensions/discord/setup-entry.ts
var setup_entry_default = defineSetupPluginEntry(discordSetupPlugin);
//#endregion
export { setup_entry_default as default, discordSetupPlugin };
