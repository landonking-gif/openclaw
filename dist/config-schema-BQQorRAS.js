import { r as buildChannelConfigSchema } from "./config-schema-Cl_s6UTH.js";
import { o as MSTeamsConfigSchema } from "./zod-schema.providers-core-D0wGIf0e.js";
import "./channel-config-schema-RCS64Y4n.js";
//#endregion
//#region extensions/msteams/src/config-schema.ts
const MSTeamsChannelConfigSchema = buildChannelConfigSchema(MSTeamsConfigSchema, { uiHints: {
	"": {
		label: "MS Teams",
		help: "Microsoft Teams channel provider configuration and provider-specific policy toggles. Use this section to isolate Teams behavior from other enterprise chat providers."
	},
	configWrites: {
		label: "MS Teams Config Writes",
		help: "Allow Microsoft Teams to write config in response to channel events/commands (default: true)."
	}
} });
//#endregion
export { MSTeamsChannelConfigSchema as t };
