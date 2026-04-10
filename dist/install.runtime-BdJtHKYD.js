import { n as isPathInside, r as isPathInsideWithRealpath } from "./scan-paths-CA1kjRy9.js";
import { i as validateRegistryNpmSpec } from "./npm-registry-spec-tH1Gnzy2.js";
import { a as resolveArchiveKind, i as readJsonFile, r as fileExists } from "./archive-DSI7xoOx.js";
import { r as resolveArchiveSourcePath } from "./install-source-utils-7OFIBoc9.js";
import { i as withExtractedArchiveRoot, n as installPackageDirWithManifestDeps, r as resolveExistingInstallPath, t as installPackageDir } from "./install-package-dir-yEesAztf.js";
import { a as finalizeNpmSpecArchiveInstall, i as resolveTimedInstallModeOptions, n as resolveCanonicalInstallTarget, o as installFromNpmSpecArchiveWithInstaller, r as resolveInstallModeOptions, t as ensureInstallTargetAvailable } from "./install-target-CvhxNBEF.js";
//#region src/infra/install-from-npm-spec.ts
async function installFromValidatedNpmSpecArchive(params) {
	const spec = params.spec.trim();
	const specError = validateRegistryNpmSpec(spec);
	if (specError) return {
		ok: false,
		error: specError
	};
	return finalizeNpmSpecArchiveInstall(await installFromNpmSpecArchiveWithInstaller({
		tempDirPrefix: params.tempDirPrefix,
		spec,
		timeoutMs: params.timeoutMs,
		expectedIntegrity: params.expectedIntegrity,
		onIntegrityDrift: params.onIntegrityDrift,
		warn: params.warn,
		installFromArchive: params.installFromArchive,
		archiveInstallParams: params.archiveInstallParams
	}));
}
//#endregion
export { ensureInstallTargetAvailable, fileExists, installFromValidatedNpmSpecArchive, installPackageDir, installPackageDirWithManifestDeps, isPathInside, isPathInsideWithRealpath, readJsonFile, resolveArchiveKind, resolveArchiveSourcePath, resolveCanonicalInstallTarget, resolveExistingInstallPath, resolveInstallModeOptions, resolveTimedInstallModeOptions, withExtractedArchiveRoot };
