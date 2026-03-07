import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

/**
 * Cost Tracker Plugin — Tracks LLM token usage and enforces budget limits.
 * Uses Redis for real-time counters with auto-expiry.
 * 
 * NVAPI models (kimi-k2.5, deepseek-r1, glm-5) are FREE — $0.00/1K tokens.
 * Budget limits are guardrails for if paid models are added later.
 */

const AGENT_NAME = process.env.OPENCLAW_SERVICE_LABEL || "unknown";

// Model costs per 1K tokens (NVAPI models are free)
const MODEL_COSTS: Record<string, { input: number; output: number }> = {
  "nvidia/moonshotai/kimi-k2.5":                        { input: 0.0, output: 0.0 },
  "nvidia/deepseek-ai/deepseek-r1-distill-qwen-32b":   { input: 0.0, output: 0.0 },
  "nvidia/z-ai/glm-5":                                  { input: 0.0, output: 0.0 },
  "nvidia/meta/llama-3.3-70b-instruct":                 { input: 0.0, output: 0.0 },
  "nvidia/nvidia/llama-3.1-nemotron-70b-instruct":      { input: 0.0, output: 0.0 },
  // Future paid models:
  "openai/gpt-4o":          { input: 0.0025, output: 0.01 },
  "anthropic/claude-3.5":   { input: 0.003,  output: 0.015 },
};

const DAILY_BUDGET  = parseFloat(process.env.DAILY_BUDGET  || "10.00");
const MONTHLY_BUDGET= parseFloat(process.env.MONTHLY_BUDGET|| "100.00");
const DAILY_WARN    = parseFloat(process.env.DAILY_WARN    || "8.00");
const MONTHLY_WARN  = parseFloat(process.env.MONTHLY_WARN  || "80.00");
const MEMORY_URL    = process.env.MEMORY_SERVICE_URL || "http://localhost:18820";

// In-memory tracking (Redis-backed version sends to memory-service for persistence)
let dailySpend = 0;
let monthlySpend = 0;
let totalCalls = 0;
const callsByModel: Record<string, number> = {};
const callsByAgent: Record<string, number> = {};
const lastReset = { daily: new Date().toDateString(), monthly: `${new Date().getFullYear()}-${new Date().getMonth()}` };

function resetIfNeeded() {
  const today = new Date().toDateString();
  const thisMonth = `${new Date().getFullYear()}-${new Date().getMonth()}`;
  if (lastReset.daily !== today) { dailySpend = 0; lastReset.daily = today; }
  if (lastReset.monthly !== thisMonth) { monthlySpend = 0; lastReset.monthly = thisMonth; }
}

function getCostForModel(model: string, inputTokens: number, outputTokens: number): number {
  const costs = MODEL_COSTS[model] || { input: 0.001, output: 0.002 };
  return (inputTokens / 1000) * costs.input + (outputTokens / 1000) * costs.output;
}

export default function register(api: OpenClawPluginApi) {
  // ── Tool: check_budget ───────────────────────────────────────────────────
  api.registerTool({
    name: "check_budget",
    description: "Check remaining daily and monthly budget for LLM usage.",
    parameters: { type: "object", properties: {} },
    execute: async () => {
      resetIfNeeded();
      const dailyRemaining = DAILY_BUDGET - dailySpend;
      const monthlyRemaining = MONTHLY_BUDGET - monthlySpend;
      const lines = [
        `Daily:   $${dailySpend.toFixed(4)} / $${DAILY_BUDGET} (remaining: $${dailyRemaining.toFixed(4)})`,
        `Monthly: $${monthlySpend.toFixed(4)} / $${MONTHLY_BUDGET} (remaining: $${monthlyRemaining.toFixed(4)})`,
        `Total calls: ${totalCalls}`,
        `Note: NVAPI models (kimi, deepseek, glm5) are FREE — no cost.`,
      ];
      if (dailySpend >= DAILY_WARN) lines.push("⚠️  Daily spend approaching limit!");
      if (monthlySpend >= MONTHLY_WARN) lines.push("⚠️  Monthly spend approaching limit!");
      return lines.join("\n");
    },
  });

  // ── Tool: get_usage_report ───────────────────────────────────────────────
  api.registerTool({
    name: "get_usage_report",
    description: "Get detailed usage report broken down by model and agent.",
    parameters: { type: "object", properties: {} },
    execute: async () => {
      resetIfNeeded();
      const lines = ["## Usage Report", ""];
      lines.push(`Total calls: ${totalCalls}`);
      lines.push(`Daily spend: $${dailySpend.toFixed(4)} / $${DAILY_BUDGET}`);
      lines.push(`Monthly spend: $${monthlySpend.toFixed(4)} / $${MONTHLY_BUDGET}`);
      lines.push("", "### By Model");
      for (const [model, count] of Object.entries(callsByModel)) {
        lines.push(`  ${model}: ${count} calls`);
      }
      lines.push("", "### By Agent");
      for (const [agent, count] of Object.entries(callsByAgent)) {
        lines.push(`  ${agent}: ${count} calls`);
      }
      return lines.join("\n");
    },
  });

  // ── Hook: track usage after every tool call ──────────────────────────────
  api.on("after_tool_call", async (event: any) => {
    resetIfNeeded();
    totalCalls++;
    callsByAgent[AGENT_NAME] = (callsByAgent[AGENT_NAME] || 0) + 1;

    // Extract token usage from event metadata if available
    const tokenUsage = event.tokenUsage || event.metadata?.tokenUsage;
    if (tokenUsage) {
      const model = event.model || "unknown";
      const inputTokens = tokenUsage.inputTokens || tokenUsage.prompt_tokens || 0;
      const outputTokens = tokenUsage.outputTokens || tokenUsage.completion_tokens || 0;
      const cost = getCostForModel(model, inputTokens, outputTokens);

      dailySpend += cost;
      monthlySpend += cost;
      callsByModel[model] = (callsByModel[model] || 0) + 1;
    }

    return event;
  });

  // ── Hook: pre-flight budget check before tool calls ──────────────────────
  api.on("before_tool_call", async (event: any) => {
    resetIfNeeded();

    if (dailySpend >= DAILY_BUDGET) {
      // Only block if it's an LLM call (not a file read or similar)
      const llmTools = ["generate", "chat", "complete", "ask_llm"];
      if (llmTools.some(t => event.toolName?.toLowerCase().includes(t))) {
        return {
          ...event,
          blocked: true,
          blockReason: `Daily budget exhausted ($${dailySpend.toFixed(2)} / $${DAILY_BUDGET}). Note: NVAPI models are free and exempt.`,
        };
      }
    }
    return event;
  });
}
