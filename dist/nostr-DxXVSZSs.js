import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./status-helpers-CtC8UKdv.js";
import "./ssrf-C8Ew-J28.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
import "./webhook-memory-guards-xoT8oW6-.js";
import "./direct-dm-BO6pMN7j.js";
//#region src/plugin-sdk/nostr.ts
const nostrSetup = createOptionalChannelSetupSurface({
	channel: "nostr",
	label: "Nostr",
	npmSpec: "@openclaw/nostr",
	docsPath: "/channels/nostr"
});
const nostrSetupAdapter = nostrSetup.setupAdapter;
const nostrSetupWizard = nostrSetup.setupWizard;
//#endregion
export { nostrSetupWizard as n, nostrSetupAdapter as t };
