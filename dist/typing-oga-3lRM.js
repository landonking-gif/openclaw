import { t as getChannelPlugin } from "./registry-DWiJhWZh.js";
import "./plugins-B9ydw93g.js";
import { a as resolveIdentityName, r as resolveEffectiveMessagesConfig } from "./identity-BHQcyOKA.js";
import { t as extractShortModelName } from "./response-prefix-template-CyYxP5iv.js";
import { n as createTypingKeepaliveLoop, t as createTypingStartGuard } from "./typing-start-guard-BAmPTA9-.js";
//#region src/channels/reply-prefix.ts
function createReplyPrefixContext(params) {
	const { cfg, agentId } = params;
	const prefixContext = { identityName: resolveIdentityName(cfg, agentId) };
	const onModelSelected = (ctx) => {
		prefixContext.provider = ctx.provider;
		prefixContext.model = extractShortModelName(ctx.model);
		prefixContext.modelFull = `${ctx.provider}/${ctx.model}`;
		prefixContext.thinkingLevel = ctx.thinkLevel ?? "off";
	};
	return {
		prefixContext,
		responsePrefix: resolveEffectiveMessagesConfig(cfg, agentId, {
			channel: params.channel,
			accountId: params.accountId
		}).responsePrefix,
		enableSlackInteractiveReplies: params.channel ? getChannelPlugin(params.channel)?.messaging?.enableInteractiveReplies?.({
			cfg,
			accountId: params.accountId
		}) ?? void 0 : void 0,
		responsePrefixContextProvider: () => prefixContext,
		onModelSelected
	};
}
function createReplyPrefixOptions(params) {
	const { responsePrefix, enableSlackInteractiveReplies, responsePrefixContextProvider, onModelSelected } = createReplyPrefixContext(params);
	return {
		responsePrefix,
		enableSlackInteractiveReplies,
		responsePrefixContextProvider,
		onModelSelected
	};
}
//#endregion
//#region src/channels/typing.ts
function createTypingCallbacks(params) {
	const stop = params.stop;
	const keepaliveIntervalMs = params.keepaliveIntervalMs ?? 3e3;
	const maxConsecutiveFailures = Math.max(1, params.maxConsecutiveFailures ?? 2);
	const maxDurationMs = params.maxDurationMs ?? 6e4;
	let stopSent = false;
	let closed = false;
	let ttlTimer;
	const startGuard = createTypingStartGuard({
		isSealed: () => closed,
		onStartError: params.onStartError,
		maxConsecutiveFailures,
		onTrip: () => {
			keepaliveLoop.stop();
		}
	});
	const fireStart = async () => {
		await startGuard.run(() => params.start());
	};
	const keepaliveLoop = createTypingKeepaliveLoop({
		intervalMs: keepaliveIntervalMs,
		onTick: fireStart
	});
	const startTtlTimer = () => {
		if (maxDurationMs <= 0) return;
		clearTtlTimer();
		ttlTimer = setTimeout(() => {
			if (!closed) {
				console.warn(`[typing] TTL exceeded (${maxDurationMs}ms), auto-stopping typing indicator`);
				fireStop();
			}
		}, maxDurationMs);
	};
	const clearTtlTimer = () => {
		if (ttlTimer) {
			clearTimeout(ttlTimer);
			ttlTimer = void 0;
		}
	};
	const onReplyStart = async () => {
		if (closed) return;
		stopSent = false;
		startGuard.reset();
		keepaliveLoop.stop();
		clearTtlTimer();
		await fireStart();
		if (startGuard.isTripped()) return;
		keepaliveLoop.start();
		startTtlTimer();
	};
	const fireStop = () => {
		closed = true;
		keepaliveLoop.stop();
		clearTtlTimer();
		if (!stop || stopSent) return;
		stopSent = true;
		stop().catch((err) => (params.onStopError ?? params.onStartError)(err));
	};
	return {
		onReplyStart,
		onIdle: fireStop,
		onCleanup: fireStop
	};
}
//#endregion
export { createReplyPrefixContext as n, createReplyPrefixOptions as r, createTypingCallbacks as t };
