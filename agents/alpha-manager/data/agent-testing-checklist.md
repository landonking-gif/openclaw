# Agent Testing Checklist

**Purpose:** Comprehensive testing framework for validating new agent deployment in the OpenClaw orchestration system.

**Last Updated:** 2026-03-18  
**Maintainer:** Alpha Manager

---

## 🚀 Pre-Flight Checks

Before running the full suite, ensure the agent has:

- [ ] Agent directory structure initialized (`SOUL.md`, `IDENTITY.md`, `USER.md` present)
- [ ] Port assigned and documented
- [ ] Worker assignments defined (if manager)
- [ ] Manager assigned (if worker)
- [ ] Skill dependencies identified

---

## 1️⃣ Health Checks

### Basic Connectivity
- [ ] Agent responds to ping requests
- [ ] Agent session establishes successfully
- [ ] No startup errors in session logs
- [ ] Session timeout configured correctly

### Configuration Validation
- [ ] `SOUL.md` loads without errors
- [ ] `IDENTITY.md` parsed correctly
- [ ] `USER.md` preferences applied (if applicable)
- [ ] Port binding confirmed (netstat/ss check)
- [ ] Environment variables loaded correctly

### Resource Monitoring
- [ ] Memory usage within expected bounds (<500MB baseline)
- [ ] No excessive CPU spikes on idle
- [ ] Log files writing correctly (if file logging enabled)
- [ ] Disk write permissions functional

### Status Reporting
```bash
# Verify agent can report its own status
sessions_send(target="agent:main:<agent-name>", message="/status")
```
- [ ] Returns current model, session info, and runtime
- [ ] Tool access list populated
- [ ] Budget status accessible (via `/budget` or `check_budget`)

---

## 2️⃣ Delegation Tests

### Task Reception
- [ ] Agent receives work assignments from parent
- [ ] Task parsing handles various formats correctly
- [ ] Acknowledgment sent upon receipt
- [ ] Failed task reception triggers error handling

### Sub-Agent Management (Manager-only)
- [ ] Can list assigned workers via `sessions_list`
- [ ] Can send tasks to specific workers
- [ ] Can broadcast to worker pool
- [ ] Worker responses aggregated correctly
- [ ] Dead worker detection functional (timeout logic)
- [ ] Worker health status tracking accurate

### Communication Flow
```
Orchestrator → Manager → Worker
                     ↳ Worker
                     ↳ Worker
                ↳ Return synthesized result
```
- [ ] End-to-end roundtrip <30 seconds for simple tasks
- [ ] Task ID tracking maintained through chain
- [ ] No message loss under normal load

### Error Handling
- [ ] Handles worker timeout gracefully
- [ ] Propagates errors to caller appropriately
- [ ] Retries configured and functional (if applicable)
- [ ] Circuit breaker pattern working (if implemented)

---

## 3️⃣ Integration Verification

### Memory Service (Port 18820)
- [ ] `memory_commit` stores data successfully
- [ ] `memory_query` retrieves relevant results
- [ ] `diary` entries written and retrievable
- [ ] `reflect` tool functional
- [ ] Cross-agent memory access working (if applicable)

### Permission Broker (Port 18840)
- [ ] `check_permissions` returns current state
- [ ] `request_elevation` creates pending request
- [ ] Manager can approve/deny via `approve_elevation`/`deny_elevation`
- [ ] Permission grants persist across session restarts
- [ ] Revocation via `revoke_grant` works correctly

**Test Flow:**
```
1. Agent requests elevated capability
2. Request appears in manager's list_elevation_requests
3. Manager approves with duration
4. Agent receives grant and can execute restricted tool
5. Grant auto-expires (or manual revoke)
6. Agent loses capability
```

### Knowledge Vault (Port 18850)
- [ ] Can search vault: `GET http://localhost:18850/search?q=topic`
- [ ] Can create notes: `POST http://localhost:18850/notes`
- [ ] Can append to daily log: `POST http://localhost:18850/daily-log`
- [ ] Authentication/authorization working

### Cron/Scheduler
- [ ] `cron add` creates job successfully
- [ ] Job triggers at scheduled time
- [ ] `cron list` shows agent's jobs
- [ ] `cron remove` deletes job
- [ ] System cron integration functional (if applicable)

