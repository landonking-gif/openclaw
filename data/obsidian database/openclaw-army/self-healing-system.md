# Self-Healing System

The OpenClaw Army has built-in **self-healing capabilities** to detect and recover from failures automatically.

## Overview

When components fail, the Meta-Orchestrator can:
1. **Detect** failures via health checks and delegation timeouts
2. **Diagnose** root causes using diagnostic tools
3. **Repair** by clearing locks, restarting services, rotating keys
4. **Verify** recovery through follow-up checks

## Self-Healing Tools

| Tool | Function |
|------|----------|
| `run_self_heal` | Clear locks, restart crashed managers, rotate API keys |
| `run_diagnostic` | Full health report of all 16 agents + 5 services |
| `query_failure_patterns` | Analyze recent error patterns |
| `restart_self` | Restart orchestrator process |

## The Self-Heal Procedure

```python
run_self_heal(reason="beta-manager delegation failed")
```

Actions performed:
1. **Clear stale locks** — Remove orphaned workflow locks
2. **Check all managers** — Verify alpha, beta, gamma responsiveness
3. **Restart crashed** — Spawn any dead managers
4. **Rotate API keys** — Refresh expired tokens
5. **Report fixes** — Log all actions taken

## Health Monitoring

### Diagnostic Report
```python
run_diagnostic()
```

Returns:
- Which agents are up/down
- Stale lock status
- System issues detected
- Port availability

### Failure Pattern Analysis
```python
query_failure_patterns(hours=24)
```

Shows:
- Error frequency
- Most affected managers
- Error types
- Time patterns

## Retry Protocol

After self-heal, follow this protocol:

1. **Call run_self_heal** with specific failure reason
2. **Wait for completion** — Self-heal returns success/failure
3. **Retry delegation** — Attempt the failed task again
4. **Report result** — If retry fails, report persistent failure

```python
# Example
result = delegate_to_beta(task="code review")
if not result.get("dispatched"):
    run_self_heal("beta-manager unresponsive")
    # Retry once
    result = delegate_to_beta(task="code review")
    if not result.get("dispatched"):
        report_persistent_failure()
```

## Automatic Recovery

### Process Watchdog
```python
process_watchdog(action="register",
    name="alpha-manager",
    command="python agents/alpha-manager/main.py",
    health_url="http://localhost:18800/health",
    interval=30,
    max_restarts=10
)
```

### Health Checks
- **Heartbeat timeout:** 60 seconds
- **Check interval:** 30 seconds
- **Max restarts:** 10 before giving up

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Delegation timeout | Manager crashed | restart_self_heal |
| Stale locks | Interrupted workflow | run_self_heal |
| API key expired | Token rotation needed | run_self_heal |
| Port conflict | Process didn't exit | port_manager kill |
| Memory full | ChromaDB/Redis saturation | Restart services |

## Proactive Monitoring

### Scheduled Health Checks
```python
schedule_task(
    name="hourly_health_check",
    interval=3600,
    handler_code="""
        result = await run_diagnostic()
        if result.get("issues"):
            await run_self_heal("proactive check found issues")
    """
)
```

### Quality Monitoring
```python
check_quality()
```

Detects:
- Response degradation over time
- Quality score trends
- Output consistency

## Integration with Memory

Self-healing events are logged:
- **Activity log** — All heal attempts
- **Memory Service** — Pattern learning
- **Obsidian** — Incident documentation

## Related Notes

- [[Meta-Orchestrator]] — Self-healing user
- [[Agent Registry]] — Health registration
- [[Process Watchdog]] — Auto-restart
- [[Memory Architecture]] — Persistence

---

**Tags:** #self-healing #reliability #recovery #health-monitoring #automation
