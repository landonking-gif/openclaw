import { t as resolvePluginProviders } from "./providers.runtime-DON49YNM.js";
import { i as runProviderModelSelectedHook, n as resolveProviderPluginChoice } from "./provider-wizard-CVRAVbPN.js";
import { n as resolveProviderModelPickerFlowContributions, r as resolveProviderModelPickerFlowEntries } from "./provider-flow-qdSOb3_y.js";
import { n as runProviderPluginAuthMethod } from "./provider-auth-choice-CAArMa7r.js";
//#region src/commands/model-picker.runtime.ts
const modelPickerRuntime = {
	resolveProviderModelPickerContributions: resolveProviderModelPickerFlowContributions,
	resolveProviderModelPickerEntries: resolveProviderModelPickerFlowEntries,
	resolveProviderPluginChoice,
	runProviderModelSelectedHook,
	resolvePluginProviders,
	runProviderPluginAuthMethod
};
//#endregion
export { modelPickerRuntime };
