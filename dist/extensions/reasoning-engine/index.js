//#region extensions/reasoning-engine/index.ts
/**
* Reasoning Engine Plugin — Provides three structured reasoning patterns:
* 
* 1. ReAct (Thought → Action → Observation loop)
*    For step-by-step problem solving with tool use.
* 
* 2. Reflective (PLAN → EXECUTE → VALIDATE → REFINE)
*    For tasks requiring quality validation and iterative improvement.
* 
* 3. Enterprise (THINK → PLAN → APPROVE → EXECUTE → VALIDATE → REFLECT)
*    For high-stakes tasks requiring governance and approval gates.
* 
* Each pattern returns a structured execution trace with reasoning steps.
*/
const AGENT_NAME = process.env.OPENCLAW_SERVICE_LABEL || "unknown";
const MEMORY_URL = process.env.MEMORY_SERVICE_URL || "http://localhost:18820";
const MAX_REACT_ITERATIONS = parseInt(process.env.MAX_REACT_ITERATIONS || "10");
const MAX_REFLECTIVE_ITERATIONS = parseInt(process.env.MAX_REFLECTIVE_ITERATIONS || "5");
const MIN_CONFIDENCE = parseFloat(process.env.MIN_CONFIDENCE_TO_EXECUTE || "0.6");
const MIN_QUALITY = parseFloat(process.env.MIN_QUALITY_SCORE || "0.7");
function now() {
	return (/* @__PURE__ */ new Date()).toISOString();
}
function buildTrace(pattern, task, steps, finalResult) {
	return JSON.stringify({
		pattern,
		task,
		agent: AGENT_NAME,
		steps,
		finalResult,
		totalSteps: steps.length,
		completedAt: now()
	}, null, 2);
}
async function logToMemory(category, content) {
	try {
		await fetch(`${MEMORY_URL}/memory/commit`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				agent_name: AGENT_NAME,
				content,
				category,
				importance: .7,
				metadata: { source: "reasoning-engine" }
			})
		});
	} catch {}
}
function register(api) {
	api.registerTool({
		name: "react_execute",
		description: `Execute a task using the ReAct reasoning pattern (Thought → Action → Observation).
Use this for step-by-step problem solving where you need to iteratively think, act, and observe results.
Returns a structured trace of all reasoning steps.`,
		parameters: {
			type: "object",
			properties: {
				task: {
					type: "string",
					description: "The task to solve using ReAct reasoning."
				},
				context: {
					type: "string",
					description: "Optional context or constraints for the task."
				},
				max_iterations: {
					type: "number",
					description: `Max iterations before forcing completion (default: ${MAX_REACT_ITERATIONS}).`
				}
			},
			required: ["task"]
		},
		execute: async (args) => {
			const maxIter = args.max_iterations || MAX_REACT_ITERATIONS;
			const steps = [];
			const scratchpad = [];
			steps.push({
				phase: "INIT",
				content: `Starting ReAct loop for task: ${args.task}`,
				timestamp: now(),
				metadata: {
					context: args.context || "none",
					maxIterations: maxIter
				}
			});
			if (args.context) scratchpad.push(`Context: ${args.context}`);
			const reactPrompt = [
				`## ReAct Reasoning Framework`,
				``,
				`**Task:** ${args.task}`,
				args.context ? `**Context:** ${args.context}` : "",
				``,
				`Follow this iterative pattern:`,
				`1. **Thought**: Analyze what you know and what you need to find out`,
				`2. **Action**: Choose a specific action to take (use tools, search, compute, etc.)`,
				`3. **Observation**: Record the result of your action`,
				`4. Repeat until you have enough information to provide a final answer`,
				``,
				`**Max iterations**: ${maxIter}`,
				`**Current scratchpad**: ${scratchpad.join("\\n") || "(empty)"}`,
				``,
				`Begin your reasoning. At each step, clearly label [Thought], [Action], and [Observation].`,
				`When you have a final answer, output [FINAL ANSWER]: <your answer>`
			].filter(Boolean).join("\n");
			steps.push({
				phase: "PROMPT",
				content: reactPrompt,
				timestamp: now()
			});
			await logToMemory("reasoning", `[ReAct] Started: ${args.task}`);
			return buildTrace("react", args.task, steps, reactPrompt);
		}
	});
	api.registerTool({
		name: "reflective_execute",
		description: `Execute a task using the Reflective reasoning pattern (PLAN → EXECUTE → VALIDATE → REFINE).
Use this when quality matters — includes built-in validation and iterative refinement.
Returns a structured execution trace with confidence scores.`,
		parameters: {
			type: "object",
			properties: {
				task: {
					type: "string",
					description: "The task to execute with reflective reasoning."
				},
				quality_criteria: {
					type: "string",
					description: "Criteria to validate the output against."
				},
				max_refinements: {
					type: "number",
					description: `Max refinement iterations (default: ${MAX_REFLECTIVE_ITERATIONS}).`
				},
				min_quality_score: {
					type: "number",
					description: `Minimum quality score to accept (0-1, default: ${MIN_QUALITY}).`
				}
			},
			required: ["task"]
		},
		execute: async (args) => {
			const maxRefine = args.max_refinements || MAX_REFLECTIVE_ITERATIONS;
			const minQuality = args.min_quality_score || MIN_QUALITY;
			const steps = [];
			steps.push({
				phase: "PLAN",
				content: `Generating execution plan for: ${args.task}`,
				timestamp: now(),
				metadata: { qualityCriteria: args.quality_criteria || "default" }
			});
			const reflectivePrompt = [
				`## Reflective Reasoning Framework`,
				``,
				`**Task:** ${args.task}`,
				args.quality_criteria ? `**Quality Criteria:** ${args.quality_criteria}` : "",
				`**Max refinements:** ${maxRefine}`,
				`**Min quality score:** ${minQuality}`,
				``,
				`Follow these phases:`,
				``,
				`### Phase 1: PLAN`,
				`- Break the task into clear sub-steps`,
				`- Identify potential challenges`,
				`- Define success criteria: ${args.quality_criteria || "output is correct, complete, and well-structured"}`,
				``,
				`### Phase 2: EXECUTE`,
				`- Execute each sub-step methodically`,
				`- Document intermediate results`,
				`- Note any deviations from the plan`,
				``,
				`### Phase 3: VALIDATE`,
				`- Review output against quality criteria`,
				`- Score each criterion on 0-1 scale`,
				`- Compute overall quality score (must be ≥ ${minQuality})`,
				`- Format: [QUALITY_SCORE]: 0.XX`,
				``,
				`### Phase 4: REFINE (if quality < ${minQuality})`,
				`- Identify specific weaknesses`,
				`- Apply targeted improvements`,
				`- Re-validate (repeat up to ${maxRefine} times)`,
				``,
				`Begin with Phase 1: PLAN.`
			].filter(Boolean).join("\n");
			steps.push({
				phase: "PROMPT",
				content: reflectivePrompt,
				timestamp: now()
			});
			await logToMemory("reasoning", `[Reflective] Started: ${args.task}`);
			return buildTrace("reflective", args.task, steps, reflectivePrompt);
		}
	});
	api.registerTool({
		name: "enterprise_execute",
		description: `Execute a task using the Enterprise reasoning pattern with full governance.
Includes approval gates, risk assessment, and post-execution reflection.
(THINK → PLAN → APPROVE → EXECUTE → VALIDATE → REFLECT)
Use for high-stakes tasks: deployments, data changes, external communications, financial operations.`,
		parameters: {
			type: "object",
			properties: {
				task: {
					type: "string",
					description: "The high-stakes task to execute."
				},
				risk_level: {
					type: "string",
					enum: [
						"low",
						"medium",
						"high",
						"critical"
					],
					description: "Risk assessment level (determines approval requirements)."
				},
				stakeholders: {
					type: "string",
					description: "Comma-separated list of stakeholders/systems affected."
				},
				rollback_plan: {
					type: "string",
					description: "How to undo if things go wrong."
				},
				confidence_threshold: {
					type: "number",
					description: `Min confidence to proceed past APPROVE (0-1, default: ${MIN_CONFIDENCE}).`
				}
			},
			required: ["task", "risk_level"]
		},
		execute: async (args) => {
			const confThreshold = args.confidence_threshold || MIN_CONFIDENCE;
			const steps = [];
			const approvalRequired = args.risk_level === "high" || args.risk_level === "critical";
			const humanApproval = args.risk_level === "critical";
			steps.push({
				phase: "INIT",
				content: `Enterprise execution initiated for: ${args.task}`,
				timestamp: now(),
				metadata: {
					riskLevel: args.risk_level,
					approvalRequired,
					humanApproval,
					stakeholders: args.stakeholders || "none specified"
				}
			});
			const enterprisePrompt = [
				`## Enterprise Reasoning Framework`,
				``,
				`**Task:** ${args.task}`,
				`**Risk Level:** ${args.risk_level.toUpperCase()}`,
				`**Approval Required:** ${approvalRequired ? "YES" : "No (auto-approved)"}`,
				`**Human Approval:** ${humanApproval ? "YES — MUST GET USER CONFIRMATION" : "No"}`,
				args.stakeholders ? `**Stakeholders:** ${args.stakeholders}` : "",
				args.rollback_plan ? `**Rollback Plan:** ${args.rollback_plan}` : "",
				`**Confidence Threshold:** ${confThreshold}`,
				``,
				`### Phase 1: THINK`,
				`- Deep analysis of the task and its implications`,
				`- Identify all risks, edge cases, and dependencies`,
				`- Consider impact on: ${args.stakeholders || "the system and users"}`,
				`- Document assumptions`,
				``,
				`### Phase 2: PLAN`,
				`- Create a detailed execution plan with numbered steps`,
				`- Include safety checks at each step`,
				`- Define rollback points: ${args.rollback_plan || "(define during planning)"}`,
				`- Estimate impact and resource requirements`,
				``,
				`### Phase 3: APPROVE`,
				approvalRequired ? humanApproval ? `- ⚠️ CRITICAL RISK: Present the plan to the user and WAIT for explicit approval before proceeding` : `- HIGH RISK: Self-assess confidence. Score each plan step 0-1. Overall must be ≥ ${confThreshold}` : `- LOW/MEDIUM: Auto-approved. Document reasoning for audit trail.`,
				`- Format: [CONFIDENCE_SCORE]: 0.XX — [APPROVED/DENIED]`,
				``,
				`### Phase 4: EXECUTE`,
				`- Execute each plan step in order`,
				`- After each step, verify it succeeded before proceeding`,
				`- If any step fails, evaluate whether to continue or rollback`,
				`- Document all actions taken with timestamps`,
				``,
				`### Phase 5: VALIDATE`,
				`- Verify all acceptance criteria are met`,
				`- Run any automated checks or tests`,
				`- Score overall execution quality (0-1)`,
				`- Format: [VALIDATION_SCORE]: 0.XX`,
				``,
				`### Phase 6: REFLECT`,
				`- What went well? What went poorly?`,
				`- What would you do differently next time?`,
				`- Are there follow-up actions needed?`,
				`- Create a 1-paragraph diary entry summarizing the execution`,
				``,
				`Begin with Phase 1: THINK.`
			].filter(Boolean).join("\n");
			steps.push({
				phase: "PROMPT",
				content: enterprisePrompt,
				timestamp: now()
			});
			await logToMemory("reasoning", `[Enterprise:${args.risk_level}] Started: ${args.task}`);
			return buildTrace("enterprise", args.task, steps, enterprisePrompt);
		}
	});
	api.registerTool({
		name: "get_reasoning_patterns",
		description: "List and describe all available reasoning patterns with guidance on when to use each.",
		parameters: {
			type: "object",
			properties: {}
		},
		execute: async () => {
			return [
				"## Available Reasoning Patterns",
				"",
				"### 1. ReAct (react_execute)",
				"Pattern: Thought → Action → Observation (iterative)",
				"Best for: Exploratory tasks, information gathering, multi-step problem solving",
				"Example: Research a topic, debug an issue, investigate a codebase",
				"",
				"### 2. Reflective (reflective_execute)",
				"Pattern: PLAN → EXECUTE → VALIDATE → REFINE",
				"Best for: Quality-critical tasks requiring iterative improvement",
				"Example: Write documentation, implement a feature, create a report",
				"",
				"### 3. Enterprise (enterprise_execute)",
				"Pattern: THINK → PLAN → APPROVE → EXECUTE → VALIDATE → REFLECT",
				"Best for: High-stakes operations requiring governance and audit trails",
				"Example: Deploy to production, modify databases, send external communications",
				"",
				"### Selection Guide",
				"- Quick exploration? → ReAct",
				"- Need quality iteration? → Reflective",
				"- High stakes / needs approval? → Enterprise"
			].join("\n");
		}
	});
}
//#endregion
export { register as default };
