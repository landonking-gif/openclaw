import { r as streamWithPayloadPatch } from "../../moonshot-thinking-stream-wrappers-Bcn6-E6S.js";
import { _ as isAnthropicBedrockModel, g as createBedrockNoCacheWrapper } from "../../openai-stream-wrappers-8dDBuYmP.js";
import { t as definePluginEntry } from "../../plugin-entry-C2JEeAkR.js";
import "../../provider-stream-CJZgrFLB.js";
import { a as resolveImplicitBedrockProvider, i as resolveBedrockConfigApiKey, n as mergeImplicitBedrockProvider } from "../../discovery-Cz21KBKE.js";
import "../../api-BZ_ajoB5.js";
//#region extensions/amazon-bedrock/index.ts
function createGuardrailWrapStreamFn(innerWrapStreamFn, guardrailConfig) {
	return (ctx) => {
		const inner = innerWrapStreamFn(ctx);
		if (!inner) return inner;
		return (model, context, options) => {
			return streamWithPayloadPatch(inner, model, context, options, (payload) => {
				const gc = {
					guardrailIdentifier: guardrailConfig.guardrailIdentifier,
					guardrailVersion: guardrailConfig.guardrailVersion
				};
				if (guardrailConfig.streamProcessingMode) gc.streamProcessingMode = guardrailConfig.streamProcessingMode;
				if (guardrailConfig.trace) gc.trace = guardrailConfig.trace;
				payload.guardrailConfig = gc;
			});
		};
	};
}
const PROVIDER_ID = "amazon-bedrock";
const CLAUDE_46_MODEL_RE = /claude-(?:opus|sonnet)-4(?:\.|-)6(?:$|[-.])/i;
var amazon_bedrock_default = definePluginEntry({
	id: PROVIDER_ID,
	name: "Amazon Bedrock Provider",
	description: "Bundled Amazon Bedrock provider policy plugin",
	register(api) {
		const guardrail = api.pluginConfig?.guardrail;
		const baseWrapStreamFn = ({ modelId, streamFn }) => isAnthropicBedrockModel(modelId) ? streamFn : createBedrockNoCacheWrapper(streamFn);
		const wrapStreamFn = guardrail?.guardrailIdentifier && guardrail?.guardrailVersion ? createGuardrailWrapStreamFn(baseWrapStreamFn, guardrail) : baseWrapStreamFn;
		api.registerProvider({
			id: PROVIDER_ID,
			label: "Amazon Bedrock",
			docsPath: "/providers/models",
			auth: [],
			catalog: {
				order: "simple",
				run: async (ctx) => {
					const implicit = await resolveImplicitBedrockProvider({
						config: ctx.config,
						env: ctx.env
					});
					if (!implicit) return null;
					return { provider: mergeImplicitBedrockProvider({
						existing: ctx.config.models?.providers?.[PROVIDER_ID],
						implicit
					}) };
				}
			},
			resolveConfigApiKey: ({ env }) => resolveBedrockConfigApiKey(env),
			capabilities: {
				providerFamily: "anthropic",
				dropThinkingBlockModelHints: ["claude"]
			},
			wrapStreamFn,
			resolveDefaultThinkingLevel: ({ modelId }) => CLAUDE_46_MODEL_RE.test(modelId.trim()) ? "adaptive" : void 0
		});
	}
});
//#endregion
export { amazon_bedrock_default as default };
