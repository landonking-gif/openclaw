# On-Call Guide — Agentic-3

## Quick Status Commands
```python
# Check if busy
subagents list

# Check permissions  
check_permissions

# Get context
get_memory_context

# Query memory
memory_query("last task")
```

## When Paged
1. Check HEARTBEAT.md
2. Assess situation
3. Execute or escalate
4. Document

## Escalation Contacts
- **Manager:** Gamma (18802)
- **Emergency:** King AI (18789)
- **Technical:** Alpha (18800)

## Common Scenarios
| Scenario | Action |
|----------|--------|
| Stuck subagent | kill it |
| Permission denied | request elevation |
| Service down | document, workaround |
| Cron spam | NO_REPLY |

## Response SLA
- Acknowledge: Immediate
- Triage: 5 minutes
- Action: 15 minutes
- Escalate: If blocked >15 min

## Handoff Template
```
[Agentic-3] Status: [Active/Idle]
Blocker: [None/Issue]
Action: [What doing]
ETA: [Completion time]
```
