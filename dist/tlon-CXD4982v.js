import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./setup-helpers-CqDPDxCm.js";
import "./status-helpers-CtC8UKdv.js";
import "./ssrf-C8Ew-J28.js";
import "./fetch-guard-4gkAtfeh.js";
import "./runtime-C8T6q1m8.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
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
