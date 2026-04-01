import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.providers-core-DtTlbX_O.js";
import "./registry-C0lW5OhB.js";
import "./setup-helpers-CqDPDxCm.js";
import "./status-helpers-CtC8UKdv.js";
import "./outbound-media-DEmL-jK-.js";
import "./fetch-guard-4gkAtfeh.js";
import "./web-media-Bhty-vWo.js";
import "./web-media-Dsjd8V7i.js";
import "./common-DotKVabV.js";
import { n as resolveChannelGroupRequireMention } from "./group-policy-C6p_uQdV.js";
import "./setup-wizard-helpers-UVbGobAo.js";
import "./dm-policy-shared-DPpYfcGE.js";
import "./channel-policy-DoPDTANw.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
import "./webhook-ingress-ByU3Ayhm.js";
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
