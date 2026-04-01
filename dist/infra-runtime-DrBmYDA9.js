import "./errors-Bs2h5H8p.js";
import { t as createSubsystemLogger } from "./subsystem-CJEvHE2o.js";
import "./tmp-openclaw-dir-Day5KPIY.js";
import "./env-CjUKd1aw.js";
import "./file-lock-ki4S5WEB.js";
import "./fs-safe-DTvsfd9L.js";
import "./ssrf-C8Ew-J28.js";
import "./fetch-guard-4gkAtfeh.js";
import "./system-events-Dm76CSl1.js";
import "./heartbeat-visibility-y99mIlg-.js";
import "./transport-ready-jzG85C_H.js";
import "./retry-DPB8cvxs.js";
import "./undici-global-dispatcher-Dj9ag7qf.js";
import "./exec-approvals-CzqGD3AZ.js";
import "./proxy-fetch-BCicYs0k.js";
import "./secret-file-CJy1G8b5.js";
import "./exec-approval-session-target-kgcdF1mk.js";
import "./identity-CpzPR2eZ.js";
import { t as createOperatorApprovalsGatewayClient } from "./operator-approvals-client-2rrv0NIn.js";
import "./retry-policy-C5G1UDJ-.js";
import "./ssrf-policy-nXVGepAD.js";
//#region src/infra/exec-approval-channel-runtime.ts
function createExecApprovalChannelRuntime(adapter) {
	const log = createSubsystemLogger(adapter.label);
	const nowMs = adapter.nowMs ?? Date.now;
	const eventKinds = new Set(adapter.eventKinds ?? ["exec"]);
	const pending = /* @__PURE__ */ new Map();
	let gatewayClient = null;
	let started = false;
	let shouldRun = false;
	let startPromise = null;
	const spawn = (label, promise) => {
		promise.catch((err) => {
			const message = err instanceof Error ? err.message : String(err);
			log.error(`${label}: ${message}`);
		});
	};
	const clearPendingEntry = (approvalId) => {
		const entry = pending.get(approvalId);
		if (!entry) return null;
		pending.delete(approvalId);
		if (entry.timeoutId) clearTimeout(entry.timeoutId);
		return entry;
	};
	const handleExpired = async (approvalId) => {
		const entry = clearPendingEntry(approvalId);
		if (!entry) return;
		log.debug(`expired ${approvalId}`);
		await adapter.finalizeExpired?.({
			request: entry.request,
			entries: entry.entries
		});
	};
	const handleRequested = async (request) => {
		if (!adapter.shouldHandle(request)) return;
		log.debug(`received request ${request.id}`);
		const existing = pending.get(request.id);
		if (existing?.timeoutId) clearTimeout(existing.timeoutId);
		const entry = {
			request,
			entries: [],
			timeoutId: null,
			delivering: true,
			pendingResolution: null
		};
		pending.set(request.id, entry);
		let entries;
		try {
			entries = await adapter.deliverRequested(request);
		} catch (err) {
			if (pending.get(request.id) === entry) clearPendingEntry(request.id);
			throw err;
		}
		if (pending.get(request.id) !== entry) return;
		if (!entries.length) {
			pending.delete(request.id);
			return;
		}
		entry.entries = entries;
		entry.delivering = false;
		if (entry.pendingResolution) {
			pending.delete(request.id);
			log.debug(`resolved ${entry.pendingResolution.id} with ${entry.pendingResolution.decision}`);
			await adapter.finalizeResolved({
				request: entry.request,
				resolved: entry.pendingResolution,
				entries: entry.entries
			});
			return;
		}
		const timeoutMs = Math.max(0, request.expiresAtMs - nowMs());
		const timeoutId = setTimeout(() => {
			spawn("error handling approval expiration", handleExpired(request.id));
		}, timeoutMs);
		timeoutId.unref?.();
		entry.timeoutId = timeoutId;
	};
	const handleResolved = async (resolved) => {
		const entry = pending.get(resolved.id);
		if (!entry) return;
		if (entry.delivering) {
			entry.pendingResolution = resolved;
			return;
		}
		const finalizedEntry = clearPendingEntry(resolved.id);
		if (!finalizedEntry) return;
		log.debug(`resolved ${resolved.id} with ${resolved.decision}`);
		await adapter.finalizeResolved({
			request: finalizedEntry.request,
			resolved,
			entries: finalizedEntry.entries
		});
	};
	const handleGatewayEvent = (evt) => {
		if (evt.event === "exec.approval.requested" && eventKinds.has("exec")) {
			spawn("error handling approval request", handleRequested(evt.payload));
			return;
		}
		if (evt.event === "plugin.approval.requested" && eventKinds.has("plugin")) {
			spawn("error handling approval request", handleRequested(evt.payload));
			return;
		}
		if (evt.event === "exec.approval.resolved" && eventKinds.has("exec")) {
			spawn("error handling approval resolved", handleResolved(evt.payload));
			return;
		}
		if (evt.event === "plugin.approval.resolved" && eventKinds.has("plugin")) spawn("error handling approval resolved", handleResolved(evt.payload));
	};
	return {
		async start() {
			if (started) return;
			if (startPromise) {
				await startPromise;
				return;
			}
			shouldRun = true;
			startPromise = (async () => {
				if (!adapter.isConfigured()) {
					log.debug("disabled");
					return;
				}
				const client = await createOperatorApprovalsGatewayClient({
					config: adapter.cfg,
					gatewayUrl: adapter.gatewayUrl,
					clientDisplayName: adapter.clientDisplayName,
					onEvent: handleGatewayEvent,
					onHelloOk: () => {
						log.debug("connected to gateway");
					},
					onConnectError: (err) => {
						log.error(`connect error: ${err.message}`);
					},
					onClose: (code, reason) => {
						log.debug(`gateway closed: ${code} ${reason}`);
					}
				});
				if (!shouldRun) {
					client.stop();
					return;
				}
				client.start();
				gatewayClient = client;
				started = true;
			})().finally(() => {
				startPromise = null;
			});
			await startPromise;
		},
		async stop() {
			shouldRun = false;
			if (startPromise) await startPromise.catch(() => {});
			if (!started && !gatewayClient) return;
			started = false;
			for (const entry of pending.values()) if (entry.timeoutId) clearTimeout(entry.timeoutId);
			pending.clear();
			gatewayClient?.stop();
			gatewayClient = null;
			log.debug("stopped");
		},
		handleRequested,
		handleResolved,
		handleExpired,
		async request(method, params) {
			if (!gatewayClient) throw new Error(`${adapter.label}: gateway client not connected`);
			return await gatewayClient.request(method, params);
		}
	};
}
//#endregion
//#region src/infra/approval-native-delivery.ts
function buildTargetKey$1(target) {
	return `${target.to}:${target.threadId ?? ""}`;
}
function dedupeTargets(targets) {
	const seen = /* @__PURE__ */ new Set();
	const deduped = [];
	for (const target of targets) {
		const key = buildTargetKey$1(target.target);
		if (seen.has(key)) continue;
		seen.add(key);
		deduped.push(target);
	}
	return deduped;
}
async function resolveChannelNativeApprovalDeliveryPlan(params) {
	const adapter = params.adapter;
	if (!adapter) return {
		targets: [],
		originTarget: null,
		notifyOriginWhenDmOnly: false
	};
	const capabilities = adapter.describeDeliveryCapabilities({
		cfg: params.cfg,
		accountId: params.accountId,
		approvalKind: params.approvalKind,
		request: params.request
	});
	if (!capabilities.enabled) return {
		targets: [],
		originTarget: null,
		notifyOriginWhenDmOnly: false
	};
	const originTarget = capabilities.supportsOriginSurface && adapter.resolveOriginTarget ? await adapter.resolveOriginTarget({
		cfg: params.cfg,
		accountId: params.accountId,
		approvalKind: params.approvalKind,
		request: params.request
	}) ?? null : null;
	const approverDmTargets = capabilities.supportsApproverDmSurface && adapter.resolveApproverDmTargets ? await adapter.resolveApproverDmTargets({
		cfg: params.cfg,
		accountId: params.accountId,
		approvalKind: params.approvalKind,
		request: params.request
	}) : [];
	const plannedTargets = [];
	const preferOrigin = capabilities.preferredSurface === "origin" || capabilities.preferredSurface === "both";
	const preferApproverDm = capabilities.preferredSurface === "approver-dm" || capabilities.preferredSurface === "both";
	if (preferOrigin && originTarget) plannedTargets.push({
		surface: "origin",
		target: originTarget,
		reason: "preferred"
	});
	if (preferApproverDm) for (const target of approverDmTargets) plannedTargets.push({
		surface: "approver-dm",
		target,
		reason: "preferred"
	});
	else if (!originTarget) for (const target of approverDmTargets) plannedTargets.push({
		surface: "approver-dm",
		target,
		reason: "fallback"
	});
	return {
		targets: dedupeTargets(plannedTargets),
		originTarget,
		notifyOriginWhenDmOnly: capabilities.preferredSurface === "approver-dm" && capabilities.notifyOriginWhenDmOnly === true && originTarget !== null
	};
}
//#endregion
//#region src/infra/approval-native-runtime.ts
function buildTargetKey(target) {
	return `${target.to}:${target.threadId == null ? "" : String(target.threadId)}`;
}
async function deliverApprovalRequestViaChannelNativePlan(params) {
	const deliveryPlan = await resolveChannelNativeApprovalDeliveryPlan({
		cfg: params.cfg,
		accountId: params.accountId,
		approvalKind: params.approvalKind,
		request: params.request,
		adapter: params.adapter
	});
	const originTargetKey = deliveryPlan.originTarget ? buildTargetKey(deliveryPlan.originTarget) : null;
	const plannedTargetKeys = new Set(deliveryPlan.targets.map((plannedTarget) => buildTargetKey(plannedTarget.target)));
	if (deliveryPlan.notifyOriginWhenDmOnly && deliveryPlan.originTarget && (originTargetKey == null || !plannedTargetKeys.has(originTargetKey))) try {
		await params.sendOriginNotice?.({
			originTarget: deliveryPlan.originTarget,
			request: params.request
		});
	} catch (error) {
		params.onOriginNoticeError?.({
			error,
			originTarget: deliveryPlan.originTarget,
			request: params.request
		});
	}
	const deliveredKeys = /* @__PURE__ */ new Set();
	const pendingEntries = [];
	for (const plannedTarget of deliveryPlan.targets) try {
		const preparedTarget = await params.prepareTarget({
			plannedTarget,
			request: params.request
		});
		if (!preparedTarget) continue;
		if (deliveredKeys.has(preparedTarget.dedupeKey)) {
			params.onDuplicateSkipped?.({
				plannedTarget,
				preparedTarget,
				request: params.request
			});
			continue;
		}
		const entry = await params.deliverTarget({
			plannedTarget,
			preparedTarget: preparedTarget.target,
			request: params.request
		});
		if (!entry) continue;
		deliveredKeys.add(preparedTarget.dedupeKey);
		pendingEntries.push(entry);
		params.onDelivered?.({
			plannedTarget,
			preparedTarget,
			request: params.request,
			entry
		});
	} catch (error) {
		params.onDeliveryError?.({
			error,
			plannedTarget,
			request: params.request
		});
	}
	return pendingEntries;
}
//#endregion
export { resolveChannelNativeApprovalDeliveryPlan as n, createExecApprovalChannelRuntime as r, deliverApprovalRequestViaChannelNativePlan as t };
