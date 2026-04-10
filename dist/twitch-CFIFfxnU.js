import "./links-v2wQeP8P.js";
import "./zod-schema.core-ZvH5iguE.js";
import "./config-schema-Cl_s6UTH.js";
import { t as createOptionalChannelSetupSurface } from "./channel-setup-BQmd-t8e.js";
import "./channel-reply-pipeline-BkyGa5kN.js";
//#region src/plugin-sdk/twitch.ts
const twitchSetup = createOptionalChannelSetupSurface({
	channel: "twitch",
	label: "Twitch",
	npmSpec: "@openclaw/twitch"
});
const twitchSetupAdapter = twitchSetup.setupAdapter;
const twitchSetupWizard = twitchSetup.setupWizard;
//#endregion
export { twitchSetupWizard as n, twitchSetupAdapter as t };
