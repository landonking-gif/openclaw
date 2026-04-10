import { t as resolvePluginProviders } from "./providers.runtime-BbZCx93w.js";
import { i as runProviderModelSelectedHook, n as resolveProviderPluginChoice } from "./provider-wizard-CE5Sp-XL.js";
import { n as resolveProviderModelPickerFlowContributions, r as resolveProviderModelPickerFlowEntries } from "./provider-flow-Cg9N5Vqy.js";
import { n as runProviderPluginAuthMethod } from "./provider-auth-choice-_7Lad_AY.js";
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
