import { a as createLazyRuntimeSurface } from "./lazy-runtime-DShlDMvu.js";
//#region src/cli/outbound-send-mapping.ts
const LEGACY_SOURCE_TO_CHANNEL = {
	sendMessageWhatsApp: "whatsapp",
	sendMessageTelegram: "telegram",
	sendMessageDiscord: "discord",
	sendMessageSlack: "slack",
	sendMessageSignal: "signal",
	sendMessageIMessage: "imessage"
};
const CHANNEL_TO_LEGACY_DEP_KEY = {
	whatsapp: "sendWhatsApp",
	telegram: "sendTelegram",
	discord: "sendDiscord",
	slack: "sendSlack",
	signal: "sendSignal",
	imessage: "sendIMessage"
};
/**
* Pass CLI send sources through as-is — both CliOutboundSendSource and
* OutboundSendDeps are now channel-ID-keyed records.
*/
function createOutboundSendDepsFromCliSource(deps) {
	const outbound = { ...deps };
	for (const [legacySourceKey, channelId] of Object.entries(LEGACY_SOURCE_TO_CHANNEL)) {
		const sourceValue = deps[legacySourceKey];
		if (sourceValue !== void 0 && outbound[channelId] === void 0) outbound[channelId] = sourceValue;
	}
	for (const [channelId, legacyDepKey] of Object.entries(CHANNEL_TO_LEGACY_DEP_KEY)) {
		const sourceValue = outbound[channelId];
		if (sourceValue !== void 0 && outbound[legacyDepKey] === void 0) outbound[legacyDepKey] = sourceValue;
	}
	return outbound;
}
//#endregion
//#region src/cli/deps.ts
const senderCache = /* @__PURE__ */ new Map();
/**
* Create a lazy-loading send function proxy for a channel.
* The channel's module is loaded on first call and cached for reuse.
*/
function createLazySender(channelId, loader) {
	const loadRuntimeSend = createLazyRuntimeSurface(loader, ({ runtimeSend }) => runtimeSend);
	return async (...args) => {
		let cached = senderCache.get(channelId);
		if (!cached) {
			cached = loadRuntimeSend();
			senderCache.set(channelId, cached);
		}
		return await (await cached).sendMessage(...args);
	};
}
function createDefaultDeps() {
	return {
		whatsapp: createLazySender("whatsapp", () => import("./whatsapp-CMk8YYDg.js")),
		telegram: createLazySender("telegram", () => import("./telegram-DqwXyefe.js")),
		discord: createLazySender("discord", () => import("./discord-BgCtvbub.js")),
		slack: createLazySender("slack", () => import("./slack-B6JiKs6H.js")),
		signal: createLazySender("signal", () => import("./signal-Bw_O9DMl.js")),
		imessage: createLazySender("imessage", () => import("./imessage-C9oIBbL4.js"))
	};
}
function createOutboundSendDeps(deps) {
	return createOutboundSendDepsFromCliSource(deps);
}
//#endregion
export { createOutboundSendDeps as n, createOutboundSendDepsFromCliSource as r, createDefaultDeps as t };
