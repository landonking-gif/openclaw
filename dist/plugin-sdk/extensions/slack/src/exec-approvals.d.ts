import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import type { ExecApprovalRequest, PluginApprovalRequest } from "openclaw/plugin-sdk/infra-runtime";
import type { ReplyPayload } from "openclaw/plugin-sdk/reply-runtime";
type ApprovalRequest = ExecApprovalRequest | PluginApprovalRequest;
export declare function normalizeSlackApproverId(value: string | number): string | undefined;
export declare function shouldHandleSlackExecApprovalRequest(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
    request: ApprovalRequest;
}): boolean;
export declare function getSlackExecApprovalApprovers(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
}): string[];
export declare function isSlackExecApprovalClientEnabled(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
}): boolean;
export declare function isSlackExecApprovalApprover(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
    senderId?: string | null;
}): boolean;
export declare function isSlackExecApprovalTargetRecipient(params: {
    cfg: OpenClawConfig;
    senderId?: string | null;
    accountId?: string | null;
}): boolean;
export declare function isSlackExecApprovalAuthorizedSender(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
    senderId?: string | null;
}): boolean;
export declare function resolveSlackExecApprovalTarget(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
}): "dm" | "channel" | "both";
export declare function shouldSuppressLocalSlackExecApprovalPrompt(params: {
    cfg: OpenClawConfig;
    accountId?: string | null;
    payload: ReplyPayload;
}): boolean;
export {};
