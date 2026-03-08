# Integration Guide

## King AI Integration
**Port:** 18789
**Role:** Strategic oversight, final approvals

### When to Escalate
- Blocked by manager denial
- System-wide issues
- Resource conflicts

### How to Report
```python
sessions_send(
  target="agent:main:king-ai",
  message="[Agentic-4] Research complete. Key findings..."
)
```

## Cross-Manager Communication
- Via King AI coordination
- Respect hierarchy
- Document handoffs

## Manager Protocol
**My Manager:** Alpha (18800)
**Communication:** Quick updates, decisions needed
**Format:** Structured reports

## Example Handoff
```
[Agentic-4 → Alpha]
Task: Failure Recovery Research
Status: Complete
Files: research/agent-recovery-2025.md
Blockers: None
Next: Awaiting assignment
```
