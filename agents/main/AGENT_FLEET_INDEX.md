# OpenClaw Army - Agent Fleet Index

## Overview
**Total Agents:** 16  
**Architecture:** 1 King + 3 Managers + 12 Workers

---

## Tier 1: Meta-Orchestrator

### King AI (main)
- **Port:** 18789
- **Model:** kimi-k2.5
- **Role:** Strategic planning, task decomposition, coordination
- **Reports To:** User (you)
- **Direct Reports:** alpha-manager, beta-manager, gamma-manager
- **Workspace:** `/Users/landonking/openclaw-army/agents/main/`

---

## Tier 2: Managers (3)

### Alpha Manager
- **Port:** 18800
- **Role:** Communication & coordination lead
- **Handles:** Email, messaging, notifications, scheduling
- **Reports To:** King AI
- **Direct Reports:** general-1, general-2, general-3, general-4

### Beta Manager
- **Port:** 18801
- **Role:** Implementation & execution lead
- **Handles:** Code review, CI/CD, deployments, system operations
- **Reports To:** King AI
- **Direct Reports:** coding-1, coding-2, coding-3, coding-4

### Gamma Manager
- **Port:** 18802
- **Role:** Research & analysis lead
- **Handles:** Web research, data analysis, trend monitoring
- **Reports To:** King AI
- **Direct Reports:** agentic-1, agentic-2, agentic-3, agentic-4

---

## Tier 3: Workers (12)

### General Agents (4)
| Agent | Purpose |
|-------|---------|
| general-1 | Multi-purpose assistance |
| general-2 | Multi-purpose assistance |
| general-3 | Multi-purpose assistance |
| general-4 | Multi-purpose assistance |

### Coding Agents (4)
| Agent | Purpose |
|-------|---------|
| coding-1 | Code implementation |
| coding-2 | Code implementation |
| coding-3 | Code implementation |
| coding-4 | Code implementation |

### Agentic Agents (4)
| Agent | Purpose |
|-------|---------|
| agentic-1 | Research & analysis |
| agentic-2 | Research & analysis |
| agentic-3 | Research & analysis |
| agentic-4 | Research & analysis |

---

## System Services

| Service | Port | Purpose |
|---------|------|---------|
| Memory Service | 18820 | 3-tier memory (Redis, PostgreSQL, ChromaDB) |
| Orchestrator | 18830 | Task decomposition & workflow tracking |
| Knowledge Vault | 18850 | Shared Obsidian vault |

---

## Heartbeat Status
| Agent | Status | Interval |
|-------|--------|----------|
| main (King) | ✅ Enabled | 30m |
| All others | ❌ Disabled | — |

---

## Workspace Paths

```
/Users/landonking/openclaw-army/agents/
├── main/                  # King AI workspace
│   ├── memory/
│   ├── AGENTS.md
│   ├── SOUL.md
│   └── memory/
├── alpha-manager/
├── beta-manager/
├── gamma-manager/
├── general-1 through 4/
├── coding-1 through 4/
└── agentic-1 through 4/
```

---

*Last Updated: 2026-03-07*
