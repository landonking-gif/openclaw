import { n as fetchWithSsrFGuard } from "./fetch-guard-4gkAtfeh.js";
import "./ssrf-runtime-VeuSJJww.js";
import { s as DEFAULT_FETCH_TIMEOUT_MS } from "./oauth.shared-CdwLdlho.js";
//#region extensions/google/oauth.http.ts
async function fetchWithTimeout(url, init, timeoutMs = DEFAULT_FETCH_TIMEOUT_MS) {
	const { response, release } = await fetchWithSsrFGuard({
		url,
		init,
		timeoutMs
	});
	try {
		const body = await response.arrayBuffer();
		return new Response(body, {
			status: response.status,
			statusText: response.statusText,
			headers: response.headers
		});
	} finally {
		await release();
	}
}
//#endregion
export { fetchWithTimeout as t };
