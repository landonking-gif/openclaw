import { n as resolveWhatsAppGroupIntroHint } from "../../whatsapp-shared-B-MU6Ay2.js";
import { a as defineSetupPluginEntry } from "../../core-BD-JWpum.js";
import { n as resolveWhatsAppGroupToolPolicy, t as resolveWhatsAppGroupRequireMention } from "../../group-policy-CscXdDWm.js";
import { t as whatsappSetupAdapter } from "../../setup-core-DLxE_0qY.js";
import { i as whatsappSetupWizardProxy, n as createWhatsAppPluginBase } from "../../shared-CMpMuSQj.js";
import "../../api-wZTa6ocm.js";
import { d as webAuthExists } from "../../auth-store-BsnL4qFT.js";
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
