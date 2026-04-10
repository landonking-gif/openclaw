import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./status-helpers-DyX-NNWd.js";
import "./ssrf-CyUk4uMr.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
import "./webhook-memory-guards-Bx5okKue.js";
import "./direct-dm-DB_czfqF.js";
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
