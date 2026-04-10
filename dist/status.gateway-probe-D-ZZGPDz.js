import { r as resolveGatewayProbeAuthSafeWithSecretInputs } from "./probe-auth-DGoT7JUw.js";
import { t as pickGatewaySelfPresence } from "./gateway-presence-DapaSL7s.js";
//#region src/commands/status.gateway-probe.ts
async function resolveGatewayProbeAuthResolution(cfg) {
	return resolveGatewayProbeAuthSafeWithSecretInputs({
		cfg,
		mode: cfg.gateway?.mode === "remote" ? "remote" : "local",
		env: process.env
	});
}
async function resolveGatewayProbeAuth(cfg) {
	return (await resolveGatewayProbeAuthResolution(cfg)).auth;
}
//#endregion
export { pickGatewaySelfPresence, resolveGatewayProbeAuth, resolveGatewayProbeAuthResolution };
