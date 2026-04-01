import { t as loadWebMedia } from "./web-media-Bhty-vWo.js";
import "./web-media-Dsjd8V7i.js";
//#region src/media/load-options.ts
function resolveOutboundMediaLocalRoots(mediaLocalRoots) {
	return mediaLocalRoots && mediaLocalRoots.length > 0 ? mediaLocalRoots : void 0;
}
function resolveOutboundMediaAccess(params = {}) {
	const localRoots = resolveOutboundMediaLocalRoots(params.mediaAccess?.localRoots ?? params.mediaLocalRoots);
	const readFile = params.mediaAccess?.readFile ?? params.mediaReadFile;
	const workspaceDir = params.mediaAccess?.workspaceDir;
	if (!localRoots && !readFile && !workspaceDir) return;
	return {
		...localRoots ? { localRoots } : {},
		...readFile ? { readFile } : {},
		...workspaceDir ? { workspaceDir } : {}
	};
}
function buildOutboundMediaLoadOptions(params = {}) {
	const mediaAccess = resolveOutboundMediaAccess(params);
	const workspaceDir = mediaAccess?.workspaceDir ?? params.workspaceDir;
	if (mediaAccess?.readFile) return {
		...params.maxBytes !== void 0 ? { maxBytes: params.maxBytes } : {},
		localRoots: "any",
		readFile: mediaAccess.readFile,
		hostReadCapability: true,
		...params.optimizeImages !== void 0 ? { optimizeImages: params.optimizeImages } : {},
		...workspaceDir ? { workspaceDir } : {}
	};
	const localRoots = mediaAccess?.localRoots;
	return {
		...params.maxBytes !== void 0 ? { maxBytes: params.maxBytes } : {},
		...localRoots ? { localRoots } : {},
		...params.optimizeImages !== void 0 ? { optimizeImages: params.optimizeImages } : {},
		...workspaceDir ? { workspaceDir } : {}
	};
}
//#endregion
//#region src/plugin-sdk/outbound-media.ts
/** Load outbound media from a remote URL or approved local path using the shared web-media policy. */
async function loadOutboundMediaFromUrl(mediaUrl, options = {}) {
	return await loadWebMedia(mediaUrl, buildOutboundMediaLoadOptions({
		maxBytes: options.maxBytes,
		mediaAccess: options.mediaAccess,
		mediaLocalRoots: options.mediaLocalRoots,
		mediaReadFile: options.mediaReadFile
	}));
}
//#endregion
export { resolveOutboundMediaLocalRoots as i, buildOutboundMediaLoadOptions as n, resolveOutboundMediaAccess as r, loadOutboundMediaFromUrl as t };
