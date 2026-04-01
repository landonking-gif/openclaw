import { t as definePluginEntry } from "../../plugin-entry-C2JEeAkR.js";
import { t as createSearxngWebSearchProvider } from "../../searxng-search-provider-B-jjiSyy.js";
//#region extensions/searxng/index.ts
var searxng_default = definePluginEntry({
	id: "searxng",
	name: "SearXNG Plugin",
	description: "Bundled SearXNG web search plugin",
	register(api) {
		api.registerWebSearchProvider(createSearxngWebSearchProvider());
	}
});
//#endregion
export { searxng_default as default };
