import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./setup-helpers-K3E4OVw3.js";
import "./status-helpers-DyX-NNWd.js";
import "./ssrf-CyUk4uMr.js";
import "./fetch-guard-C_UnNY7U.js";
import "./runtime-CHfkI0WR.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
//#region src/plugin-sdk/tlon.ts
const tlonSetup = createOptionalChannelSetupSurface({
	channel: "tlon",
	label: "Tlon",
	npmSpec: "@openclaw/tlon",
	docsPath: "/channels/tlon"
});
const tlonSetupAdapter = tlonSetup.setupAdapter;
const tlonSetupWizard = tlonSetup.setupWizard;
//#endregion
export { tlonSetupWizard as n, tlonSetupAdapter as t };
