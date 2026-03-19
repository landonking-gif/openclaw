# Agent Testing Checklist

> **Version:** 1.0  
> **Last Updated:** 2026-03-18  
> **Scope:** New agent onboarding in ai_final orchestration system  

---

## Quick Summary

This checklist verifies that new agents are fully functional before entering production. Covers health checks, delegation capabilities, tool access, and integration with the broader orchestration system.

---

## Phase 1: Pre-Deployment Setup

### Configuration Verification

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 1.1 | Agent `SKILL.md` exists and is valid | File present with complete description | [ ] |
| 1.2 | Port assignment defined in `config/agents.json` | Unique port, no conflicts | [ ] |
| 1.3 | Agent files in correct directory | `/agents/<agent-name>/` with required files | [ ] |
| 1.4 | Required files present | `SOUL.md`, `AGENTS.md`, `USER.md`, `HEARTBEAT.md`, `TOOLS.md` | [ ] |
| 1.5 | Manager relationship defined | `reports_to` and `manages` fields populated | [ ] |
| 1.6 | Tools/capabilities declared | `AGENTS.md` lists available skills/tools | [ ] |

### File Structure Requirements

```
/agents/<agent-name>/
├── SKILL.md              # Skill definition (if applicable)
├── SOUL.md               # Personality and role
├── AGENTS.md             # Core configuration
├── USER.md               # Context about human
├── HEARTBEAT.md          # Periodic task checklist
├── TOOLS.md              # Tool-specific notes
├── MEMORY.md             # Long-term memory
├── BOOTSTRAP.md          # First-run instructions (if exists)
└── memory/               # Session logs
```

---

## Phase 2: Health Checks

### 2.1 Service Availability

| # | Task | Command / Method | Expected Result | Status |
|---|------|------------------|-----------------|--------|
| 2.1.1 | Gateway service running | `openclaw gateway status` | `running` | [ ] |
| 2.1.2 | Agent port responsive | `curl -s http://localhost:<PORT>/health` | `{"status":"ok"}` | [ ] |
| 2.1.3 | Agent can respond to pings | Send test message | Response received < 5s | [ ] |
| 2.1.4 | No startup errors in logs | Check agent logs | No critical errors | [ ] |
| 2.1.5 | Memory service accessible | `memory_query` test query | Returns success | [ ] |

### 2.2 Resource Checks

| # | Task | Threshold | Status |
|---|------|-----------|--------|
| 2.2.1 | Memory usage | < 500MB | [ ] |
| 2.2.2 | CPU usage (idle) | < 10% | [ ] |
| 2.2.3 | Disk space for logs | > 1GB free | [ ] |
| 2.2.4 | File descriptor limits | > 1024 available | [ ] |

### 2.3 Configuration Validity

```bash
# Run these verification commands
openclaw agent validate <agent-name>
openclaw agent config <agent-name> --check
```

---

## Phase 3: Core Capabilities

### 3.1 Tool Access

| # | Tool | Test | Expected Result | Status |
|---|------|------|-----------------|--------|
| 3.1.1 | `read` | Read a test file | File contents returned | [ ] |
| 3.1.2 | `write` | Write to temp file | File created successfully | [ ] |
| 3.1.3 | `edit` | Modify test file | Precise edit applied | [ ] |
| 3.1.4 | `exec` | Run `echo "test"` | Command output returned | [ ] |
| 3.1.5 | `sessions_send` | Message to another agent | Delivery confirmed | [ ] |
| 3.1.6 | `sessions_spawn` | Spawn sub-agent | Sub-agent launches | [ ] |
| 3.1.7 | `memory_commit` | Store test memory | Committed successfully | [ ] |
| 3.1.8 | `memory_query` | Query test memory | Results returned | [ ] |

### 3.2 Permission System

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 3.2.1 | Agent can check permissions | `check_permissions()` returns data | [ ] |
| 3.2.2 | Agent can request elevation | `request_elevation()` call succeeds | [ ] |
| 3.2.3 | Manager can approve/deny requests | Approval/denial processes correctly | [ ] |
| 3.2.4 | Grant revocation works | `revoke_grant()` succeeds | [ ] |

