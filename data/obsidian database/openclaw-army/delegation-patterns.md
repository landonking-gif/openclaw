# Delegation Patterns

How the Meta-Orchestrator routes work to the 16-agent hierarchy.

## Core Principle

> **THINK FIRST, then delegate.**

The Meta-Orchestrator answers directly when possible. Delegation is a tool, not a default.

## Decision Tree

```
User Request
    │
    ├─→ Can I answer directly? ──→ YES → Respond immediately
    │                                    
    └─→ NO → Can I do it with tools? ──→ YES → Execute directly
    │                                          
    └─→ NO → What capability needed?
                │
                ├─→ Writing/MAC/Email ──→ Alpha Manager
                ├─→ Coding/Debug/Test ──→ Beta Manager
                └─→ Research/Analysis ──→ Gamma Manager
```

## Manager Capabilities

### Alpha Manager (Port 18800)
**Trigger:** writing, summarization, mac, email, communication

```python
delegate_to_alpha(
    task="Write a professional email to the team",
    priority=2
)
```

**Workers:**
- general-1: Writing & prose
- general-2: Summarization
- general-3: Q&A
- general-4: macOS automation

### Beta Manager (Port 18801)
**Trigger:** code, debug, test, deploy, infrastructure

```python
delegate_to_beta(
    task="Implement a REST API endpoint",
    priority=1
)
```

**Workers:**
- coding-1: Python
- coding-2: JavaScript/TypeScript
- coding-3: Bash/DevOps
- coding-4: Testing/QA

### Gamma Manager (Port 18802)
**Trigger:** research, search, analyze, fact-check

```python
delegate_to_gamma(
    task="Research the latest AI agent frameworks",
    priority=2
)
```

**Workers:**
- agentic-1: Web search
- agentic-2: Document analysis
- agentic-3: Data synthesis
- agentic-4: Fact-checking

## Parallel Delegation

Use batch_delegate for concurrent tasks:

```python
batch_delegate(tasks=[
    {"manager": "alpha", "task": "Draft email", "priority": 2},
    {"manager": "beta", "task": "Code feature", "priority": 1},
    {"manager": "gamma", "task": "Research competitors", "priority": 3}
])
```

## Direct Agent Messaging

Message any agent directly:

```python
agent_message(
    agent_name="coding-1",
    message="What's your current task?"
)
```

## Honesty Protocol

### Correct Language
- ❌ "I've completed this"
- ✅ "I'm delegating this to [manager]"
- ✅ "Dispatched to [manager] for execution"

### Completion Verification
```python
result = delegate_to_beta(task="implement feature")
if result.get("dispatched"):
    # Task is IN PROGRESS, not done
    await track_workflow(result["workflow_id"])
```

## Workflow Lifecycle

```
1. User Request
2. Orchestrator THINKS
3. DECIDE: Direct / Tools / Delegate
4. IF Delegate:
   a. Select manager by capability
   b. Create workflow
   c. Dispatch task
   d. Return workflow_id
5. Track workflow status
6. Synthesize results
7. Respond to user
```

## Capability Matching

```python
MANAGER_POOLS = {
    "alpha-manager": {
        "capabilities": [
            "writing", "prose", "summarization", "qa",
            "automation", "mac", "email", "communication"
        ]
    },
    "beta-manager": {
        "capabilities": [
            "code", "coding", "implement", "python",
            "debug", "test", "deploy", "docker"
        ]
    },
    "gamma-manager": {
        "capabilities": [
            "research", "search", "analysis", "data",
            "synthesis", "fact-check", "investigate"
        ]
    }
}
```

## Error Handling

### Delegation Failure
```python
result = delegate_to_beta(task="code")
if not result.get("dispatched"):
    # Self-heal and retry
    run_self_heal("beta-manager failed")
    result = delegate_to_beta(task="code")  # Retry once
```

### Timeout Handling
- Default timeout: 60 seconds
- Complex tasks: Extend timeout
- Failed: Self-heal + retry

## Best Practices

1. **Always think first** — Don't delegate reflexively
2. **Match capabilities** — Send to the right manager
3. **Parallel when possible** — Use batch_delegate
4. **Honest language** — Say "dispatched" not "done"
5. **Verify outcomes** — Track workflows to completion
6. **Self-heal on failure** — Retry after healing

## Related Notes

- [[Meta-Orchestrator]] — Makes delegation decisions
- [[Manager Agents]] — Who receives delegation
- [[Worker Agents]] — Who executes the work
- [[Self-Healing System]] — Recovery from failures

---

**Tags:** #delegation #workflow #routing #managers #patterns