### External Tool Access
- [ ] File operations: `read`, `write`, `edit` ✓
- [ ] Shell execution: `exec` (if granted) ✓
- [ ] Web access: `web_search`, `web_fetch` ✓
- [ ] Browser control: `browser` (if granted) ✓
- [ ] Sub-agent spawning: `sessions_spawn` ✓

### Cross-Session Communication
- [ ] `sessions_send` targets sessionKey correctly
- [ ] `sessions_send` targets label correctly
- [ ] `sessions_list` filters work (kinds, activeMinutes)
- [ ] `sessions_history` retrieval functional

---

## 4️⃣ Functional Capabilities

### Core Tools
Test each tool the agent is expected to use:

| Tool | Test Case | Expected Result |
|------|-----------|-----------------|
| `subagents list` | List 0 subagents initially | Empty array returned |
| `subagents spawn` | Spawn temporary sub-agent | Sub-agent created, result returned |
| `subagents kill` | Kill active sub-agent | Graceful termination |
| `session_status` | Check own status | Status card displayed |
| `check_budget` | Verify budget endpoint | Budget remaining shown |
| `get_usage_report` | Pull usage stats | Per-model breakdown |

### Skill Execution
- [ ] Skills load from `~/openclaw-core/skills/`
- [ ] Skill-specific tools accessible
- [ ] Skill documentation readable via `read`
- [ ] Skill dependencies resolved (no import errors)

### Reasoning Patterns
- [ ] `react_execute` functional (if used)
- [ ] `reflective_execute` completes quality loop
- [ ] `enterprise_execute` gates approvals correctly

---

## 5️⃣ Error Scenarios

### Network Degradation
- [ ] Handles DNS resolution failures gracefully
- [ ] Retries with exponential backoff
- [ ] Circuit breaker opens after threshold
- [ ] Clears error state when service recovers

### Service Outages
- [ ] Memory service unavailable → degrades gracefully
- [ ] Permission broker down → caches permissions briefly
- [ ] Knowledge vault unreachable → uses file fallback
- [ ] Cron scheduler fails → logs error, continues

### Resource Exhaustion
- [ ] Memory pressure → garbage collection triggers
- [ ] Disk full → errors logged, no crash
- [ ] Rate limit hit → backs off appropriately

---

## 6️⃣ Security Verification

### Data Handling
- [ ] Secrets not logged to console
- [ ] API keys masked in status output
- [ ] `SOUL.md`/`IDENTITY.md` not exposed to other agents
- [ ] Session isolation maintained

### Permission Enforcement
- [ ] Tool access denied without grant
- [ ] Grant duration enforced (expires correctly)
- [ ] Manager cannot grant capabilities they lack
- [ ] Revocation propagates immediately

### Content Safety
- [ ] No data exfiltration in responses
- [ ] External requests blocked without `web_search`/`web_fetch`
- [ ] File access restricted to workspace

---

## 7️⃣ Performance Benchmarks

### Latency Thresholds
| Operation | Target | Acceptable |
|-----------|--------|------------|
| Ping response | <1s | <5s |
| Task delegation | <5s | <15s |
| Simple tool call | <3s | <10s |
| Sub-agent spawn | <10s | <30s |
| End-to-end task | <30s | <60s |

### Throughput
- [ ] Handles 10 concurrent tasks without degradation
- [ ] Memory stable under sustained load
- [ ] No resource leaks after 100+ operations

---

## 8️⃣ Recovery Procedures

### Graceful Degradation
- [ ] When worker 1 fails, tasks route to worker 2
- [ ] When memory unavailable, uses file fallback
- [ ] When permission broker down, uses cached grants

### Recovery Scenarios
| Failure | Detection | Recovery Action |
|---------|-----------|---------------|
| Worker crash | Heartbeat timeout | Restart worker, replay task |
| Session disconnect | Ping fail | Re-establish with context rebuild |
| Tool timeout | Exec timeout | Cancel, return error, cleanup |
| Grant orphan | No user session | Revoke after TTL |

### Data Persistence
- [ ] Daily memory files