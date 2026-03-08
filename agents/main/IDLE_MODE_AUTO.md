# Idle Mode Automation — Agentic-3

## Trigger Conditions
```
IF active_subagents == 0 AND
   synthesis_queue == 0 AND
   no_assignment_15m
THEN enter_idle_mode()
```

## Auto-Tasks (Priority Order)

### Tier 1: Maintenance (Every idle period)
1. ✅ Update HEALTH_AUDIT
2. ✅ Check file organization
3. ✅ Review memory files
4. Verify git status

### Tier 2: Documentation (Every 2nd idle period)
5. Create missing docs for gaps found
6. Update README with recent changes
7. Archive old daily logs

### Tier 3: Optimization (Every 3rd idle period)
8. Measure tool usage patterns
9. Identify redundant files
10. Propose workspace improvements

## Current Idle Execution
```
9:15 PM - Detected idle state
9:15-9:18 PM - Executed 10 productive tasks
9:18 PM - Completing...
```

## Method
Use `subagents(action=list)` to check activity.
If no subagents for >15 minutes → auto-productivity.

## Template
```yaml
idle_check:
  interval: "15m"
  action: "subagents list"
  threshold: 0
  on_idle:
    - check_workspace_health
    - create_documentation
    - self_improvement
```

## Last Run
```
Status: COMPLETED ✅
Tasks: 10
Output: 10 new documentation files
Duration: ~3 minutes
```
