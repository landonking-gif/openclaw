import { a as defineSetupPluginEntry } from "../../core-BD-JWpum.js";
import { s as signalSetupAdapter } from "../../setup-core-B-zLZrak.js";
import { i as signalSetupWizard, t as createSignalPluginBase } from "../../shared-C9AqQW51.js";
//#region extensions/signal/src/channel.setup.ts
const signalSetupPlugin = { ...createSignalPluginBase({
	setupWizard: signalSetupWizard,
	setup: signalSetupAdapter
}) };
//#endregion
//#region extensions/signal/setup-entry.ts
var setup_entry_default = defineSetupPluginEntry(signalSetupPlugin);
//#endregion
export { setup_entry_default as default, signalSetupPlugin };
