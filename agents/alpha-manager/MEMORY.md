# MEMORY.md — Alpha Manager

## My Workers

| Worker | Port | Specialty | Status |
|--------|------|-----------|--------|
| general-1 | 18811 | Writing/Content | ✅ online (was JS error, now active) |
| general-2 | 18812 | Summarization | ✅ online (was JS error, now active) |
| general-3 | 18813 | Q&A | ✅ online |
| general-4 | 18814 | Mac Automation | ✅ online (was JS error, now active) |

*Note:* All workers showing JS errors on 2026-03-08 morning but sessions confirmed active by evening. Ping timeouts were misleading.

## Delegation Protocol

When I receive a task from King AI:
1. Classify the task type (writing, summary, Q&A, automation, or mixed)
2. Select the best worker based on specialty
3. Send task via `sessions_send(target="agent:main:general-N", message=task)`
4. Wait for worker response
5. Polish/synthesize the result if needed
6. Return result to King AI

## Load Balancing

- **Default:** Route by specialty match
- **Fallback:** Round-robin among available workers
- **Overloaded:** Queue and process sequentially
- **Health check:** Ping workers every 30s, mark down after 3 failures

## Escalation Rules

- If task is actually code → Tell King AI to route to Beta Manager
- If task requires research → Tell King AI to route to Gamma Manager
- If all my workers are down → Handle the task myself as last resort

## Communication

```
# Send to worker
sessions_send(target="agent:main:general-1", message="<task>")

# Report to King AI
sessions_send(target="agent:main:king-ai", message="<result>")
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

## Known System Issues (2026-03-08)

### GitHub Sync Failures
- **Status:** Local commits succeed, push fails with 401/403
- **Root Cause:** GitHub repo `landonking/openclaw-army` either doesn't exist or lacks auth
- **History:** Multiple commits saved locally (28c2184, ef6c78f, 0b7f912, 00fd083, 684e5d7)
- **Resolution:** Needs `gh auth status` check and repo creation or auth fix

### Elevation System Degraded
- **Status:** `list_elevation_requests` failing with "Cannot find elevation request file"
- **Impact:** Cannot approve worker elevation requests
- **Possible Cause:** Permission-broker state file missing/corrupted, or port 18840 unavailable
- **Workaround:** Workers may need to request elevation directly from King AI

### Cron Job Noise
- **Status:** Multiple duplicate error messages every 15-30 minutes
- **Types:** 410 API errors, 400 "single tool-call" errors, permission denied, GitHub 404
- **Impact:** Alert fatigue from same root causes
- **Note:** Consider disabling or fixing cron config to reduce log spam

## Known System Issues (2026-03-09)

### GitHub Sync Still Failing
- **Status:** Repo `landonking/openclaw-army` does not exist on GitHub
- **Remote URL:** `https://github.com/landonking/openclaw-army.git`
- **Local commits:** Working perfectly (4 files, 8,692 lines today)
- **Error pattern:** DNS resolution (earlier) → now "repo not found"
- **Root cause:** Repository was never created on GitHub
- **Resolution options:** 
  1. Create repo at https://github.com/new
  2. Run `gh repo create openclaw-army --source=. --push`
  3. Update remote to correct URL if different

### Memory Service Down
- **Status:** `memory_search` unavailable
- **Error:** OpenAI API key 401 (invalid)
- **Impact:** Cannot use memory commit/query/reflect tools
- **Workaround:** Rely on file-based memory in `memory/` directory

### Elevation System
- **Status:** Degraded — `list_elevation_requests` still returning errors
- **Workaround:** Workers elevated via manager approval (King AI or me) when needed

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
- **Before delegating:** Search vault for relevant prior work on the topic
- **After task completion:** Store polished results as vault notes (research, code-patterns, etc.)
- **When synthesizing:** Pull related notes to enrich combined outputs
- **Daily:** Create/update today's daily log

### API
```bash
GET  http://localhost:18850/search?q=topic
POST http://localhost:18850/notes {"title": "...", "folder": "research", "content": "...", "tags": ["type/research"], "agent": "alpha-manager"}
POST http://localhost:18850/notes/append {"path": "...", "section": "...", "content": "...", "agent": "alpha-manager"}
POST http://localhost:18850/daily-log?agent=alpha-manager
```

### My Vault Folders
- `agents/alpha-manager/` — My knowledge index
- I write to `research/` and `projects/` for synthesized outputs
- I read from ALL folders to inform task delegation
