import { t as createSubsystemLogger } from "./subsystem-CJEvHE2o.js";
import { Jt as withBundledPluginEnablementCompat, qt as withBundledPluginAllowlistCompat } from "./io-CHHRUM9X.js";
import { a as withBundledProviderVitestCompat, r as resolveEnabledProviderPluginIds, t as resolveBundledProviderCompatPluginIds } from "./providers-CIsVVFYY.js";
import { t as applyPluginAutoEnable } from "./plugin-auto-enable-m0r_ES9X.js";
import { n as loadOpenClawPlugins } from "./loader-BrGpIitI.js";
import { t as createPluginLoaderLogger } from "./logger-BNmmh5Qj.js";
//#region src/plugins/providers.runtime.ts
const log = createSubsystemLogger("plugins");
function resolvePluginProviders(params) {
	const env = params.env ?? process.env;
	const autoEnabledConfig = params.config !== void 0 ? applyPluginAutoEnable({
		config: params.config,
		env
	}).config : void 0;
	const bundledProviderCompatPluginIds = params.bundledProviderAllowlistCompat || params.bundledProviderVitestCompat ? resolveBundledProviderCompatPluginIds({
		config: autoEnabledConfig,
		workspaceDir: params.workspaceDir,
		env,
		onlyPluginIds: params.onlyPluginIds
	}) : [];
	const maybeAllowlistCompat = params.bundledProviderAllowlistCompat ? withBundledPluginAllowlistCompat({
		config: autoEnabledConfig,
		pluginIds: bundledProviderCompatPluginIds
	}) : autoEnabledConfig;
	const allowlistCompatConfig = params.bundledProviderAllowlistCompat ? withBundledPluginEnablementCompat({
		config: maybeAllowlistCompat,
		pluginIds: bundledProviderCompatPluginIds
	}) : maybeAllowlistCompat;
	const config = params.bundledProviderVitestCompat ? withBundledProviderVitestCompat({
		config: allowlistCompatConfig,
		pluginIds: bundledProviderCompatPluginIds,
		env
	}) : allowlistCompatConfig;
	const providerPluginIds = resolveEnabledProviderPluginIds({
		config,
		workspaceDir: params.workspaceDir,
		env,
		onlyPluginIds: params.onlyPluginIds
	});
	return loadOpenClawPlugins({
		config,
		workspaceDir: params.workspaceDir,
		env,
		onlyPluginIds: providerPluginIds,
		pluginSdkResolution: params.pluginSdkResolution,
		cache: params.cache ?? false,
		activate: params.activate ?? false,
		logger: createPluginLoaderLogger(log)
	}).providers.map((entry) => ({
		...entry.provider,
		pluginId: entry.pluginId
	}));
}
//#endregion
export { resolvePluginProviders as t };