### 3.3 Skill Integration

| # | Check | Status |
|-------|-------|--------|
| 3.3.1 | Agent can read relevant SKILL.md files | [ ] |
| 3.3.2 | Agent can use declared skills | [ ] |
| 3.3.3 | Skill tool calls succeed | [ ] |

---

## Phase 4: Delegation Tests

### 4.1 Manager → Worker

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 4.1.1 | Manager can send task to worker | `sessions_send(target="agent:main:worker-N")` | [ ] |
| 4.1.2 | Worker receives and processes task | Acknowledges receipt | [ ] |
| 4.1.3 | Worker returns result to manager | Response received < 60s | [ ] |
| 4.1.4 | Manager can spawn sub-agent | `sessions_spawn()` succeeds | [ ] |
| 4.1.5 | Manager can list subagents | `subagents list` returns active agents | [ ] |
| 4.1.6 | Manager can kill subagent | `subagents kill <id>` terminates agent | [ ] |

### 4.2 Worker → Manager

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 4.2.1 | Worker can report status to manager | Message delivered | [ ] |
| 4.2.2 | Worker can request elevation from manager | Request appears in manager's queue | [ ] |
| 4.2.3 | Worker receives approval response | Grant active | [ ] |
| 4.2.4 | Worker escalates to King AI when needed | Proper escalation chain | [ ] |

### 4.3 Workload Distribution

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 4.3.1 | Round-robin assignment works | Tasks distributed evenly | [ ] |
| 4.3.2 | Specialty-based routing works | Tasks go to correct agent | [ ] |
| 4.3.3 | Fallback routing works | Overflow handled correctly | [ ] |
| 4.3.4 | Health-based routing works | Unhealthy agents excluded | [ ] |

---

## Phase 5: Integration Verification

### 5.1 Orchestrator Integration

| # | Component | Test | Status |
|---|-----------|------|--------|
| 5.1.1 | Workflow reception | Receives tasks from orchestrator | [ ] |
| 5.1.2 | Subtask completion | Reports subtask results | [ ] |
| 5.1.3 | Progress reporting | Sends periodic updates | [ ] |
| 5.1.4 | Error reporting | Properly reports failures | [ ] |
| 5.1.5 | Heartbeat handling | Responds to heartbeat polls | [ ] |

### 5.2 Knowledge Vault Integration

| # | Task | Expected Result | Status |
|---|------|-----------------|--------|
| 5.2.1 | Can search Knowledge Vault | `GET /search` returns results | [ ] |
| 5.2.2 | Can create vault notes | `POST /notes` succeeds | [ ] |
| 5.2.3 | Can append to daily log | `POST /daily-log` succeeds | [ ] |

### 5.3 Memory Service Integration

| # | Tier | Test | Status |
|---|------|------|--------|
| 5.3.1 | Tier 1 (Redis) | Recent context accessible | [ ] |
| 5.3.2 | Tier 2 (PostgreSQL) | Session summaries stored | [ ] |
| 5.3.3 | Tier 3 (ChromaDB) | Vector search functional | [ ] |
| 5.3.4 | `diary` entries | Task logs committed | [ ] |
| 5.3.5 | `reflect` tool | Learnings extracted | [ ] |

### 5.4 Cost Tracking Integration

| # | Task | Status |
|---|------|--------|
| 5.4.1 | LLM calls tracked in cost system | [ ] |
| 5.4.2 | `check_budget()` returns data | [ ] |
| 5.4.3 | `get_usage_report()` works | [ ] |

---

## Phase 6: Error Handling & Recovery

### 6.1 Failure Scenarios

| # | Scenario | Expected Behavior | Status |
|---|----------|-------------------|--------|
| 6.1.1 | Tool timeout | Graceful error, no crash | [ ] |
| 6.1.2 | Tool not found | Clear error message | [ ] |
| 6.1.3 | Permission denied | Proper rejection with reason | [ ] |
| 6.1.4 | Worker unavailable | Fallback to other workers | [ ] |
| 6.1.5 | Memory service down | Degraded mode, file fallback | [ ] |
| 6.1.6 | Network partition | Retries with backoff | [ ] |

### 6.2 Recovery Procedures

