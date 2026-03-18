j# OpenClaw Army - Architecture Overview

**Date:** March 17, 2026  
**Version:** 1.0  
**Owner:** [[Landon King]]  
**Codebase:** 13,881 lines, 101 internal tools

---

## Executive Summary

OpenClaw Army is a **16-agent hierarchical AI system** with 6 supporting services and a [[Meta-Orchestrator|self-evolving orchestrator]]. Built on free NVIDIA API models (Kimi K2.5), it demonstrates sophisticated multi-agent coordination with radical self-modification capabilities.

---

## System Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│  King AI (18789) - Kimi K2.5 via NVIDIA API            │
│  └─ Meta-Orchestrator (18830) - You are here           │
└───────────────────┬─────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───┴───┐      ┌───┴───┐      ┌───┴───┐
│ Alpha │      │ Beta  │      │ Gamma │
│:18800 │      │:18801 │      │:18802 │
│Kimi   │      │DeepSeek      │Kimi   │
│K2.5   │      │R1     │      │K2.5   │
└───┬───┘      └───┬───┘      └───┬───┘
    │              │              │
┌───┴───┐      ┌───┴───┐      ┌───┴───┐
│general│      │coding │      │agentic│
│ 1-4   │      │ 1-4   │      │ 1-4   │
│:18811 │      │:18803 │      │:18807 │
│ 18814 │      │ 18806 │      │ 18810 │
└───────┘      └───────┘      └───────┘
```

---

## Agent Count: 16 Total

| Level | Count | Agents |
|-------|-------|--------|
| Supreme | 1 | [[King AI]] |
| Orchestrator | 1 | [[Meta-Orchestrator]] (you) |
| Managers | 3 | [[Alpha Manager]], [[Beta Manager]], [[Gamma Manager]] |
| Workers | 12 | [[Worker Agents]] (4 per manager) |
| **Total** | **16** | + 6 supporting services |

---

## Supporting Services

| Service | Port | Purpose |
|---------|------|---------|
| [[Memory Service]] | 18820 | 3-tier memory: Redis + PostgreSQL + ChromaDB |
| [[Knowledge Bridge]] | 18850 | Obsidian vault API for persistent knowledge |
| [[Agent Registry]] | 18860 | Self-registration, heartbeat, capability discovery |
| [[Ralph]] | 18840 | Autonomous PRD-driven coding loop |
| [[Notification Service]] | 18870 | Email alerts via Gmail SMTP |
| Orchestrator API | 18830 | Meta-orchestrator (this system) |

---

## Infrastructure

- **PostgreSQL 17** (port 5432): Session storage, structured data
- **Redis** (port 6379): Caching, pub/sub, sliding window memory
- **ChromaDB**: Vector embeddings for semantic search
- **macOS LaunchD**: Auto-start on boot

---

## Key Capabilities

### [[Self-Healing System]]
- `run_self_heal`: Clears locks, restarts crashed managers, rotates API keys
- `run_diagnostic`: Full health report of all 16 agents
- Automatic retry with exponential backoff

### [[Self-Modification]]
- `modify_own_code`: Edit main.py live (with backup)
- `register_new_tool`: Create new capabilities at runtime
- `update_system_prompt`: Learn new behaviors persistently
- `learn_new_skill`: Create reusable multi-file skill packages

### [[101 Tools]]
From `run_shell_command` to `desktop_control` to `browser_automate` — full system access.

---

## Quality Metrics

- **98% pass rate** on 100-prompt stress test
- **2% timeout** (API latency, not capability failures)
- **0% hallucination** rate
- Avg response: 66s

---

## Related Notes

- [[Meta-Orchestrator]] ← You are here
- [[Manager Agents]]
- [[Worker Agents]]
- [[Memory Architecture]]
- [[101 Tools Reference]]
- [[Self-Healing System]]
- [[Delegation Patterns]]
- [[Services Overview]]
- [[Landon King]] - Owner & architect

---

*Last updated: March 17, 2026*
