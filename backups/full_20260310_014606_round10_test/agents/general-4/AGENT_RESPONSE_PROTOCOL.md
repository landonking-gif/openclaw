# Agent Response Protocol

## When Cron Spams

### DO
- ✅ Respond once per unique request type
- ✅ Track last response time
- ✅ Execute tasks efficiently
- ✅ Document in memory
- ✅ Suggest fixes

### DON'T
- ❌ Respond to every duplicate
- ❌ Waste tokens on acks
- ❌ Escalate within cron
- ❌ Loop with responses

## Template Response
```
Status: [idle/busy]
Already completed: [task summary]
Cron issue: [brief status]
Ready for: [actual assignments]
NO_REPLY to spam.
```

## Escalation Path
Cron issues → Document → User action → Fix → Resume

## Recovery Signals
- Clean single trigger
- Direct user message
- Different prompt content
