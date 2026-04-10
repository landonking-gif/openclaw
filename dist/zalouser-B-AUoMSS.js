import "./tmp-openclaw-dir-Day5KPIY.js";
import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.agent-runtime-DGBVnG3C.js";
import "./setup-helpers-K3E4OVw3.js";
import "./status-helpers-DyX-NNWd.js";
import "./outbound-media-C4Vs3Wfg.js";
import "./setup-wizard-helpers-058c-tIO.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
import "./command-auth-Cm9A1xQ-.js";
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
