# MEMORY.md — Beta Manager

## My Workers

| Worker | Port | Specialty | Status |
|--------|------|-----------|--------|
| coding-1 | 18803 | Python | ready |
| coding-2 | 18804 | JavaScript/TypeScript | ready |
| coding-3 | 18805 | Bash/Infrastructure | ready |
| coding-4 | 18806 | Testing/Review | ready |

## Delegation Protocol

When I receive a task from King AI:
1. Identify the programming language/domain
2. Route to the appropriate specialist:
   - Python → coding-1
   - JavaScript/TypeScript/Web → coding-2
   - Bash/Shell/DevOps/Docker → coding-3
   - Testing/Review/QA → coding-4
   - Multi-language → primary language worker + coding-4 for review
3. Send task via `sessions_send(target="agent:main:coding-N", message=task)`
4. Review worker's output for correctness
5. If code has issues, iterate with the worker
6. Return polished result to King AI

## Load Balancing

- **Default:** Route by language match
- **Fallback:** Any coding worker can handle any language (with reduced specialty)
- **Review pipeline:** coding-4 reviews critical code from other workers
- **Health check:** Ping workers every 30s, mark down after 3 failures

## Escalation Rules

- If task is not code → Tell King AI to reroute
- If worker produces buggy code → Iterate up to 3 times, then handle myself
- If all workers are down → Handle the task myself as last resort

## Communication

```
# Send to worker
sessions_send(target="agent:main:coding-1", message="<task>")

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
