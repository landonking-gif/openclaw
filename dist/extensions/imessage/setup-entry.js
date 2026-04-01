import { a as defineSetupPluginEntry } from "../../core-BIzVA7Id.js";
import { a as imessageSetupAdapter } from "../../setup-core-Bne8CdZ9.js";
import { r as imessageSetupWizard, t as createIMessagePluginBase } from "../../shared-CpFvGN1V.js";
//#region extensions/imessage/src/channel.setup.ts
const imessageSetupPlugin = { ...createIMessagePluginBase({
	setupWizard: imessageSetupWizard,
	setup: imessageSetupAdapter
}) };
//#endregion
//#region extensions/imessage/setup-entry.ts
var setup_entry_default = defineSetupPluginEntry(imessageSetupPlugin);
//#endregion
export { setup_entry_default as default, imessageSetupPlugin };
