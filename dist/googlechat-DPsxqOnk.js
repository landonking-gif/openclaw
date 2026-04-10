import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.providers-core-D0wGIf0e.js";
import "./registry-C0lW5OhB.js";
import "./setup-helpers-K3E4OVw3.js";
import "./status-helpers-DyX-NNWd.js";
import "./outbound-media-C4Vs3Wfg.js";
import "./fetch-guard-C_UnNY7U.js";
import "./web-media-CkaAIY0r.js";
import "./web-media-DXbVsiyW.js";
import "./common-DbyForkU.js";
import { n as resolveChannelGroupRequireMention } from "./group-policy-DD8wDxR4.js";
import "./setup-wizard-helpers-058c-tIO.js";
import "./dm-policy-shared-DGVIISSQ.js";
import "./channel-policy-XbkOLNBx.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
import "./webhook-ingress-BWcTICaS.js";
//#region src/plugin-sdk/googlechat.ts
function resolveGoogleChatGroupRequireMention(params) {
	return resolveChannelGroupRequireMention({
		cfg: params.cfg,
		channel: "googlechat",
		groupId: params.groupId,
		accountId: params.accountId
	});
}
const googlechatSetup = createOptionalChannelSetupSurface({
	channel: "googlechat",
	label: "Google Chat",
	npmSpec: "@openclaw/googlechat",
	docsPath: "/channels/googlechat"
});
const googlechatSetupAdapter = googlechatSetup.setupAdapter;
const googlechatSetupWizard = googlechatSetup.setupWizard;
//#endregion
export { googlechatSetupWizard as n, resolveGoogleChatGroupRequireMention as r, googlechatSetupAdapter as t };
