import { r as resolveGatewayService } from "./service-CXcGwK73.js";
import { t as resolveNodeService } from "./node-service-Chtol5UN.js";
import { t as formatDaemonRuntimeShort } from "./status.format-CfWVUCiJ.js";
import { t as readServiceStatusSummary } from "./status.service-summary-BUkgLzDJ.js";
//#region src/commands/status.daemon.ts
async function buildDaemonStatusSummary(serviceLabel) {
	const summary = await readServiceStatusSummary(serviceLabel === "gateway" ? resolveGatewayService() : resolveNodeService(), serviceLabel === "gateway" ? "Daemon" : "Node");
	return {
		label: summary.label,
		installed: summary.installed,
		loaded: summary.loaded,
		managedByOpenClaw: summary.managedByOpenClaw,
		externallyManaged: summary.externallyManaged,
		loadedText: summary.loadedText,
		runtimeShort: formatDaemonRuntimeShort(summary.runtime)
	};
}
async function getDaemonStatusSummary() {
	return await buildDaemonStatusSummary("gateway");
}
async function getNodeDaemonStatusSummary() {
	return await buildDaemonStatusSummary("node");
}
//#endregion
export { getNodeDaemonStatusSummary as n, getDaemonStatusSummary as t };
