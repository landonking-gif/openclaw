import "./utils-ozuUQtXc.js";
import "./links-v2wQeP8P.js";
import "./setup-helpers-K3E4OVw3.js";
import "./setup-binary-C6UFXOI6.js";
import "./signal-cli-install-DbGdzGWu.js";
import "./setup-wizard-proxy-iyMDEVdb.js";
import "./setup-wizard-helpers-058c-tIO.js";
//#region src/plugin-sdk/resolution-notes.ts
/** Format a short note that separates successfully resolved targets from unresolved passthrough values. */
function formatResolvedUnresolvedNote(params) {
	if (params.resolved.length === 0 && params.unresolved.length === 0) return;
	return [params.resolved.length > 0 ? `Resolved: ${params.resolved.join(", ")}` : void 0, params.unresolved.length > 0 ? `Unresolved (kept as typed): ${params.unresolved.join(", ")}` : void 0].filter(Boolean).join("\n");
}
//#endregion
export { formatResolvedUnresolvedNote as t };
