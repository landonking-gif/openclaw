import { t as definePluginEntry } from "../../plugin-entry-C2JEeAkR.js";
import { t as createDuckDuckGoWebSearchProvider } from "../../ddg-search-provider-BuDFRF_v.js";
//#region extensions/duckduckgo/index.ts
var duckduckgo_default = definePluginEntry({
	id: "duckduckgo",
	name: "DuckDuckGo Plugin",
	description: "Bundled DuckDuckGo web search plugin",
	register(api) {
		api.registerWebSearchProvider(createDuckDuckGoWebSearchProvider());
	}
});
//#endregion
export { duckduckgo_default as default };
