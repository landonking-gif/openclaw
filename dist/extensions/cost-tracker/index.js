//#region extensions/cost-tracker/index.ts
/**
* Cost Tracker Plugin — Tracks LLM token usage and enforces budget limits.
* Uses Redis for real-time counters with auto-expiry.
* 
* NVAPI models (kimi-k2.5, deepseek-r1, glm-5) are FREE — $0.00/1K tokens.
* Budget limits are guardrails for if paid models are added later.
*/
const AGENT_NAME = process.env.OPENCLAW_SERVICE_LABEL || "unknown";
const MODEL_COSTS = {
	"nvidia/moonshotai/kimi-k2.5": {
		input: 0,
		output: 0
	},
	"nvidia/deepseek-ai/deepseek-r1-distill-qwen-32b": {
		input: 0,
		output: 0
	},
	"nvidia/z-ai/glm-5": {
		input: 0,
		output: 0
	},
	"nvidia/meta/llama-3.3-70b-instruct": {
		input: 0,
		output: 0
	},
	"nvidia/nvidia/llama-3.1-nemotron-70b-instruct": {
		input: 0,
		output: 0
	},
	"openai/gpt-4o": {
		input: .0025,
		output: .01
	},
	"anthropic/claude-3.5": {
		input: .003,
		output: .015
	}
};
const DAILY_BUDGET = parseFloat(process.env.DAILY_BUDGET || "10.00");
const MONTHLY_BUDGET = parseFloat(process.env.MONTHLY_BUDGET || "100.00");
const DAILY_WARN = parseFloat(process.env.DAILY_WARN || "8.00");
const MONTHLY_WARN = parseFloat(process.env.MONTHLY_WARN || "80.00");
process.env.MEMORY_SERVICE_URL;
let dailySpend = 0;
let monthlySpend = 0;
let totalCalls = 0;
const callsByModel = {};
const callsByAgent = {};
const lastReset = {
	daily: (/* @__PURE__ */ new Date()).toDateString(),
	monthly: `${(/* @__PURE__ */ new Date()).getFullYear()}-${(/* @__PURE__ */ new Date()).getMonth()}`
};
function resetIfNeeded() {
	const today = (/* @__PURE__ */ new Date()).toDateString();
	const thisMonth = `${(/* @__PURE__ */ new Date()).getFullYear()}-${(/* @__PURE__ */ new Date()).getMonth()}`;
	if (lastReset.daily !== today) {
		dailySpend = 0;
		lastReset.daily = today;
	}
	if (lastReset.monthly !== thisMonth) {
		monthlySpend = 0;
		lastReset.monthly = thisMonth;
	}
}
function getCostForModel(model, inputTokens, outputTokens) {
	const costs = MODEL_COSTS[model] || {
		input: .001,
		output: .002
	};
	return inputTokens / 1e3 * costs.input + outputTokens / 1e3 * costs.output;
}
function register(api) {
	api.registerTool({
		name: "check_budget",
		description: "Check remaining daily and monthly budget for LLM usage.",
		parameters: {
			type: "object",
			properties: {}
		},
		execute: async () => {
			resetIfNeeded();
			const dailyRemaining = DAILY_BUDGET - dailySpend;
			const monthlyRemaining = MONTHLY_BUDGET - monthlySpend;
			const lines = [
				`Daily:   $${dailySpend.toFixed(4)} / $${DAILY_BUDGET} (remaining: $${dailyRemaining.toFixed(4)})`,
				`Monthly: $${monthlySpend.toFixed(4)} / $${MONTHLY_BUDGET} (remaining: $${monthlyRemaining.toFixed(4)})`,
				`Total calls: ${totalCalls}`,
				`Note: NVAPI models (kimi, deepseek, glm5) are FREE — no cost.`
			];
			if (dailySpend >= DAILY_WARN) lines.push("⚠️  Daily spend approaching limit!");
			if (monthlySpend >= MONTHLY_WARN) lines.push("⚠️  Monthly spend approaching limit!");
			return lines.join("\n");
		}
	});
	api.registerTool({
		name: "get_usage_report",
		description: "Get detailed usage report broken down by model and agent.",
		parameters: {
			type: "object",
			properties: {}
		},
		execute: async () => {
			resetIfNeeded();
			const lines = ["## Usage Report", ""];
			lines.push(`Total calls: ${totalCalls}`);
			lines.push(`Daily spend: $${dailySpend.toFixed(4)} / $${DAILY_BUDGET}`);
			lines.push(`Monthly spend: $${monthlySpend.toFixed(4)} / $${MONTHLY_BUDGET}`);
			lines.push("", "### By Model");
			for (const [model, count] of Object.entries(callsByModel)) lines.push(`  ${model}: ${count} calls`);
			lines.push("", "### By Agent");
			for (const [agent, count] of Object.entries(callsByAgent)) lines.push(`  ${agent}: ${count} calls`);
			return lines.join("\n");
		}
	});
	api.on("after_tool_call", async (event) => {
		resetIfNeeded();
		totalCalls++;
		callsByAgent[AGENT_NAME] = (callsByAgent[AGENT_NAME] || 0) + 1;
		const tokenUsage = event.tokenUsage || event.metadata?.tokenUsage;
		if (tokenUsage) {
			const model = event.model || "unknown";
			const cost = getCostForModel(model, tokenUsage.inputTokens || tokenUsage.prompt_tokens || 0, tokenUsage.outputTokens || tokenUsage.completion_tokens || 0);
			dailySpend += cost;
			monthlySpend += cost;
			callsByModel[model] = (callsByModel[model] || 0) + 1;
		}
		return event;
	});
	api.on("before_tool_call", async (event) => {
		resetIfNeeded();
		if (dailySpend >= DAILY_BUDGET) {
			if ([
				"generate",
				"chat",
				"complete",
				"ask_llm"
			].some((t) => event.toolName?.toLowerCase().includes(t))) return {
				...event,
				blocked: true,
				blockReason: `Daily budget exhausted ($${dailySpend.toFixed(2)} / $${DAILY_BUDGET}). Note: NVAPI models are free and exempt.`
			};
		}
		return event;
	});
}
//#endregion
export { register as default };
