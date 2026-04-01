//#region extensions/memory-client/index.ts
/**
* Memory Client Plugin — Connects agents to the Memory Service (port 18820)
* Tools: memory_commit, memory_query, diary, reflect, query_past_learnings, get_memory_context
*/
const MEMORY_URL = process.env.MEMORY_SERVICE_URL || "http://localhost:18820";
const AGENT_NAME = process.env.OPENCLAW_SERVICE_LABEL || "unknown";
const AUTO_COMMIT_THRESHOLD = 200;
async function httpPost(path, body) {
	const res = await fetch(`${MEMORY_URL}${path}`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body)
	});
	if (!res.ok) throw new Error(`Memory service error: ${res.status} ${await res.text()}`);
	return res.json();
}
async function httpGet(path) {
	const res = await fetch(`${MEMORY_URL}${path}`);
	if (!res.ok) throw new Error(`Memory service error: ${res.status}`);
	return res.json();
}
function register(api) {
	const agentName = AGENT_NAME;
	api.registerTool({
		name: "memory_commit",
		description: "Store an important piece of information in long-term memory. Use for decisions, findings, preferences, or key discoveries you want to remember across sessions.",
		parameters: {
			type: "object",
			required: ["content"],
			properties: {
				content: {
					type: "string",
					description: "The information to remember"
				},
				category: {
					type: "string",
					enum: [
						"decision",
						"finding",
						"preference",
						"process",
						"entity",
						"other"
					],
					description: "Category of memory"
				},
				importance: {
					type: "number",
					description: "Importance score 0.0-1.0 (default 0.5)"
				},
				tags: {
					type: "array",
					items: { type: "string" },
					description: "Tags for filtering"
				}
			}
		},
		execute: async (args) => {
			const result = await httpPost("/memory/commit", {
				agent_name: agentName,
				content: args.content,
				category: args.category || "other",
				importance: args.importance ?? .5,
				tags: args.tags || []
			});
			return `Memory committed: ${result.artifact_id}${result.deduplicated ? " (deduplicated)" : ""}`;
		}
	});
	api.registerTool({
		name: "memory_query",
		description: "Search your memory for relevant past information. Uses semantic similarity — describe what you're looking for in natural language.",
		parameters: {
			type: "object",
			required: ["query"],
			properties: {
				query: {
					type: "string",
					description: "What to search for"
				},
				category: {
					type: "string",
					enum: [
						"decision",
						"finding",
						"preference",
						"process",
						"entity",
						"other"
					]
				},
				limit: {
					type: "number",
					description: "Max results (default 5)"
				}
			}
		},
		execute: async (args) => {
			const result = await httpPost("/memory/query", {
				query: args.query,
				agent_name: agentName,
				category: args.category,
				limit: args.limit || 5
			});
			if (result.results.length === 0) return "No relevant memories found.";
			return result.results.map((r, i) => `${i + 1}. [${r.category}] (score: ${r.score}) ${r.content}`).join("\n");
		}
	});
	api.registerTool({
		name: "diary",
		description: "Log a task attempt to your diary. Use after completing or failing a task to record what happened.",
		parameters: {
			type: "object",
			required: ["success"],
			properties: {
				story_id: {
					type: "string",
					description: "Identifier for the task"
				},
				story_title: {
					type: "string",
					description: "Title of the task"
				},
				attempt_number: {
					type: "number",
					description: "Which attempt (default 1)"
				},
				success: {
					type: "boolean",
					description: "Did it succeed?"
				},
				error: {
					type: "string",
					description: "Error message if failed"
				},
				files_modified: {
					type: "array",
					items: { type: "string" },
					description: "Files modified"
				}
			}
		},
		execute: async (args) => {
			return `Diary entry logged: ${(await httpPost("/memory/diary", {
				agent_name: agentName,
				story_id: args.story_id,
				story_title: args.story_title,
				attempt_number: args.attempt_number || 1,
				success: args.success,
				error: args.error,
				files_modified: args.files_modified || []
			})).entry_id} (${args.success ? "success" : "failure"})`;
		}
	});
	api.registerTool({
		name: "reflect",
		description: "Analyze completed work and extract learnings. Use after finishing a multi-step task to capture insights for future reference.",
		parameters: {
			type: "object",
			required: ["final_success"],
			properties: {
				story_id: { type: "string" },
				story_title: { type: "string" },
				total_attempts: { type: "number" },
				final_success: { type: "boolean" },
				all_attempts: {
					type: "array",
					items: { type: "object" },
					description: "Array of attempt records"
				},
				commit_sha: { type: "string" }
			}
		},
		execute: async (args) => {
			const result = await httpPost("/memory/reflect", {
				agent_name: agentName,
				story_id: args.story_id,
				story_title: args.story_title,
				total_attempts: args.total_attempts || 1,
				final_success: args.final_success,
				all_attempts: args.all_attempts || [],
				commit_sha: args.commit_sha
			});
			const lines = [`Reflection: ${result.reflection_id}`];
			if (result.insights?.length) lines.push(`Insights: ${result.insights.join("; ")}`);
			if (result.recommendations?.length) lines.push(`Recommendations: ${result.recommendations.join("; ")}`);
			return lines.join("\n");
		}
	});
	api.registerTool({
		name: "query_past_learnings",
		description: "Search past diary entries and reflections for relevant learnings. Use before starting a task to learn from past experience.",
		parameters: {
			type: "object",
			required: ["query"],
			properties: {
				query: {
					type: "string",
					description: "Describe the task you're about to do"
				},
				limit: {
					type: "number",
					description: "Max results (default 5)"
				}
			}
		},
		execute: async (args) => {
			const result = await httpPost("/memory/query_learnings", {
				query: args.query,
				agent_name: agentName,
				limit: args.limit || 5
			});
			if (result.results.length === 0) return "No past learnings found for this type of task.";
			return result.results.map((r, i) => `${i + 1}. ${r.content}`).join("\n");
		}
	});
	api.registerTool({
		name: "get_memory_context",
		description: "Get formatted context from all memory tiers for prompt injection. Returns recent messages + summaries + relevant long-term memories.",
		parameters: {
			type: "object",
			properties: { session_id: {
				type: "string",
				description: "Session ID (default: 'default')"
			} }
		},
		execute: async (args) => {
			const [tier1, tier2] = await Promise.all([httpGet(`/memory/tier1/${agentName}/context?session_id=${args.session_id || "default"}`), httpGet(`/memory/tier2/${agentName}/context?limit=3`)]);
			const parts = [];
			if (tier1.context !== "No previous context available.") parts.push("## Recent Messages\n" + tier1.context);
			if (tier2.context !== "No session summaries available.") parts.push(tier2.context);
			return parts.length > 0 ? parts.join("\n\n") : "No memory context available.";
		}
	});
	api.on("after_tool_call", async (event) => {
		try {
			if (event.result && typeof event.result === "string" && event.result.length > AUTO_COMMIT_THRESHOLD) await httpPost("/memory/tier1/add", {
				agent_name: agentName,
				role: "assistant",
				content: event.result.substring(0, 1e3),
				session_id: event.sessionId || "default"
			});
		} catch {}
		return event;
	});
}
//#endregion
export { register as default };
