import { n as fetchWithSsrFGuard } from "./fetch-guard-C_UnNY7U.js";
import "./ssrf-runtime-LMJvSghd.js";
import { s as DEFAULT_FETCH_TIMEOUT_MS } from "./oauth.shared-5vmmiRyK.js";
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
