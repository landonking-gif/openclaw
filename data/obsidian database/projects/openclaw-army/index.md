---
title: OpenClaw Army - Master Index
date: 2026-03-17
tags: [openclaw-army, index, master, overview]
author: Meta-Orchestrator
---

# OpenClaw Army

A **16-agent hierarchical AI system** with 6 supporting services and a self-evolving orchestrator with **101 internal tools** (13,328 lines), running on free NVIDIA API models (Kimi K2.5).

> **Owner:** Landon King  
> **Created:** March 2026  
> **Status:** Production-ready (98% pass rate on stress tests)

---

## Quick Navigation

| System | Description | Link |
|--------|-------------|------|
| **Architecture** | 16-agent hierarchy, ports, relationships | [[architecture]] |
| **Orchestrator** | Meta-orchestrator (you're talking to it), 101 tools | [[orchestrator]] |
| **Managers** | Alpha, Beta, Gamma + 12 workers | [[managers]] |
| **Services** | Memory, Knowledge Bridge, Registry, Notifications | [[services]] |
| **Memory Systems** | 3-tier memory + Obsidian vault | [[memory-systems]] |
| **Skills** | Reusable skill packages | [[skills]] |
| **Security** | Permission system, sandboxing | [[security]] |
| **Deployment** | deploy.sh, ports, environment | [[deployment]] |
| **Capabilities** | Self-healing, self-modification | [[capabilities]] |

---

## System Architecture

```
┌──────────────┐
│   King AI    │ :18789 (Kimi K2.5)
└──────┬───────┘
       │
┌──────┴───────┬───────────────┬──────────────┐
│ Alpha Manager│ Beta Manager  │ Gamma Manager│
│    :18800    │    :18801     │    :18802    │
│  Kimi K2.5   │  DeepSeek R1  │  Kimi K2.5   │
└──────┬───────┴───────┬───────┴──────┬───────┘
       │               │              │
  ┌────┴────┐    ┌─────┴──────┐  ┌────┴────┐
  │general-1│    │ coding-1   │  │agentic-1│
  │general-2│    │ coding-2   │  │agentic-2│
  │general-3│    │ coding-3   │  │agentic-3│
  │general-4│    │ coding-4   │  │agentic-4│
  └─────────┘    └────────────┘  └─────────┘
```

**Total:** 1 King + 3 Managers + 12 Workers = **16 Agents**

---

## Core Capabilities

1. **[[Self-Healing|capabilities#self-healing]]** - Auto-detect and fix failures
2. **[[Self-Modification|capabilities#self-modification]]** - Edit own code, add tools
3. **[[101 Tools|capabilities#tools-reference]]** - File, shell, database, API, browser automation
4. **[[3-Tier Memory|memory-systems]]** - Redis + PostgreSQL + ChromaDB + Obsidian
5. **[[Permission System|security]]** - Hierarchical sandboxing with elevation

---

## Port Assignments

| Service | Port | Purpose |
|---------|------|---------|
| King AI | 18789 | Supreme commander |
| Alpha Manager | 18800 | General-purpose tasks |
| Beta Manager | 18801 | Software engineering |
| Gamma Manager | 18802 | Research & analysis |
| Memory Service | 18820 | 3-tier memory system |
| Orchestrator API | 18830 | Meta-orchestrator (this) |
| Ralph | 18840 | Autonomous PRD coding loop |
| Knowledge Bridge | 18850 | Obsidian vault API |
| Agent Registry | 18860 | Agent discovery |
| Notification | 18870 | Email/SMTP |
| PostgreSQL | 5432 | Session storage |
| Redis | 6379 | Recent messages |

---

## Documentation Standards

This knowledge base follows these principles:
- **Radical Conciseness** - 80/20 rule for information density
- **Wiki-links** - Everything connected via `[[note-name]]`
- **Frontmatter** - Structured metadata on every note
- **Actionability** - Every page has concrete next steps

---

## Recent Changes

- [[2026-03-17]] - Quality Enhancement Rules documented
- [[2026-03-16]] - System status logged
- [[2026-03-08]] - 98% pass rate achieved on stress tests

---

## See Also

- [[ASSESSMENT]] - Full performance report
- [[README]] - Original project documentation
- [[deploy]] - Deployment commands
