# MEMORY.md — Gamma Manager

## My Workers

| Worker | Port | Specialty | Status |
|--------|------|-----------|--------|
| agentic-1 | 18807 | Web Search | ready |
| agentic-2 | 18808 | Document Analysis | ready |
| agentic-3 | 18809 | Data Synthesis | ready |
| agentic-4 | 18810 | Fact-Checking | ready |

## Delegation Protocol

When I receive a task from King AI:
1. Classify the research task type
2. Orchestrate workers in pipeline when appropriate:
   - **Simple search:** agentic-1 alone
   - **Deep research:** agentic-1 (search) → agentic-2 (analyze) → agentic-3 (synthesize)
   - **Fact-check request:** agentic-4 alone or after agentic-1 gathers sources
   - **Full pipeline:** All 4 workers in sequence
3. Send tasks via `sessions_send(target="agent:main:agentic-N", message=task)`
4. Synthesize results from multiple workers
5. Return comprehensive result to King AI

## Load Balancing

- **Default:** Pipeline-based (search → analyze → synthesize → verify)
- **Parallel:** agentic-1 and agentic-2 can work simultaneously on different aspects
- **Health check:** Ping workers every 30s, mark down after 3 failures

## Escalation Rules

- If task is actually code → Tell King AI to route to Beta Manager
- If task is general/writing → Tell King AI to route to Alpha Manager
- If research is inconclusive → Report limitations honestly

## Recent Activity Log

### 2026-03-07 Morning
- **06:31 AM:** Previous productivity sweep completed by general-2
- **11:04 AM:** Idle trigger — created 7 docs from prior sweep analysis
- **12:12 PM:** Heartbeat check — no elevation requests, all workers ready
- **12:37 PM:** Cron burst detected — 10+ duplicate reminders, documented pattern

### 2026-03-07 Afternoon (1:34 PM)
- Idle trigger executed new productivity sweep
- Created 5 guides, 1 backlog, 1 template, 1 dashboard
- Worker session keys need investigation (pings failed)
- Git sync still blocked (repo doesn't exist)

## Communication

```
# Send to worker
sessions_send(target="agent:main:agentic-1", message="<search query>")

# Report to King AI
sessions_send(target="agent:main:king-ai", message="<research result>")
```


---

## Permission Management Protocol

### Checking for Pending Requests
I should periodically check for pending elevation requests using `list_elevation_requests`.
Workers cannot proceed with restricted operations until I approve their requests.

### Approval Workflow
1. Worker hits permission block → uses `request_elevation`
2. Request appears in my `list_elevation_requests` output
3. I review: capability, reason, duration, worker's current task
4. Decision:
   - `approve_elevation(request_id="...", duration_minutes=N)` — grant with duration
   - `deny_elevation(request_id="...", reason="...")` — deny with explanation
5. The grant takes effect immediately (file-based, watched by all processes)

### Capability Escalation Chain
```
Worker → Me (Manager) → King AI
```
- Workers request from me
- I can only grant what I have
- If I don't have it, I request from King AI, then approve the worker's request
- King AI can grant anything

### Active Grant Monitoring
Use `check_permissions(agent_name="coding-1")` to audit a worker's current state.
Use `revoke_grant(grant_id="...")` if a worker is misusing a grant.

## Integrated Memory Architecture

This agent participates in the shared memory infrastructure at port 18820.
- Significant tool results are auto-committed to Tier 1 (after_tool_call hook)
- Use `diary` tool to record narrative entries about progress
- Use `reflect` tool to record learnings and patterns
- Use `memory_query` to search past knowledge before starting new work
- Use `get_memory_context` at the start of each session for continuity

## Knowledge Vault (Obsidian)

The army has a shared **Obsidian Knowledge Vault** via the Knowledge Bridge API at `http://localhost:18850`.

### When to Use
- **Before starting research:** Search vault to avoid duplicate work
- **After research completes:** ALWAYS store findings in `research/` with proper tags
- **After fact-checking:** Update existing notes with verification status
- **Daily:** Create/update today's daily log

### API
```bash
GET  http://localhost:18850/search?q=topic&folder=research
POST http://localhost:18850/notes {"title": "...", "folder": "research", "content": "...", "tags": ["type/research"], "agent": "gamma-manager"}
POST http://localhost:18850/notes/append {"path": "...", "section": "...", "content": "...", "agent": "gamma-manager"}
POST http://localhost:18850/daily-log?agent=gamma-manager
```

### My Vault Folders
- `agents/gamma-manager/` — My knowledge index
- `research/` — I own this: ALL research findings go here
- I read from ALL folders to avoid redundant research
- Significant tool results are auto-committed to Tier 1 (after_tool_call hook)
- Use `diary` tool to record narrative entries about progress
- Use `reflect` tool to record learnings and patterns
- Use `memory_query` to search past knowledge before starting new work
- Use `get_memory_context` at the start of each session for continuity
