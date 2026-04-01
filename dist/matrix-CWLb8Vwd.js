import "./redact-BDinS1q9.js";
import "./links-v2wQeP8P.js";
import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import "./zod-schema.agent-runtime-DGBVnG3C.js";
import "./net-ufRGHFYT.js";
import "./setup-helpers-CqDPDxCm.js";
import "./channel-plugin-common-CuBVXJMU.js";
import "./status-helpers-CtC8UKdv.js";
import "./outbound-media-DEmL-jK-.js";
import "./fetch-guard-4gkAtfeh.js";
import "./web-media-Bhty-vWo.js";
import "./json-store-BphZeuFy.js";
import "./common-DotKVabV.js";
import "./session-binding-service-Be6fDk2D.js";
import "./identity-BHQcyOKA.js";
import "./typing-oga-3lRM.js";
import "./run-command-CiDnb3ER.js";
import "./secret-input-5Z_M9SDk.js";
import "./setup-wizard-helpers-UVbGobAo.js";
import "./runtime-C8T6q1m8.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BSl-RF59.js";
import "./channel-reply-pipeline-DsxWyaIK.js";
import "./setup-group-access-B_U1rx-1.js";
import "./matrix-thread-bindings-d7d7Sm-f.js";
import "./matrix-helper-BBW9EOta.js";
import "./matrix-runtime-surface-uptU6c_f.js";
import "./matrix-surface-CQ6o8k1Y.js";
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
