import type { ChannelApprovalKind, ChannelApprovalNativeAdapter, ChannelApprovalNativeTarget } from "../channels/plugins/types.adapters.js";
import type { OpenClawConfig } from "../config/config.js";
import { type ChannelApprovalNativePlannedTarget } from "./approval-native-delivery.js";
import type { ExecApprovalRequest } from "./exec-approvals.js";
import type { PluginApprovalRequest } from "./plugin-approvals.js";
type ApprovalRequest = ExecApprovalRequest | PluginApprovalRequest;
export type PreparedChannelNativeApprovalTarget<TPreparedTarget> = {
    dedupeKey: string;
    target: TPreparedTarget;
};
export declare function deliverApprovalRequestViaChannelNativePlan<TPreparedTarget, TPendingEntry, TRequest extends ApprovalRequest = ApprovalRequest>(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
    approvalKind: ChannelApprovalKind;
    request: TRequest;
    adapter?: ChannelApprovalNativeAdapter | null;
    sendOriginNotice?: (params: {
        originTarget: ChannelApprovalNativeTarget;
        request: TRequest;
    }) => Promise<void>;
    prepareTarget: (params: {
        plannedTarget: ChannelApprovalNativePlannedTarget;
        request: TRequest;
    }) => PreparedChannelNativeApprovalTarget<TPreparedTarget> | null | Promise<PreparedChannelNativeApprovalTarget<TPreparedTarget> | null>;
    deliverTarget: (params: {
        plannedTarget: ChannelApprovalNativePlannedTarget;
        preparedTarget: TPreparedTarget;
        request: TRequest;
    }) => TPendingEntry | null | Promise<TPendingEntry | null>;
    onOriginNoticeError?: (params: {
        error: unknown;
        originTarget: ChannelApprovalNativeTarget;
        request: TRequest;
    }) => void;
    onDeliveryError?: (params: {
        error: unknown;
        plannedTarget: ChannelApprovalNativePlannedTarget;
        request: TRequest;
    }) => void;
    onDuplicateSkipped?: (params: {
        plannedTarget: ChannelApprovalNativePlannedTarget;
        preparedTarget: PreparedChannelNativeApprovalTarget<TPreparedTarget>;
        request: TRequest;
    }) => void;
    onDelivered?: (params: {
        plannedTarget: ChannelApprovalNativePlannedTarget;
        preparedTarget: PreparedChannelNativeApprovalTarget<TPreparedTarget>;
        request: TRequest;
        entry: TPendingEntry;
    }) => void;
}): Promise<TPendingEntry[]>;
export {};