| # | Action | Verification | Status |
|---|--------|------------|--------|
| 6.2.1 | Agent restart | Recovers state | [ ] |
| 6.2.2 | Gateway restart | Reconnects successfully | [ ] |
| 6.2.3 | Clear memory state | Clean restart | [ ] |

---

## Phase 7: Performance & Load

### 7.1 Baseline Metrics

| # | Metric | Baseline | Test Result |
|---|--------|----------|-------------|
| 7.1.1 | Cold start time | < 30s | [ ] |
| 7.1.2 | Tool call latency | < 2s | [ ] |
| 7.1.3 | Delegation round-trip | < 10s | [ ] |
| 7.1.4 | Memory commit latency | < 500ms | [ ] |

### 7.2 Load Testing

| # | Scenario | Requests | Duration | Status |
|---|----------|----------|----------|--------|
| 7.2.1 | Concurrent tool calls | 10 | 60s | [ ] |
| 7.2.2 | Rapid delegation | 50 | 60s | [ ] |
| 7.2.3 | Mixed workload | 100 | 120s | [ ] |

### 7.3 Resource Under Load

| # | Metric | Max Acceptable | Status |
|---|--------|----------------|--------|
| 7.3.1 | Memory growth | < 20% over baseline | [ ] |
| 7.3.2 | CPU spikes | < 80% sustained | [ ] |
| 7.3.3 | Error rate | < 1% | [ ] |
| 7.3.4 | Latency p95 | < 5s | [ ] |

---

## Phase 8: Security & Compliance

### 8.1 Permission Audit

| # | Check | Status |
|---|-------|--------|
| 8.1.1 | No excessive permissions granted | [ ] |
| 8.1.2 | `exec` access justified and documented | [ ] |
| 8.1.3 | `broadcast` capability restricted | [ ] |
| 8.1.4 | Grant durations reasonable | [ ] |
| 8.1.5 | `revoke_grant` tested | [ ] |

### 8.2 Data Handling

| # | Check | Status |
|---|-------|--------|
| 8.2.1 | No secrets in logs | [ ] |
| 8.2.2 | No PII in memory files | [ ] |
| 8.2.3 | Proper file permissions on data dir | [ ] |
| 8.2.4 | Sensitive data excluded from cross-session sync | [ ] |

---

## Phase 9: Documentation

### 9.1 Required Documentation

| # | Document | Status |
|---|----------|--------|
| 9.1.1 | `SOUL.md` - Personality defined | [ ] |
| 9.1.2 | `AGENTS.md` - Role and tools documented | [ ] |
| 9.1.3 | `TOOLS.md` - Environment notes | [ ] |
| 9.1.4 | `HEARTBEAT.md` - Periodic tasks listed | [ ] |
| 9.1.5 | `USER.md` - Human context | [ ] |

### 9.2 Code/Content Quality

| # | Check | Status |
|---|-------|--------|
| 9.2.1 | No TODO/FIXME markers in config | [ ] |
| 9.2.2 | Consistent naming conventions | [ ] |
| 9.2.3 | Clear error messages | [ ] |
| 9.2.4 | Proper observability (logging) | [ ] |

---

## Completion Checklist

### Pre-Production Sign-Off

- [ ] All Phase 1 checks passed
- [ ] All Phase 2 checks passed
- [ ] All Phase 3 checks passed
- [ ] All Phase 4 checks passed
- [ ] All Phase 5 checks passed
- [ ] All Phase 6 checks passed
- [ ] All Phase 7 checks passed
- [ ] All Phase 8 checks passed
- [ ] All Phase 9 checks passed

### Approvals Required

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Tested By | | | |
| Manager Review | | | |
| King AI Sign-Off | | | |

---

## Notes

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Port already in use | Another agent using port | Check `config/agents.json` for conflicts |
| Permission denied | Grant not approved | Manager must approve `request_elevation` |
| Skill not found | SKILL.md missing | Verify skill is installed via `clawhub` |
| Memory service error | OpenAI key issue | Fallback to file-based memory |
| Worker not responding | Session not active | Spawn new session for worker |

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-18 | Initial release |

---

**End of Checklist**


---
