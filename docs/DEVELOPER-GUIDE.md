# OpenClaw Army — Developer Guide

> **Version:** 1.0 | **Last Updated:** March 7, 2026  
> **Codebase:** `/Users/landonking/openclaw-army/`  
> **Total LOC:** ~6,200 (4,568 Python/Shell/SQL/YAML + 1,616 TypeScript)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Infrastructure Layer](#infrastructure-layer)
4. [Service Layer — Complete Reference](#service-layer--complete-reference)
5. [Agent Layer — Configuration & Identity](#agent-layer--configuration--identity)
6. [Extension Layer — TypeScript Plugins](#extension-layer--typescript-plugins)
7. [Database Schema](#database-schema)
8. [Configuration Files](#configuration-files)
9. [Deployment System](#deployment-system)
10. [Security Model](#security-model)
11. [Inter-Service Communication](#inter-service-communication)
12. [Obsidian Vault Integration](#obsidian-vault-integration)
13. [YAML Workflow Engine](#yaml-workflow-engine)
14. [Structured Logging & Observability](#structured-logging--observability)
15. [PII Redaction System](#pii-redaction-system)
16. [Token Budget Manager](#token-budget-manager)
17. [Adding New Agents](#adding-new-agents)
18. [Adding New Services](#adding-new-services)
19. [Testing](#testing)
20. [Known Limitations](#known-limitations)
21. [Design Decisions & ADRs](#design-decisions--adrs)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    OpenClaw Gateway (King AI :18789)                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │   ORCHESTRATOR API   │
                    │      :18830          │
                    │  Task decomposition  │
                    │  YAML workflows      │
                    │  WebSocket events    │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │ Alpha Manager │    │ Beta Manager  │    │ Gamma Manager│
   │ :18800       │    │ :18801       │    │ :18802       │
   │ Kimi K2.5    │    │ DeepSeek R1  │    │ Kimi K2.5    │
   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
          │                    │                    │
    ┌──┬──┼──┐          ┌──┬──┼──┐          ┌──┬──┼──┐
    ▼  ▼  ▼  ▼          ▼  ▼  ▼  ▼          ▼  ▼  ▼  ▼
   g1 g2 g3 g4        c1 c2 c3 c4        a1 a2 a3 a4
   11 12 13 14        03 04 05 06        07 08 09 10
   Kimi  Kimi         DeepSeek R1        GLM-5  Kimi

┌─────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                 │
│  ┌──────────┐ ┌───────┐ ┌─────────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Memory   │ │ Ralph │ │ Knowledge   │ │ Agent    │ │ Notif.   │ │
│  │ Service  │ │       │ │ Bridge      │ │ Registry │ │ Service  │ │
│  │ :18820   │ │:18840 │ │ :18850      │ │ :18860   │ │ :18870   │ │
│  └────┬─────┘ └───────┘ └──────┬──────┘ └──────────┘ └──────────┘ │
│       │                         │                                    │
│  ┌────┴────────────────┐  ┌────┴──────────────────┐                 │
│  │ PostgreSQL :5432    │  │ Obsidian Vault        │                 │
│  │ Redis      :6379    │  │ data/obsidian database│                 │
│  └─────────────────────┘  └───────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Hierarchy** — King → Manager → Worker. Every task flows through the chain of command.
2. **Specialization** — Each agent has one domain. Workers never cross-specialize.
3. **Isolation** — Each agent runs in its own process with its own port. No shared state except via services.
4. **Least Privilege** — Workers have minimal permissions. Elevation requires manager approval.
5. **Free Inference** — All models are free via NVAPI. Zero API cost.
6. **Local-First** — Everything runs on localhost. No cloud dependencies except NVAPI inference.

---

## Directory Structure

```
openclaw-army/
├── .env                              # Master configuration (ports, keys, limits)
├── .gitignore
├── README.md                         # Project overview
├── deploy.sh                         # Unified deployment script (~543 lines)
│
├── agents/                           # 16 agent directories
│   ├── main/                         # King AI (meta-orchestrator)
│   │   ├── openclaw.json             # Agent config (model, auth, workspace)
│   │   ├── .openclaw/                # Runtime state
│   │   ├── .pi/                      # Private identity
│   │   ├── AGENTS.md                 # Inter-agent communication guide
│   │   ├── HEARTBEAT.md              # Health monitoring config
│   │   ├── IDENTITY.md               # Role and personality
│   │   ├── MEMORY.md                 # Memory access patterns, vault integration
│   │   ├── SOUL.md                   # Core values, decision framework
│   │   ├── TOOLS.md                  # Available tools and APIs
│   │   └── USER.md                   # User interaction patterns
│   ├── alpha-manager/                # Same structure as main/
│   ├── beta-manager/
│   ├── gamma-manager/
│   ├── coding-1/ ... coding-4/
│   ├── agentic-1/ ... agentic-4/
│   └── general-1/ ... general-4/
│
├── services/                         # 6 FastAPI services
│   ├── memory-service/
│   │   ├── main.py                   # ~778 lines — 3-tier memory, PII, budget
│   │   └── requirements.txt
│   ├── orchestrator-api/
│   │   ├── main.py                   # ~877 lines — Task routing, workflows
│   │   └── requirements.txt
│   ├── ralph/
│   │   ├── ralph.py                  # ~486 lines — Autonomous PRD coding
│   │   └── requirements.txt
│   ├── knowledge-bridge/
│   │   ├── main.py                   # ~447 lines — Obsidian vault REST API
│   │   └── requirements.txt
│   ├── agent-registry/
│   │   ├── main.py                   # ~240 lines — Registration, heartbeat
│   │   └── requirements.txt
│   ├── notification/
│   │   ├── main.py                   # ~198 lines — Gmail SMTP
│   │   └── requirements.txt
│   └── shared/
│       └── logging_middleware.py      # ~86 lines — Correlation IDs
│
├── extensions/                       # 4 TypeScript plugins
│   ├── permission-broker/            # 869 lines — Hierarchical permissions
│   ├── memory-client/                # 215 lines — Memory service client
│   ├── cost-tracker/                 # 135 lines — Token usage tracking
│   └── reasoning-engine/             # 397 lines — ReAct/Reflective patterns
│
├── scripts/
│   ├── health-check.sh               # Watchdog with --watch, --auto-restart
│   └── setup-database.sql            # PostgreSQL schema (11 tables, 30 indexes)
│
├── config/
│   ├── topology.json                 # Agent/service port map
│   └── workflows/
│       ├── research-implement-report.yaml
│       └── full-system-health.yaml
│
├── data/
│   ├── logs/                         # Service and agent log files
│   ├── pids/                         # PID files for process management
│   ├── obsidian database/            # Obsidian vault (primary)
│   │   ├── agents/                   # Per-agent knowledge
│   │   ├── research/
│   │   ├── code-patterns/
│   │   ├── decisions/
│   │   ├── daily-logs/
│   │   ├── projects/
│   │   ├── inbox/
│   │   └── templates/
│   ├── chroma/                       # ChromaDB storage (disabled)
│   └── ralph/                        # Ralph working directory
│
├── vault/                            # Secondary vault copy (Obsidian app target)
│
└── docs/
    ├── USER-GUIDE.md
    └── DEVELOPER-GUIDE.md
```

---

## Infrastructure Layer

### PostgreSQL 17

- **Port:** 5432
- **Database:** `openclaw_army`
- **User:** `openclaw` / password `openclaw`
- **Connection:** `postgresql://openclaw:openclaw@localhost:5432/openclaw_army`
- **Install:** `brew install postgresql@17` (keg-only, requires explicit PATH)
- **PATH:** `/opt/homebrew/opt/postgresql@17/bin` is prepended in deploy.sh

Used by: memory-service (Tier 2 persistent memory), orchestrator-api (workflow state), agent-registry (registration persistence).

### Redis

- **Port:** 6379
- **Database:** 0
- **Connection:** `redis://localhost:6379/0`
- **Install:** `brew install redis`

Used by: memory-service (Tier 1 sliding window), cost tracking counters, session state.

### OpenClaw Binary

- **Location:** `/usr/local/bin/openclaw`
- **Version:** v2026.2.22-2
- **Start command:** `openclaw gateway --port <port>`
- **Config per agent:** `agents/<name>/openclaw.json`
- **State directory:** `agents/<name>/.openclaw/`

Each agent is started as `openclaw gateway --port <port>` from within its directory, with environment variables set for `NVAPI_KEY`, `VAULT_PATH`, `MEMORY_SERVICE_URL`, etc.

---

## Service Layer — Complete Reference

All services are FastAPI applications running under uvicorn, bound to `127.0.0.1`.

### Memory Service (Port 18820)

**File:** `services/memory-service/main.py` (~778 lines)

**3-Tier Architecture:**
- **Tier 1 (Redis):** Sliding window of recent messages per session. TTL: 72 hours. PII redaction applied before storage.
- **Tier 2 (PostgreSQL):** Session summaries, diary entries, reflections, memory artifacts. Retention: 730 days.
- **Tier 3 (ChromaDB):** Vector-indexed semantic memory. **Currently disabled** — ChromaDB is incompatible with Python 3.14. Gracefully degrades.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — shows PII status, budget info, tier availability |
| POST | `/commit` | Store a message in session (Tier 1 + optional Tier 2) |
| GET | `/query` | Semantic search across all tiers |
| POST | `/diary` | Create a diary entry (structured task log) |
| POST | `/reflect` | Generate a reflection from recent diary entries |
| GET | `/artifacts` | Retrieve long-term memory artifacts |
| GET | `/budget` | Current token budget status (daily/monthly) |
| POST | `/budget/track` | Record token usage for an agent/model |
| GET | `/sessions/{session_id}` | Get all messages in a session |
| DELETE | `/sessions/{session_id}` | Clear a session |

**Key Implementation Details:**
- PII patterns detected: emails, SSNs (`\d{3}-\d{2}-\d{4}`), phone numbers, credit cards, IP addresses, API keys (`nvapi-`, `sk-`, `ghp_`, etc.)
- Budget tracking uses Redis for real-time counters + PostgreSQL for historical records
- Diary entries capture: agent, task description, code generated, errors, quality checks, learnings
- Reflections synthesize patterns across diary entries: failure patterns, success factors, recommendations
- Correlation ID middleware attached via `services/shared/logging_middleware.py`

---

### Orchestrator API (Port 18830)

**File:** `services/orchestrator-api/main.py` (~877 lines)

**Responsibilities:** Task decomposition, manager routing, workflow execution, progress tracking.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — shows agent roster, workflow count |
| POST | `/plan` | Decompose a task into subtasks with manager assignments |
| POST | `/execute` | Execute a plan (dispatch to managers) |
| POST | `/dispatch` | Direct dispatch to a specific manager |
| GET | `/tasks/{task_id}` | Get task status and results |
| GET | `/workflows/manifests` | List loaded YAML workflow manifests |
| POST | `/workflows/run/{name}` | Execute a named workflow |
| WS | `/events` | WebSocket for real-time task status events |

**Manager Routing Logic:**

```python
MANAGER_POOLS = {
    "coding":   {"manager": "beta-manager",  "port": 18801, "workers": ["coding-1"..."coding-4"]},
    "research": {"manager": "gamma-manager", "port": 18802, "workers": ["agentic-1"..."agentic-4"]},
    "general":  {"manager": "alpha-manager", "port": 18800, "workers": ["general-1"..."general-4"]},
}
```

Task classification keywords map to pools:
- "code", "debug", "test", "deploy", "fix", "implement" → Beta (coding)
- "research", "search", "analyze", "find", "investigate" → Gamma (research)
- Everything else → Alpha (general)

**YAML Workflow Engine:**
- Loads all `.yaml` files from `config/workflows/` on startup
- Steps execute sequentially or in parallel based on `depends_on`
- Each step targets a manager with a task template
- Variable substitution via `{variable}` in task strings

---

### Ralph — Autonomous Coding Service (Port 18840)

**File:** `services/ralph/ralph.py` (~486 lines)

**Purpose:** PRD-driven autonomous coding loop. Given a product requirements document, Ralph plans, writes code, tests it, and iterates until quality thresholds are met.

**Loop Phases:**
1. **Plan** — Parse PRD, identify required files, estimate complexity
2. **Code** — Generate implementation files
3. **Test** — Run tests against generated code
4. **Validate** — Check quality metrics (correctness, completeness, style)
5. **Reflect** — Analyze failures, adjust strategy
6. **Complete** — Package deliverable, write diary entry

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status check |
| POST | `/start-loop` | Start new autonomous coding task |
| GET | `/status/{task_id}` | Poll task progress (phase, iteration, quality) |
| POST | `/iterate` | Force next iteration cycle |

**Integration:**
- Stores diary entries to memory-service after each iteration
- Writes reflections on completion or failure
- Working directory: `data/ralph/`

---

### Knowledge Bridge — Obsidian Vault API (Port 18850)

**File:** `services/knowledge-bridge/main.py` (~447 lines)

**Purpose:** REST API for the shared Obsidian vault. All agents access the knowledge base through this service.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Vault status — path, exists, note count |
| POST | `/notes` | Create a new note in a folder |
| GET | `/notes` | Read a specific note by path |
| PUT | `/notes` | Overwrite note content |
| POST | `/notes/append` | Append content to an existing note, optionally under a section |
| GET | `/search` | Full-text search — params: `q`, `folder`, `agent`, `tags` |
| GET | `/recent` | Get most recently modified notes |
| GET | `/agents/{agent_name}/notes` | All notes by a specific agent |
| GET | `/tags` | List all unique tags across the vault |
| GET | `/stats` | Vault statistics (note count by folder, by agent) |
| POST | `/daily-log` | Create/retrieve today's daily log — param: `agent` |

**Security:**
- Path traversal prevention: all paths are resolved and checked against vault root
- Only valid folders allowed: `agents`, `research`, `code-patterns`, `decisions`, `daily-logs`, `projects`, `inbox`
- Only valid agent names allowed (all 16 agent names whitelisted)

**Frontmatter Handling:**
- Notes use YAML frontmatter for metadata (title, date, agent, tags)
- Templates in `templates/` folder are applied with `{{variable}}` substitution
- Auto-numbering for duplicate filenames (e.g., `note.md` → `note-1.md`)

---

### Agent Registry (Port 18860)

**File:** `services/agent-registry/main.py` (~240 lines)

**Purpose:** Dynamic registration, capability discovery, and liveness monitoring.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Registry status — online count |
| POST | `/register` | Register an agent with name, port, role, capabilities |
| POST | `/heartbeat` | Update agent heartbeat timestamp |
| GET | `/agents` | List all agents — optional filter: `?capability=X` |
| GET | `/agents/{name}` | Get specific agent details |
| GET | `/topology` | Full hierarchy export (JSON) |
| DELETE | `/agents/{name}` | Deregister an agent |

**Heartbeat Logic:**
- Agents are expected to heartbeat every `HEARTBEAT_TIMEOUT_SEC` (default: 60s)
- Agents missing heartbeat are marked as `offline` but not deregistered
- The `/topology` endpoint returns the full hierarchy with status

---

### Notification Service (Port 18870)

**File:** `services/notification/main.py` (~198 lines)

**Purpose:** Email notifications via Gmail SMTP.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | SMTP configuration status |
| POST | `/send` | Send email — body: `{to, subject, body}` |
| POST | `/alert` | Send alert (high-priority template) |
| GET | `/history` | Recent notification history |

**Configuration:**
- `GMAIL_USER` — Gmail address
- `GMAIL_APP_PASSWORD` — Google App Password (16 chars, requires 2FA)
- `NOTIFICATION_EMAIL` — Default recipient
- Uses `smtplib.SMTP_SSL` to `smtp.gmail.com:465`

---

## Agent Layer — Configuration & Identity

### Agent Directory Layout

Each of the 16 agents follows this structure:

```
agents/<name>/
├── openclaw.json          # OpenClaw runtime config
├── .openclaw/             # Runtime state (managed by OpenClaw)
├── .pi/                   # Private identity files
├── agents/                # Sub-agent references
├── memory/                # Local memory cache
├── workspace/             # Agent working directory
├── AGENTS.md              # How to communicate with other agents
├── HEARTBEAT.md           # Health monitoring expectations
├── IDENTITY.md            # Role definition, personality traits
├── MEMORY.md              # Memory patterns, vault integration, API usage
├── SOUL.md                # Core values, decision framework, constraints
├── TOOLS.md               # Available tools and capabilities
└── USER.md                # User interaction patterns, preferences
```

### openclaw.json Structure

```json
{
  "model": {
    "provider": "nvapi",
    "name": "nvidia/kimi-k2.5",
    "api_key_env": "NVAPI_KIMI_KEY_1"
  },
  "gateway": {
    "port": 18789,
    "host": "127.0.0.1"
  },
  "workspace": "./workspace",
  "memory_dir": "./memory",
  "extensions": [
    "../extensions/permission-broker",
    "../extensions/memory-client",
    "../extensions/cost-tracker",
    "../extensions/reasoning-engine"
  ]
}
```

### Model Assignments

| Agent | Model | NVAPI Key |
|-------|-------|-----------|
| King AI (main) | Kimi K2.5 | NVAPI_KIMI_KEY_1 |
| alpha-manager | Kimi K2.5 | NVAPI_KIMI_KEY_1 |
| beta-manager | DeepSeek R1 | NVAPI_DEEPSEEK_KEY_1 |
| gamma-manager | Kimi K2.5 | NVAPI_KIMI_KEY_2 |
| coding-1 | DeepSeek R1 | NVAPI_DEEPSEEK_KEY_2 |
| coding-2 | DeepSeek R1 | NVAPI_DEEPSEEK_KEY_3 |
| coding-3 | DeepSeek R1 | NVAPI_DEEPSEEK_KEY_4 |
| coding-4 | DeepSeek R1 | NVAPI_DEEPSEEK_KEY_5 |
| agentic-1 | GLM-5 | NVAPI_GLM5_KEY_1 |
| agentic-2 | GLM-5 | NVAPI_GLM5_KEY_2 |
| agentic-3 | Kimi K2.5 | NVAPI_KIMI_KEY_1 |
| agentic-4 | Kimi K2.5 | NVAPI_KIMI_KEY_2 |
| general-1 | Kimi K2.5 | NVAPI_KIMI_KEY_1 |
| general-2 | Kimi K2.5 | NVAPI_KIMI_KEY_2 |
| general-3 | Kimi K2.5 | NVAPI_KIMI_KEY_1 |
| general-4 | Kimi K2.5 | NVAPI_KIMI_KEY_2 |

**Rationale:**
- **DeepSeek R1** for coding — strongest at code generation and reasoning
- **GLM-5** for agentic search/analysis — designed for multi-step tool use
- **Kimi K2.5** everywhere else — strong general-purpose, good at synthesis and communication

### Agent Communication Protocol

Agents communicate via two methods:

**1. OpenClaw Protocol (sessions_send):**
```
sessions_send(target="agent:main:beta-manager", message="Review this code...")
```
- Direct agent-to-agent messaging through OpenClaw's internal protocol
- Used for delegation (King → Manager), status updates, result returns

**2. HTTP Service Calls:**
```bash
# Agent calls orchestrator to plan a task
curl -X POST http://localhost:18830/plan -d '{"task": "..."}'

# Agent stores memory
curl -X POST http://localhost:18820/commit -d '{"session_id": "...", "content": "..."}'

# Agent writes to vault
curl -X POST http://localhost:18850/notes -d '{"folder": "code-patterns", ...}'
```

---

## Extension Layer — TypeScript Plugins

Extensions are OpenClaw plugins written in TypeScript. They extend agent capabilities.

### Permission Broker (869 lines)

**File:** `extensions/permission-broker/index.ts`

**Purpose:** Enforces hierarchical least-privilege permissions.

**Capabilities controlled:**
- `exec` — Shell command execution
- `fs_write` — File system writes
- `net_request` — External network requests
- `db_write` — Database writes
- `escalate` — Permission elevation requests

**Hierarchy:**
- **Workers:** Read-only by default. Must request elevation for write/exec operations.
- **Managers:** Can approve worker elevations. Can execute in their domain.
- **King AI:** Full permissions. Approves manager escalation requests.

**Audit logging:** Every permission check (granted or denied) is logged with timestamp, agent, capability, and decision.

### Memory Client (215 lines)

**File:** `extensions/memory-client/index.ts`

**Purpose:** Transparent memory integration for agents.

**Features:**
- Auto-commits agent responses >200 characters to memory-service
- Provides `memory_commit()`, `memory_query()`, `memory_diary()` tools
- Session management with automatic TTL handling
- Connects to `http://localhost:18820`

### Cost Tracker (135 lines)

**File:** `extensions/cost-tracker/index.ts`

**Purpose:** Token usage tracking and budget enforcement.

**Features:**
- Tracks input/output tokens per model per agent
- Enforces daily and monthly budget limits
- Reports usage via `get_usage_report()` tool
- Connects to memory-service `/budget/track` endpoint

### Reasoning Engine (397 lines)

**File:** `extensions/reasoning-engine/index.ts`

**Purpose:** Advanced reasoning patterns for complex tasks.

**Patterns:**
- **ReAct:** Think → Act → Observe loop (max 10 iterations)
- **Reflective:** Execute → Reflect → Improve loop (max 5 iterations)
- **Enterprise:** Combined ReAct + Reflective with confidence thresholds

**Tools provided:**
- `react_execute(task)` — ReAct pattern
- `reflective_execute(task)` — Reflective pattern
- `enterprise_execute(task)` — Full enterprise pattern

---

## Database Schema

**File:** `scripts/setup-database.sql` (~202 lines)

### Tables

```sql
-- Agent task diary (what was attempted, what happened)
diary_entries (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64),
    session_id VARCHAR(128),
    task_description TEXT,
    code_generated TEXT,
    errors_encountered TEXT,
    quality_checks JSONB,
    learnings TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Synthesized reflections from diary patterns
reflections (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64),
    reflection_type VARCHAR(32),        -- 'failure_pattern', 'success_factor', 'recommendation'
    content TEXT,
    source_entries INTEGER[],           -- FK to diary_entries
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Long-term semantic memory artifacts
memory_artifacts (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64),
    content TEXT,
    embedding FLOAT[],                  -- Vector for semantic search (Tier 3)
    decay_score FLOAT DEFAULT 1.0,      -- Decays over time (90-day half-life)
    last_accessed TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Audit trail for all agent actions
provenance_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(64),                  -- Agent name
    action VARCHAR(128),                -- What was done
    tools_used TEXT[],                  -- Which tools were invoked
    parent_task_id VARCHAR(128),
    result_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Token usage records
cost_records (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64),
    model VARCHAR(64),
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Workflow execution state
workflow_runs (
    id SERIAL PRIMARY KEY,
    workflow_name VARCHAR(128),
    status VARCHAR(32),                 -- 'running', 'completed', 'failed'
    steps JSONB,
    input_params JSONB,
    results JSONB,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
)

-- Permission elevation requests
approval_requests (
    id SERIAL PRIMARY KEY,
    requester VARCHAR(64),
    approver VARCHAR(64),
    capability VARCHAR(64),
    reason TEXT,
    status VARCHAR(32),                 -- 'pending', 'approved', 'denied'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
)

-- Compressed session summaries
session_summaries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(128) UNIQUE,
    agent_name VARCHAR(64),
    summary TEXT,
    message_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Agent registration records
agent_registry (
    name VARCHAR(64) PRIMARY KEY,
    port INTEGER,
    role VARCHAR(32),
    capabilities TEXT[],
    status VARCHAR(32) DEFAULT 'online',
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    registered_at TIMESTAMPTZ DEFAULT NOW()
)

-- Notification history
notifications (
    id SERIAL PRIMARY KEY,
    recipient VARCHAR(256),
    subject VARCHAR(512),
    body TEXT,
    status VARCHAR(32),
    sent_at TIMESTAMPTZ DEFAULT NOW()
)

-- Token budget tracking
token_budget (
    id SERIAL PRIMARY KEY,
    period_type VARCHAR(16),            -- 'daily', 'monthly'
    period_key VARCHAR(32),             -- '2026-03-07' or '2026-03'
    total_spent FLOAT DEFAULT 0.0,
    budget_limit FLOAT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
```

### Indexes (30 total)

All tables have indexes on:
- `agent_name` — for per-agent queries
- `created_at` — for time-range queries
- `session_id` — for session lookups
- `status` — for active/pending filters
- Composite indexes where appropriate (e.g., `agent_name, created_at`)

---

## Configuration Files

### .env (Master Configuration)

| Variable | Default | Description |
|----------|---------|-------------|
| `ARMY_HOME` | `/Users/landonking/openclaw-army` | Project root |
| `OWNER_NAME` | `Landon King` | Owner identity |
| `OWNER_EMAIL` | — | Owner email |
| `KING_PORT` | `18789` | King AI port |
| `ALPHA_PORT` | `18800` | Alpha Manager port |
| `BETA_PORT` | `18801` | Beta Manager port |
| `GAMMA_PORT` | `18802` | Gamma Manager port |
| `CODING_1_PORT`...`CODING_4_PORT` | `18803-18806` | Coding worker ports |
| `AGENTIC_1_PORT`...`AGENTIC_4_PORT` | `18807-18810` | Agentic worker ports |
| `GENERAL_1_PORT`...`GENERAL_4_PORT` | `18811-18814` | General worker ports |
| `MEMORY_SERVICE_PORT` | `18820` | Memory service port |
| `ORCHESTRATOR_API_PORT` | `18830` | Orchestrator port |
| `RALPH_PORT` | `18840` | Ralph port |
| `KNOWLEDGE_BRIDGE_PORT` | `18850` | Knowledge Bridge port |
| `AGENT_REGISTRY_PORT` | `18860` | Agent Registry port |
| `NOTIFICATION_PORT` | `18870` | Notification port |
| `DATABASE_URL` | `postgresql://openclaw:openclaw@localhost:5432/openclaw_army` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SESSION_TTL_HOURS` | `72` | Redis session TTL |
| `MEMORY_RETENTION_DAYS` | `730` | PostgreSQL retention |
| `TIER3_DECAY_DAYS` | `90` | ChromaDB decay half-life |
| `DAILY_BUDGET_LIMIT` | `10.00` | Daily token budget |
| `MONTHLY_BUDGET_LIMIT` | `100.00` | Monthly token budget |
| `DAILY_BUDGET_WARN` | `8.00` | Daily budget warning threshold |
| `MONTHLY_BUDGET_WARN` | `80.00` | Monthly budget warning |
| `PII_REDACTION_ENABLED` | `true` | Enable PII scrubbing |
| `HEARTBEAT_TIMEOUT_SEC` | `60` | Agent heartbeat timeout |
| `VAULT_PATH` | `${ARMY_HOME}/data/obsidian database` | Obsidian vault location |
| `GMAIL_USER` | — | Gmail address |
| `GMAIL_APP_PASSWORD` | — | Gmail app password |
| `NOTIFICATION_EMAIL` | — | Default notification recipient |
| `NVAPI_DEEPSEEK_KEY_1`...`6` | — | 6 DeepSeek R1 API keys |
| `NVAPI_GLM5_KEY_1`...`2` | — | 2 GLM-5 API keys |
| `NVAPI_KIMI_KEY_1`...`2` | — | 2 Kimi K2.5 API keys |

### config/topology.json

Authoritative mapping of all agents and services. Used by deploy.sh and services for discovery:

```json
{
  "agents": {
    "main": {"port": 18789, "role": "meta-orchestrator", "model": "kimi-k2.5"},
    "alpha-manager": {"port": 18800, "role": "manager", "workers": ["general-1"..."general-4"]},
    ...
  },
  "services": {
    "memory-service": {"port": 18820},
    "orchestrator-api": {"port": 18830},
    ...
  }
}
```

---

## Deployment System

**File:** `deploy.sh` (~543 lines, zsh)

### Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh install` | First-time setup: check deps, create venv, install packages, init DB |
| `./deploy.sh start` | Start PostgreSQL → Redis → 6 services → 16 agents |
| `./deploy.sh stop` | Stop agents → services (keep infra running) |
| `./deploy.sh stop --full` | Stop everything including PostgreSQL and Redis |
| `./deploy.sh status` | Color-coded dashboard of all processes |
| `./deploy.sh health` | Port-level health check for all 24 components |
| `./deploy.sh restart <name>` | Restart a single agent or service |
| `./deploy.sh logs [name]` | Tail logs (all or specific) |

### Process Management

- **PID files:** `data/pids/<name>.pid` — one per service/agent
- **Log files:** `data/logs/<name>.log` — stdout/stderr per service/agent
- **Service startup:** `nohup $PYTHON -m uvicorn main:app --host 127.0.0.1 --port $PORT > logfile 2>&1 &`
- **Agent startup:** `nohup openclaw gateway --port $PORT > logfile 2>&1 &`

### Zsh-Specific Details

- Uses `${=cmd}` for word splitting (zsh doesn't split by default like bash)
- `set -euo pipefail` for strict error handling
- `.env` loaded with `set -a; source .env; set +a`

---

## Security Model

### Network Binding

All services bind to `127.0.0.1` (localhost only). No external network exposure.

### PII Redaction

Enabled by default (`PII_REDACTION_ENABLED=true`). Patterns redacted before any storage:

| Pattern | Replacement |
|---------|-------------|
| Email addresses | `[EMAIL_REDACTED]` |
| SSN (`XXX-XX-XXXX`) | `[SSN_REDACTED]` |
| Phone numbers | `[PHONE_REDACTED]` |
| Credit card numbers | `[CC_REDACTED]` |
| IPv4 addresses | `[IP_REDACTED]` |
| API keys (`nvapi-`, `sk-`, `ghp_`, `gho_`) | `[API_KEY_REDACTED]` |

### Permission Hierarchy

```
King AI        → Full permissions (exec, fs_write, net_request, db_write)
Managers       → Domain-scoped permissions (exec in their domain)
Workers        → Read-only by default, must request elevation
```

Every permission check is logged to the `approval_requests` table.

### Path Traversal Prevention

Knowledge Bridge validates all file paths:
```python
resolved = (VAULT_PATH / rel_path).resolve()
if not str(resolved).startswith(str(VAULT_PATH.resolve())):
    raise HTTPException(403, "Path traversal blocked")
```

### Credential Management

- All secrets stored in `.env` (not committed to git via `.gitignore`)
- NVAPI keys distributed across agents (each agent gets one key to prevent abuse)
- Gmail App Password used instead of account password

---

## Inter-Service Communication

### Request Flow Example: "Research Python 3.14 and implement a demo"

```
User → King AI (:18789)
  → POST /plan to Orchestrator (:18830)
    Orchestrator decomposes:
      Step 1: gamma-manager → "Research Python 3.14 features"
      Step 2: beta-manager → "Implement demo based on research" (depends_on: step1)
      Step 3: alpha-manager → "Write summary report" (depends_on: step1, step2)
    
  → POST /dispatch to gamma-manager (:18802)
    Gamma routes to agentic-1 (:18807) — search
    agentic-1:
      → GET /search to Knowledge Bridge (:18850) — check existing research
      → (web search via tools)
      → POST /notes to Knowledge Bridge (:18850) — store findings
      → POST /diary to Memory Service (:18820) — log what was done
    
  → POST /dispatch to beta-manager (:18801)
    Beta routes to coding-1 (:18803) — Python specialist
    coding-1:
      → GET /query to Memory Service (:18820) — recall similar past tasks
      → (code generation)
      → POST /commit to Memory Service (:18820) — store solution
      → POST /notes to Knowledge Bridge (:18850) — add code pattern
    
  → POST /dispatch to alpha-manager (:18800)
    Alpha routes to general-1 (:18811) — writing specialist
    → (generates report)
    
  → POST /send to Notification (:18870) — email result to user
```

### Correlation IDs

Every request gets a unique correlation ID (UUID) via the `StructuredLoggingMiddleware`:
- Injected as `X-Correlation-ID` header
- Propagated across service calls
- Logged with every log message for request tracing

---

## Obsidian Vault Integration

### Vault Location

- **Primary:** `data/obsidian database/` (configured in `.env` as `VAULT_PATH`)
- **Secondary:** `vault/` (for Obsidian app; same content)

### Folder Schema

| Folder | Purpose | Template |
|--------|---------|----------|
| `agents/` | Per-agent knowledge indexes | — |
| `research/` | Research findings, literature | `research.md` |
| `code-patterns/` | Reusable code snippets | `code-pattern.md` |
| `decisions/` | Architecture Decision Records | `decision.md` |
| `daily-logs/` | Agent activity logs | `daily-log.md` |
| `projects/` | Project tracking | `project.md` |
| `inbox/` | Quick capture / triage | — |

### Template Variables

Templates use `{{variable}}` syntax:
- `{{date}}` — ISO date
- `{{agent}}` — Agent name
- `{{title}}` — Note title
- `{{language}}` — Programming language (code-pattern)

### Example: Agent Writes a Code Pattern

```bash
curl -X POST http://localhost:18850/notes \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "code-patterns",
    "title": "FastAPI Dependency Injection",
    "content": "## Pattern\n\n```python\nfrom fastapi import Depends\n...\n```",
    "agent": "coding-1",
    "tags": ["python", "fastapi", "patterns"]
  }'
```

This creates `data/obsidian database/code-patterns/FastAPI Dependency Injection.md` with YAML frontmatter.

---

## YAML Workflow Engine

### Manifest Format

```yaml
name: workflow-name
description: "Human-readable description"
steps:
  - name: step-name
    manager: gamma-manager|beta-manager|alpha-manager
    task: "Task description with {variable} substitution"
    timeout: 300        # seconds (optional)
    depends_on: []      # list of step names (optional)
```

### Existing Workflows

**research-implement-report.yaml:**
```yaml
name: research-implement-report
description: "Research → Implement → Report pipeline"
steps:
  - name: research
    manager: gamma-manager
    task: "Research {topic} thoroughly"
    timeout: 300
  - name: implement
    manager: beta-manager
    task: "Implement solution based on research results"
    depends_on: [research]
    timeout: 600
  - name: report
    manager: alpha-manager
    task: "Write comprehensive report on findings and implementation"
    depends_on: [research, implement]
    timeout: 300
```

**full-system-health.yaml:**
```yaml
name: full-system-health
description: "Audit → Fix → Notify health pipeline"
steps:
  - name: audit
    manager: gamma-manager
    task: "Audit all system components for health issues"
    timeout: 120
  - name: fix
    manager: beta-manager
    task: "Fix any issues found in audit"
    depends_on: [audit]
    timeout: 300
  - name: notify
    manager: alpha-manager
    task: "Compile health report and send notification"
    depends_on: [audit, fix]
    timeout: 120
```

### Adding a New Workflow

1. Create `config/workflows/my-workflow.yaml`
2. Follow the manifest format above
3. Restart orchestrator: `./deploy.sh restart orchestrator-api`
4. Run: `curl -X POST http://localhost:18830/workflows/run/my-workflow -d '{"variable": "value"}'`

---

## Structured Logging & Observability

### Logging Middleware

**File:** `services/shared/logging_middleware.py` (~86 lines)

Every service includes this middleware which:
1. Generates a UUID correlation ID per request
2. Attaches it to the `X-Correlation-ID` response header
3. Sets it in a logging filter so all log messages include it
4. Logs request start/end with method, path, status, and duration

### Log Format

```
2026-03-07 14:23:01 [correlation_id=abc123] INFO memory-service: POST /commit 200 12ms
```

### Log Locations

All logs are in `data/logs/`:
```
data/logs/
├── memory-service.log
├── orchestrator-api.log
├── ralph.log
├── knowledge-bridge.log
├── agent-registry.log
├── notification.log
├── main.log              # King AI
├── alpha-manager.log
├── beta-manager.log
├── gamma-manager.log
├── coding-1.log ... coding-4.log
├── agentic-1.log ... agentic-4.log
└── general-1.log ... general-4.log
```

### Health Endpoints

Every service exposes `GET /health` returning:
```json
{
  "status": "healthy",
  "service": "<name>",
  "uptime": "<seconds>",
  "<service-specific-fields>": "..."
}
```

---

## PII Redaction System

**Location:** `services/memory-service/main.py`, function `redact_pii()`

### Patterns

```python
PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
    (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CC_REDACTED]'),
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_REDACTED]'),
    (r'\b(nvapi-|sk-|ghp_|gho_)[A-Za-z0-9_-]+\b', '[API_KEY_REDACTED]'),
]
```

### Behavior

- Applied **before** any storage (Redis Tier 1, PostgreSQL Tier 2)
- Controlled by `PII_REDACTION_ENABLED` env var
- Non-destructive to original request — redaction only affects stored copy
- Patterns are applied sequentially with `re.sub()`

---

## Token Budget Manager

**Location:** `services/memory-service/main.py`, endpoints `/budget` and `/budget/track`

### Architecture

- **Realtime counters:** Redis keys `budget:daily:{date}` and `budget:monthly:{month}` with TTLs
- **Historical records:** PostgreSQL `cost_records` and `token_budget` tables
- **Limits:** Configurable via `.env` (`DAILY_BUDGET_LIMIT`, `MONTHLY_BUDGET_LIMIT`)

### Cost Calculation

```python
# Approximate costs per model (even though free via NVAPI)
MODEL_COSTS = {
    "deepseek-r1":  {"input": 0.001, "output": 0.002},  # per 1K tokens
    "kimi-k2.5":    {"input": 0.001, "output": 0.002},
    "glm-5":        {"input": 0.0005, "output": 0.001},
}
```

### Budget Enforcement

When daily or monthly spend exceeds the warning threshold, the system:
1. Logs a warning
2. Returns a warning flag in `/budget` response
3. Agents can check before making expensive calls

When hard limit is hit, the `/budget/track` endpoint returns a `429 Too Many Requests` status.

---

## Adding New Agents

### 1. Create Agent Directory

```bash
mkdir -p agents/my-agent/{.openclaw,agents,memory,workspace,.pi}
```

### 2. Create openclaw.json

```json
{
  "model": {
    "provider": "nvapi",
    "name": "nvidia/kimi-k2.5",
    "api_key_env": "NVAPI_KIMI_KEY_1"
  },
  "gateway": {
    "port": 18815,
    "host": "127.0.0.1"
  },
  "workspace": "./workspace",
  "memory_dir": "./memory",
  "extensions": [
    "../extensions/permission-broker",
    "../extensions/memory-client",
    "../extensions/cost-tracker",
    "../extensions/reasoning-engine"
  ]
}
```

### 3. Create Identity Files

Create SOUL.md, MEMORY.md, IDENTITY.md, HEARTBEAT.md, AGENTS.md, TOOLS.md, USER.md following the patterns in existing agent directories.

### 4. Register in deploy.sh

Add to `AGENT_DEFS` array:
```bash
"my-agent:${MY_AGENT_PORT:-18815}:NVAPI_KIMI_KEY_1"
```

### 5. Register in .env

```bash
MY_AGENT_PORT=18815
```

### 6. Update topology.json

```json
"my-agent": {"port": 18815, "role": "worker", "domain": "custom", "model": "kimi-k2.5", "manager": "alpha-manager"}
```

### 7. Deploy

```bash
./deploy.sh restart
```

---

## Adding New Services

### 1. Create Service Directory

```bash
mkdir -p services/my-service
```

### 2. Create main.py

```python
import os
from fastapi import FastAPI
from services.shared.logging_middleware import StructuredLoggingMiddleware

app = FastAPI(title="My Service")
app.add_middleware(StructuredLoggingMiddleware, service_name="my-service")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "my-service"}

# Add your endpoints...
```

### 3. Create requirements.txt

```
fastapi>=0.115.0
uvicorn>=0.34.0
```

### 4. Register in deploy.sh

Add to `SERVICE_DEFS` array:
```bash
"my-service:${MY_SERVICE_PORT:-18880}:$PYTHON -m uvicorn main:app --host 127.0.0.1 --port ${MY_SERVICE_PORT:-18880}"
```

### 5. Add to .env

```bash
MY_SERVICE_PORT=18880
```

### 6. Update topology.json

```json
"my-service": {"port": 18880, "entrypoint": "main:app"}
```

### 7. Deploy

```bash
./deploy.sh restart
```

---

## Testing

### Health Check

```bash
# All 24 components
./deploy.sh health

# Continuous monitoring
./scripts/health-check.sh --watch
```

### Service Endpoint Testing

```bash
# Memory service
curl http://localhost:18820/health
curl http://localhost:18820/budget
curl -X POST http://localhost:18820/commit -H "Content-Type: application/json" \
  -d '{"session_id": "test", "agent": "king-ai", "content": "Hello world"}'

# Orchestrator
curl http://localhost:18830/health
curl http://localhost:18830/workflows/manifests
curl -X POST http://localhost:18830/plan -H "Content-Type: application/json" \
  -d '{"task": "Write a Python script"}'

# Ralph
curl http://localhost:18840/health

# Knowledge Bridge
curl http://localhost:18850/health
curl http://localhost:18850/stats
curl "http://localhost:18850/search?q=architecture"

# Agent Registry
curl http://localhost:18860/health
curl http://localhost:18860/agents
curl http://localhost:18860/topology

# Notification
curl http://localhost:18870/health
```

### PII Redaction Test

```bash
curl -X POST http://localhost:18820/commit -H "Content-Type: application/json" \
  -d '{"session_id": "test-pii", "agent": "test", "content": "Email me at test@example.com, SSN 123-45-6789"}'

# Query back — should see [EMAIL_REDACTED] and [SSN_REDACTED]
curl "http://localhost:18820/sessions/test-pii"
```

---

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **ChromaDB incompatible with Python 3.14** | Tier 3 vector memory disabled | Use Redis + PostgreSQL (Tiers 1-2). ChromaDB will work when they release a 3.14 compatible version. |
| **No web dashboard** | No visual monitoring UI | Use `./deploy.sh health` and `curl` against health endpoints |
| **No persistent health daemon** | Health must be checked manually or via `--watch` flag | Run `./scripts/health-check.sh --watch --auto-restart` in a terminal |
| **No launchd integration** | System won't auto-start after reboot | Run `./deploy.sh start` manually after reboot |
| **NVAPI rate limits** | Free tier has per-minute limits | 10 separate API keys distributed across agents to avoid hitting limits |
| **Vault space in path** | `data/obsidian database` has a space | Handled correctly in deploy.sh with quoting; works fine |
| **No automated testing suite** | Testing is manual via curl | Endpoint tests documented above |

---

## Design Decisions & ADRs

### ADR-001: Three-Tier Hierarchy

**Decision:** King AI → 3 Managers → 12 Workers (16 total)

**Rationale:**
- Mirrors proven military command structure
- Prevents King AI from being bottlenecked by too many direct reports
- Managers specialize and can make domain decisions without escalation
- Workers are cheaply replaceable (same model, different key)

### ADR-002: Free Models via NVAPI

**Decision:** Use exclusively free NVAPI models (Kimi K2.5, DeepSeek R1, GLM-5)

**Rationale:**
- Zero operating cost
- DeepSeek R1 is competitive with GPT-4 for coding
- Kimi K2.5 excels at synthesis and communication
- GLM-5 is designed for multi-step agentic tasks
- 10 separate API keys prevent rate limit issues

### ADR-003: Separate Process Per Agent

**Decision:** Each agent runs as its own `openclaw gateway` process on a unique port

**Rationale:**
- Full isolation — one agent crash doesn't affect others
- Independent scaling (can add more workers to any pool)
- Clean lifecycle management (restart one without touching others)
- Security — workers can't access other agents' memory directories

### ADR-004: Redis + PostgreSQL Over SQLite

**Decision:** Use Redis for hot data, PostgreSQL for cold data

**Rationale:**
- Redis provides sub-millisecond reads for active sessions
- PostgreSQL handles complex queries, joins, and long-term retention
- Both are battle-tested on macOS via Homebrew
- Together they cover Tiers 1 and 2 without compromise

### ADR-005: Obsidian Vault as Knowledge Base

**Decision:** Use an Obsidian-compatible markdown vault for shared knowledge

**Rationale:**
- Human-readable format (plain markdown + YAML frontmatter)
- Visual graph view via Obsidian app for exploring connections
- REST API (Knowledge Bridge) for programmatic access
- Wikilink support for cross-referencing between notes
- Templates for consistent note structure across agents

### ADR-006: PII Redaction by Default

**Decision:** All data is PII-scrubbed before storage

**Rationale:**
- Prevents accidental storage of sensitive data in memory tiers
- Applied transparently — agents don't need to think about it
- Supports compliance requirements
- Can be disabled via env var if needed for debugging

### ADR-007: YAML Workflow Manifests

**Decision:** Define reusable multi-step workflows as YAML files

**Rationale:**
- Declarative — easy to read and modify without touching Python code
- Composable — steps reference managers by name
- Dependency-aware — steps can specify prerequisites
- Hot-reloadable by restarting orchestrator

---

*For user-level documentation, see the [User Guide](USER-GUIDE.md).*
