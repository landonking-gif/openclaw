---
title: OpenClaw Army Architecture
date: 2026-03-17
tags: [architecture, hierarchy, agents, ports]
author: Meta-Orchestrator
---

# Architecture

The OpenClaw Army uses a **3-tier hierarchical architecture**: King AI at the top, 3 Managers in the middle, 12 Workers at the bottom.

---

## Hierarchy Diagram

```
                    ┌─────────────┐
                    │   King AI   │ ◄── You command here
                    │   :18789    │     (Kimi K2.5)
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴──────┐  ┌─────┴──────┐  ┌─────┴──────┐
    │   Alpha    │  │   Beta     │  │   Gamma    │
    │  Manager   │  │  Manager   │  │  Manager   │
    │   :18800   │  │   :18801   │  │   :18802   │
    │  Kimi K2.5 │  │DeepSeek R1 │  │  Kimi K2.5 │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │               │               │
    ┌─────┴──────┐  ┌─────┴──────┐  ┌─────┴──────┐
    │ general-1  │  │ coding-1   │  │ agentic-1  │
    │ :18811     │  │ :18803     │  │ :18807     │
    │ (writing)  │  │ (Python)   │  │ (search)   │
    ├────────────┤  ├────────────┤  ├────────────┤
    │ general-2  │  │ coding-2   │  │ agentic-2  │
    │ :18812     │  │ :18804     │  │ :18808     │
    │(summarize) │  │ (JS/TS)    │  │ (documents)│
    ├────────────┤  ├────────────┤  ├────────────┤
    │ general-3  │  │ coding-3   │  │ agentic-3  │
    │ :18813     │  │ :18805     │  │ :18809     │
    │   (Q&A)    │  │ (Bash/Dev) │  │ (synthesis)│
    ├────────────┤  ├────────────┤  ├────────────┤
    │ general-4  │  │ coding-4   │  │ agentic-4  │
    │ :18814     │  │ :18806     │  │ :18810     │
    │ (Mac auto) │  │ (testing)  │  │(fact-check)│
    └────────────┘  └────────────┘  └────────────┘
```

---

## Agent Breakdown

### King AI (:18789)
- **Model:** Kimi K2.5 via NVIDIA API
- **Role:** Supreme commander, direct user interface
- **Capabilities:** 101 tools, self-modification, orchestration
- **Reports to:** Landon King (human owner)

### Alpha Manager (:18800)
- **Model:** Kimi K2.5
- **Domain:** General-purpose tasks
- **Workers:** [[managers#alpha-workers|general-1 through general-4]]
- **Capabilities:** Writing, summarization, Q&A, Mac automation

### Beta Manager (:18801)
- **Model:** DeepSeek R1
- **Domain:** Software engineering
- **Workers:** [[managers#beta-workers|coding-1 through coding-4]]
- **Capabilities:** Python, JavaScript, Bash, testing

### Gamma Manager (:18802)
- **Model:** Kimi K2.5
- **Domain:** Research & analysis
- **Workers:** [[managers#gamma-workers|agentic-1 through agentic-4]]
- **Capabilities:** Web search, document analysis, fact-checking

---

## Communication Flow

```
User → King AI → Manager → Worker
                    ↑
Worker → Manager → King AI → User
```

1. User speaks to King AI (me, the Meta-Orchestrator)
2. I decide: answer directly OR delegate to manager
3. Manager delegates to appropriate worker
4. Worker executes task
5. Results bubble back up the chain

---

## Port Range Strategy

| Range | Purpose |
|-------|---------|
| 18789 | King AI |
| 18800-18802 | Managers |
| 18803-18814 | Workers |
| 18820+ | Supporting services |
| 5432 | PostgreSQL |
| 6379 | Redis |

---

## Design Principles

1. **Hierarchical Command** - Clear chain of authority
2. **Specialized Workers** - Each agent has a focus
3. **Failover Capability** - Self-healing restarts crashed agents
4. **Sandboxed Security** - Workers restricted, managers can elevate
5. **Memory Persistence** - 3-tier storage across sessions

---

## See Also

- [[managers]] - Detailed manager documentation
- [[services]] - Supporting infrastructure
- [[security]] - Permission and sandboxing
- [[index]] - Return to master index
