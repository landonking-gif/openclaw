# OpenClaw Army

A 16-agent hierarchical AI system with 6 supporting services and a self-evolving orchestrator with **99 internal tools** (12,756 lines), running on free NVIDIA API models (Kimi K2.5).

## Architecture

```
                    ┌──────────────┐
                    │   King AI    │ :18789  (Kimi K2.5)
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
    │Alpha Manager│ │Beta Manager │ │Gamma Manager│
    │   :18800    │ │   :18801    │ │   :18802    │
    │  Kimi K2.5  │ │ DeepSeek R1 │ │  Kimi K2.5  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
    │ general-1-4 │ │ coding-1-4  │ │ agentic-1-4 │
    │ :18811-14   │ │ :18803-06   │ │ :18807-10   │
    │  Kimi K2.5  │ │ DeepSeek R1 │ │ GLM-5/Kimi  │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### Manager Responsibilities

| Manager | Domain | Workers | Model |
|---------|--------|---------|-------|
| **Alpha** | Writing, email, automation, communication | general-1 through general-4 | Kimi K2.5 |
| **Beta** | Coding, testing, debugging, deployment | coding-1 through coding-4 | DeepSeek R1 |
| **Gamma** | Research, analysis, fact-checking, synthesis | agentic-1 through agentic-4 | GLM-5 / Kimi K2.5 |

## Orchestrator Capabilities (99 Internal Tools)

The orchestrator (`services/orchestrator-api/main.py`, 12,756 lines) is self-evolving — it can inspect, modify, and extend its own code at runtime. Its 99 tools span:

| Category | Tools |
|----------|-------|
| **Self-Evolution** | `modify_own_code`, `register_new_tool`, `register_new_agent`, `unregister_tool`, `update_system_prompt`, `remove_prompt_section` |
| **Self-Healing** | `run_self_heal`, `run_diagnostic`, `query_failure_patterns`, `rollback_code_change`, `check_quality`, `view_modification_history` |
| **Code & Introspection** | `read_own_code`, `eval_python`, `code_analyze` (AST, lint, security scan) |
| **Shell & System** | `run_shell_command`, `install_package`, `restart_self`, `system_info`, `system_profiler`, `manage_env`, `manage_process`, `spawn_process`, `process_watchdog`, `resource_monitor` |
| **Files & Search** | `read_file`, `write_file`, `list_files`, `search_files`, `diff_files`, `file_watch`, `compress_archive`, `project_replace` |
| **Networking** | `http_fetch`, `web_scrape`, `network_probe`, `http_server`, `api_client` (REST/GraphQL), `url_tools`, `cert_check` |
| **Data** | `query_database`, `sqlite_query`, `sql_schema`, `redis_command`, `json_schema`, `data_transform`, `hash_encode`, `math_compute`, `regex_builder` |
| **Memory & Knowledge** | `memory_store`, `memory_search`, `knowledge_query`, `cache_manager`, `embeddings` (vector similarity search) |
| **Scheduling** | `schedule_task`, `cancel_scheduled_task`, `list_scheduled_tasks`, `cron_schedule`, `cron_advanced` (with dependencies & conditions) |
| **DevOps** | `git_command`, `git_ops` (GitHub API), `docker_manage`, `create_backup`, `full_backup`, `setup_launchd`, `port_manager`, `service_mesh`, `dependency_analysis`, `test_runner` |
| **Communication** | `send_notification`, `notify_send` (multi-channel), `email_parse`, `broadcast_event`, `agent_message`, `manage_sessions`, `clipboard` |
| **Media** | `screenshot`, `image_process`, `audio_process`, `video_process`, `pdf_tools`, `qr_code`, `markdown_render`, `render_template` |
| **Desktop & GUI** | `desktop_control` (pyautogui + OCR), `browser_automate` (Playwright), `accessibility` (macOS AX API) |
| **Security & Ops** | `secret_vault`, `ssh_remote`, `webhook_register`, `manage_config`, `log_query`, `metrics_collect`, `text_process`, `date_calc`, `batch_delegate`, `manage_workflow_manifest` |
| **LLM** | `llm_fallback` (multi-provider routing with failover) |

## Services

| Service | Port | Description |
|---------|------|-------------|
| **memory-service** | 18820 | 3-tier memory (Redis → PostgreSQL → ChromaDB), diary/reflect, PII redaction, token budget |
| **orchestrator-api** | 18830 | Task decomposition, workflow planning, YAML manifest engine, WebSocket events |
| **ralph** | 18840 | Autonomous PRD-driven coding loop with quality validation |
| **knowledge-bridge** | 18850 | Obsidian vault REST API for notes, search, daily logs |
| **agent-registry** | 18860 | Agent self-registration, heartbeat monitoring, capability discovery |
| **notification** | 18870 | Email notifications via Gmail SMTP |

## Quick Start

```bash
# First time setup
./deploy.sh install

