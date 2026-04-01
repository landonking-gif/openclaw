# King AI v2 Architecture Overview

King AI v2 is an autonomous AI CEO system designed to operate businesses with minimal human oversight. The architecture follows a **hierarchical agent model** with three core layers.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MASTER BRAIN                           │
│              (Strategic Decision Engine)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │Manager │  │Manager │  │Manager │
    │Alpha   │  │Beta    │  │Gamma   │
    │(18800) │  │(18801) │  │(18802) │
    └───┬────┘  └────┬───┘  └───┬────┘
        │            │          │
   ┌────┴─────┬──────┴────┬─────┴─────┐
   ▼          ▼           ▼           ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Worker│ │Worker  │ │Worker  │ │Worker  │
│Pool  │ │Pool    │ │Pool    │ │Pool    │
└──────┘ └────────┘ └────────┘ └────────┘
```

## Core Components

### 1. Master Brain
The central orchestration layer responsible for:
- **Goal decomposition**: Breaking high-level business objectives into actionable subtasks
- **Resource allocation**: Distributing work across manager agents
- **Quality assurance**: Validating outputs before final delivery
- **Exception handling**: Escalating edge cases requiring human intervention

### 2. LLM Router
Dynamic model selection based on task requirements:

| Task Type | Preferred Model | Reasoning |
|-----------|----------------|-----------|
| Code generation | claude-opus-4 | Superior coding capabilities |
| Analysis/Research | o1-pro | Deep reasoning, chain-of-thought |
| Quick tasks | gpt-4o-mini | Cost-effective, fast |
| Creative writing | kimi-k2.5 | Natural language flow |
| Image generation | DALL-E 3 | Native integration |

**Routing Logic:**
```python
if task.complexity > 0.8 and task.type == "coding":
    return "claude-opus-4"
elif task.requires_reasoning:
    return "o1-pro"
elif task.budget_constrained:
    return "gpt-4o-mini"
```

### 3. Agent Mesh
16 specialized agents organized by domain:

- **Alpha Manager (18800)**: General coordination, synthesis, polish
- **Beta Manager (18801)**: Software development, coding tasks
- **Gamma Manager (18802)**: Research, data analysis, knowledge synthesis
- **Worker Pool**: 12 domain-specific workers (4 per manager)

## Communication Protocol

All inter-agent communication uses structured JSON:

```json
{
  "workflow_id": "uuid",
  "subtask_id": "uuid",
  "priority": 1-5,
  "task": "description",
  "context": {},
  "deadline": "ISO-8601",
  "callback_url": "http://..."
}
```

## Port Assignments

| Service | Port | Purpose |
|---------|------|---------|
| Master Brain | 18789 | Central orchestration |
| Alpha Manager | 18800 | General tasks |
| Beta Manager | 18801 | Coding tasks |
| Gamma Manager | 18802 | Research tasks |
| Knowledge Bridge | 18850 | Obsidian integration |
| Memory Service | 18820 | 3-tier memory system |
| Permission Broker | 18840 | Elevation requests |

## Key Design Principles

1. **Single Source of Truth**: Master Brain maintains canonical state
2. **Graceful Degradation**: Failed agents don't cascade failures
3. **Observable**: All decisions logged with trace IDs
4. **Reversible**: Operations designed for rollback

---
**Related:** [[business-lifecycle]] | [[risk-approval-system]] | [[comparison-openclaw]]
