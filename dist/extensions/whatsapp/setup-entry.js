import { n as resolveWhatsAppGroupIntroHint } from "../../whatsapp-shared-CA22Mdrl.js";
import { a as defineSetupPluginEntry } from "../../core-BIzVA7Id.js";
import { n as resolveWhatsAppGroupToolPolicy, t as resolveWhatsAppGroupRequireMention } from "../../group-policy-C4JtbCTy.js";
import { t as whatsappSetupAdapter } from "../../setup-core-D_HrUScL.js";
import { i as whatsappSetupWizardProxy, n as createWhatsAppPluginBase } from "../../shared-Bj4Em899.js";
import "../../api-DIjIEfrf.js";
import { d as webAuthExists } from "../../auth-store-Dbd7ODix.js";
//#region extensions/whatsapp/src/channel.setup.ts
const whatsappSetupPlugin = { ...createWhatsAppPluginBase({
	groups: {
		resolveRequireMention: resolveWhatsAppGroupRequireMention,
		resolveToolPolicy: resolveWhatsAppGroupToolPolicy,
		resolveGroupIntroHint: resolveWhatsAppGroupIntroHint
	},
	setupWizard: whatsappSetupWizardProxy,
	setup: whatsappSetupAdapter,
	isConfigured: async (account) => await webAuthExists(account.authDir)
}) };
//#endregion
//#region extensions/whatsapp/setup-entry.ts
var setup_entry_default = defineSetupPluginEntry(whatsappSetupPlugin);
//#endregion
export { setup_entry_default as default, whatsappSetupPlugin };