# Start everything (PostgreSQL, Redis, 6 services, 16 agents)
./deploy.sh start

# Check health (wait ~35s for agents to boot)
./deploy.sh health

# View status dashboard
./deploy.sh status

# Stop everything
./deploy.sh stop

# Stop including infrastructure
./deploy.sh stop --full

# Restart a specific agent
./deploy.sh restart coding-1

# Tail logs
./deploy.sh logs          # all
./deploy.sh logs ralph    # specific service
```

## Infrastructure Requirements

- **macOS** (tested on Apple Silicon)
- **PostgreSQL 17** (Homebrew: `brew install postgresql@17`)
- **Redis** (Homebrew: `brew install redis`)
- **Python 3.14** with venv at `.venv/`
- **OpenClaw binary** at `/usr/local/bin/openclaw`

## Configuration

All configuration is in `.env`. Key sections:

| Variable | Description |
|----------|-------------|
| `NVAPI_*_KEY_*` | NVIDIA API keys (free tier) for DeepSeek R1, GLM-5, Kimi K2.5 |
| `*_PORT` | Port assignments for all agents and services |
| `POSTGRES_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | Email notification credentials |
| `PII_REDACTION_ENABLED` | Enable/disable PII scrubbing in memory (default: true) |
| `DAILY_BUDGET` / `MONTHLY_BUDGET` | Token cost guardrails |

## API Reference

### Memory Service (`:18820`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health + PII status + budget |
| GET | `/budget` | Token budget status |
| POST | `/budget/track` | Track token cost |
| POST | `/memory/tier1/add` | Add message to Redis (with PII redaction) |
| GET | `/memory/tier1/{agent}` | Get recent messages |
| GET | `/memory/tier1/{agent}/context` | Get formatted context window |
| POST | `/memory/tier2/summary` | Create session summary in PostgreSQL |
| GET | `/memory/tier2/{agent}` | Get session summaries |
| POST | `/memory/commit` | Commit artifact to long-term memory (with PII redaction) |
| POST | `/memory/query` | Semantic query across tiers |
| POST | `/memory/diary` | Record diary entry |
| POST | `/memory/reflect` | Record reflection |
| POST | `/memory/query_learnings` | Query learnings from reflections |
| POST | `/memory/compact` | Compact agent memory |
| POST | `/memory/decay` | Decay old low-importance memories |
| GET | `/memory/stats` | Overall memory statistics |
| GET | `/provenance/{artifact_id}` | Get provenance chain |

### Orchestrator API (`:18830`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health status |
| POST | `/plan` | Create a workflow plan from a task |
| POST | `/plan/{id}/dispatch` | Dispatch ready subtasks |
| PUT | `/plan/{id}/subtask/{id}` | Update subtask status |
| GET | `/plan/{id}` | Get workflow details |
| GET | `/plans` | List all workflows |
| POST | `/classify` | Preview task classification |
| GET | `/agents` | List all agents |
| GET | `/agents/{name}/status` | Check agent liveness |
| GET | `/workflows/manifests` | List YAML workflow manifests |
| POST | `/workflows/run/{name}` | Run a YAML workflow manifest |
| WS | `/ws` | Real-time workflow events |

### Ralph (`:18840`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health status |
| POST | `/cycle/start` | Start a PRD coding cycle |
| POST | `/cycle/iterate` | Progress through plan→code→test→validate→reflect→complete |
| GET | `/cycle/{id}` | Get cycle details |
| GET | `/cycles` | List all cycles |

### Knowledge Bridge (`:18850`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health status |
| POST | `/notes` | Create note |
| GET | `/notes/{path}` | Read note |
| PUT | `/notes/{path}` | Update note |
| DELETE | `/notes/{path}` | Delete note |
| GET | `/search?q=query` | Search notes |
| GET | `/recent` | Recent notes |
| POST | `/daily-log` | Add daily log entry |
| GET | `/tags` | List all tags |
| GET | `/stats` | Vault statistics |
| GET | `/agents/{name}/notes` | Agent-specific notes |

### Agent Registry (`:18860`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health + online count |
| POST | `/register` | Register an agent |
| POST | `/heartbeat` | Update heartbeat |
| DELETE | `/agents/{name}` | Deregister agent |
| GET | `/agents` | List agents (filter by role/status/capability) |
| GET | `/agents/{name}` | Get agent details |
| GET | `/discover?capability=X` | Find agents by capability |
| GET | `/topology` | Full agent hierarchy |

### Notification Service (`:18870`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health + SMTP status |
| POST | `/send` | Send email notification |
| POST | `/alert` | Quick high-priority alert |
| GET | `/history` | Notification history |

## YAML Workflow Manifests

Define reusable multi-step workflows in `config/workflows/*.yaml`:

