import "./tmp-openclaw-dir-Day5KPIY.js";
import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.agent-runtime-DGBVnG3C.js";
import "./setup-helpers-CqDPDxCm.js";
import "./status-helpers-CtC8UKdv.js";
import "./outbound-media-DEmL-jK-.js";
import "./setup-wizard-helpers-UVbGobAo.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
import "./command-auth-Dfd9saHb.js";
//#region src/plugin-sdk/zalouser.ts
const zalouserSetup = createOptionalChannelSetupSurface({
	channel: "zalouser",
	label: "Zalo Personal",
	npmSpec: "@openclaw/zalouser",
	docsPath: "/channels/zalouser"
});
const zalouserSetupAdapter = zalouserSetup.setupAdapter;
const zalouserSetupWizard = zalouserSetup.setupWizard;
//#endregion
export { zalouserSetupWizard as n, zalouserSetupAdapter as t };
