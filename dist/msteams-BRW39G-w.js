import "./utils-ozuUQtXc.js";
import "./links-v2wQeP8P.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.providers-core-DtTlbX_O.js";
import "./file-lock-B6EjeH4S.js";
import "./status-helpers-CtC8UKdv.js";
import "./outbound-media-DEmL-jK-.js";
import "./mime-Dm-Z3ymz.js";
import "./ssrf-C8Ew-J28.js";
import "./fetch-guard-4gkAtfeh.js";
import "./web-media-Dsjd8V7i.js";
import "./json-store-BphZeuFy.js";
import "./tokens-CKy9ywkv.js";
import "./store-BwkKDkHh.js";
import "./setup-wizard-helpers-UVbGobAo.js";
import "./dm-policy-shared-DPpYfcGE.js";
import "./history-hQFGL-sK.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
import "./ssrf-policy-nXVGepAD.js";
import "./inbound-reply-dispatch-Dz6wzifT.js";
import "./session-envelope-BQdZf0Rn.js";
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
