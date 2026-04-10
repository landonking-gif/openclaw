import "./redact-BDinS1q9.js";
import "./links-v2wQeP8P.js";
import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.agent-runtime-DGBVnG3C.js";
import "./net-CTrWm98z.js";
import "./setup-helpers-K3E4OVw3.js";
import "./channel-plugin-common-D4Y28cqs.js";
import "./status-helpers-DyX-NNWd.js";
import "./outbound-media-C4Vs3Wfg.js";
import "./fetch-guard-C_UnNY7U.js";
import "./web-media-CkaAIY0r.js";
import "./json-store-D33wkYyO.js";
import "./common-DbyForkU.js";
import "./session-binding-service-BWEN0bmc.js";
import "./identity-xhqJmrDg.js";
import "./typing-C0wBbHXZ.js";
import "./run-command-ST-J5R0N.js";
import "./secret-input-BQYGV6z8.js";
import "./setup-wizard-helpers-058c-tIO.js";
import "./runtime-CHfkI0WR.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
import "./setup-group-access-Dato5hRK.js";
import "./matrix-thread-bindings-Bp52PJhx.js";
import "./matrix-helper-CXA1H0rE.js";
import "./matrix-runtime-surface-Ce7cSfVA.js";
import "./matrix-surface-DFkKjfSj.js";
//#region src/plugin-sdk/matrix.ts
const matrixSetup = createOptionalChannelSetupSurface({
	channel: "matrix",
	label: "Matrix",
	npmSpec: "@openclaw/matrix",
	docsPath: "/channels/matrix"
});
const matrixSetupWizard = matrixSetup.setupWizard;
const matrixSetupAdapter = matrixSetup.setupAdapter;
//#endregion
export { matrixSetupWizard as n, matrixSetupAdapter as t };