```yaml
name: research-implement-report
description: "Research, implement, and report"
version: "1.0"
steps:
  - id: research
    name: Research & Analysis
    assigned_to: gamma-manager
    description: "Research the topic"
    depends_on: []

  - id: implement
    name: Implementation
    assigned_to: beta-manager
    description: "Implement based on research"
    depends_on: [research]

  - id: report
    name: Summary Report
    assigned_to: alpha-manager
    description: "Write summary email"
    depends_on: [research, implement]
```

Run with: `POST /workflows/run/research-implement-report`

## Security Features

### Orchestrator Hardening
All subprocess calls have timeouts. AppleScript string parameters are escaped to prevent injection. Shell commands are validated against a blocklist. SSRF protection on HTTP fetches. API key rotation with thread-safe locking. Role-parameter whitelisting in accessibility API.

### PII Redaction
All content stored through the memory service is automatically scrubbed for:
- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- SSNs → `[SSN_REDACTED]`
- Credit card numbers → `[CC_REDACTED]`
- IP addresses → `[IP_REDACTED]`
- API keys/tokens → `[API_KEY_REDACTED]`

Controlled by `PII_REDACTION_ENABLED=true` in `.env`.

### Token Budget Manager
Tracks token costs per agent with daily/monthly budgets and warnings:
- `GET /budget` — check current spend
- `POST /budget/track?agent_name=X&cost=0.01` — record cost

### Structured Logging
All services use correlation ID tracking:
- Each request gets an `X-Correlation-ID` header
- Logs include `[correlation_id]` for request tracing
- Request/response timing in milliseconds

## Database Schema

PostgreSQL tables (managed by `scripts/setup-database.sql`):

| Table | Purpose |
|-------|---------|
| `diary_entries` | Agent task attempt records |
| `reflections` | Extracted insights from diary entries |
| `memory_artifacts` | Long-term memory with content hashing |
| `provenance_logs` | Audit trail for all actions |
| `cost_records` | Per-request cost tracking |
| `workflow_runs` | Orchestrator workflow persistence |
| `approval_requests` | Permission broker decisions |
| `session_summaries` | Tier 2 session summaries |
| `agent_registry` | Agent registration snapshots |
| `notifications` | Email notification log |
| `token_budget` | Daily token cost tracking |

## Directory Structure

```
openclaw-army/
├── .env                          # All configuration
├── deploy.sh                     # Unified deployment script
├── agents/                       # 16 agent configurations
│   ├── main/                     # King AI
│   ├── alpha-manager/            # General tasks manager
│   ├── beta-manager/             # Coding manager
│   ├── gamma-manager/            # Research manager
│   ├── coding-{1-4}/             # Coding workers
│   ├── agentic-{1-4}/            # Research workers
│   └── general-{1-4}/            # General workers
├── services/
│   ├── memory-service/           # 3-tier memory + PII + budget
│   ├── orchestrator-api/         # Task planner + workflow engine
│   ├── ralph/                    # PRD coding loop
│   ├── knowledge-bridge/         # Obsidian vault API
│   ├── agent-registry/           # Agent discovery
│   ├── notification/             # Email service
│   └── shared/                   # Shared logging middleware
├── extensions/                   # VS Code/OpenClaw extensions
│   ├── permission-broker/        # Action approval system
│   ├── memory-client/            # Memory integration
│   ├── cost-tracker/             # Cost monitoring
│   └── reasoning-engine/         # LLM reasoning chains
├── config/
│   ├── topology.json             # System topology
│   └── workflows/                # YAML workflow manifests
├── scripts/
│   ├── setup-database.sql        # Schema migrations
│   └── health-check.sh           # Standalone health monitor
├── data/
│   ├── logs/                     # Service and agent logs
│   ├── pids/                     # PID files
│   ├── chroma/                   # ChromaDB storage
│   └── obsidian database/        # Obsidian vault
└── vault/                        # Knowledge vault templates
```

## Self-Evolution

The orchestrator can modify its own source code at runtime via `modify_own_code`, `register_new_tool`, and `update_system_prompt`. It can:

- **Add new tools**: Define schema, implementation, and dispatch wiring — then hot-reload
- **Fix its own bugs**: Read its code, identify issues, apply patches, validate compilation
- **Register new agents**: Spin up new worker agents or entire hierarchies
- **Roll back changes**: Every modification is versioned with automatic rollback capability
- **Install dependencies**: Use `install_package` to add any Python or system package
- **Create persistent services**: Use `setup_launchd` to create macOS launch agents

All modifications pass through `check_quality` validation before being committed.

## Troubleshooting

```bash
# Check specific service log
cat data/logs/memory-service.log

# Check agent log
cat data/logs/agent-coding-1.log

# Kill orphan processes on a port
lsof -ti :18820 | xargs kill -9

# Re-run database migrations
psql -d openclaw_army -f scripts/setup-database.sql

# Manual service start for debugging
cd services/memory-service
python -m uvicorn main:app --host 127.0.0.1 --port 18820 --reload
```
