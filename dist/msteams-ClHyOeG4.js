import "./utils-ozuUQtXc.js";
import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.providers-core-D0wGIf0e.js";
import "./file-lock-B4wypLkV.js";
import "./status-helpers-DyX-NNWd.js";
import "./outbound-media-C4Vs3Wfg.js";
import "./mime-DPd6FabF.js";
import "./ssrf-CyUk4uMr.js";
import "./fetch-guard-C_UnNY7U.js";
import "./web-media-DXbVsiyW.js";
import "./json-store-D33wkYyO.js";
import "./tokens-DeETngSc.js";
import "./store-DQDdIFNb.js";
import "./setup-wizard-helpers-058c-tIO.js";
import "./dm-policy-shared-DGVIISSQ.js";
import "./history-CYQfJBwi.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
import "./ssrf-policy-DYQzTQgE.js";
import "./inbound-reply-dispatch-CHXXhHYA.js";
import "./session-envelope-CwqrxyiL.js";
//#region src/plugin-sdk/msteams.ts
const msteamsSetup = createOptionalChannelSetupSurface({
	channel: "msteams",
	label: "Microsoft Teams",
	npmSpec: "@openclaw/msteams",
	docsPath: "/channels/msteams"
});
const msteamsSetupWizard = msteamsSetup.setupWizard;
const msteamsSetupAdapter = msteamsSetup.setupAdapter;
//#endregion
export { msteamsSetupWizard as n, msteamsSetupAdapter as t };
