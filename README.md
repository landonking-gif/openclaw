# OpenClaw Army

A 16-agent hierarchical AI system with 6 supporting services and a self-evolving orchestrator with **101 internal tools** (13,328 lines), running on free NVIDIA API models (Kimi K2.5).

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

The orchestrator (`services/orchestrator-api/main.py`, 13,328 lines) is self-evolving — it can inspect, modify, and extend its own code at runtime. Its 101 tools span:

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
| **Desktop & Glasses** | `screen_share` (screen capture + annotation), `visionclaw` (Meta Ray-Ban smart glasses via VisionClaw iOS app) |

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
| POST | `/v1/chat/completions` | OpenAI-compatible chat (VisionClaw / smart glasses) |
| GET | `/v1/chat/completions` | VisionClaw health check |
| GET | `/v1/models` | OpenAI-compatible model listing |
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

---

## Claw Code README Section

# Rewriting Project Claw Code

<p align="center">
  <strong>⭐ The fastest repo in history to surpass 50K stars, reaching the milestone in just 2 hours after publication ⭐</strong>
</p>

<p align="center">
  <a href="https://star-history.com/#instructkr/claw-code&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=instructkr/claw-code&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=instructkr/claw-code&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=instructkr/claw-code&type=Date" width="600" />
    </picture>
  </a>
</p>

<p align="center">
  <img src="assets/clawd-hero.jpeg" alt="Claw" width="300" />
</p>

<p align="center">
  <strong>Better Harness Tools, not merely storing the archive of leaked Claw Code</strong>
</p>

<p align="center">
  <a href="https://github.com/sponsors/instructkr"><img src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github&style=for-the-badge" alt="Sponsor on GitHub" /></a>
</p>

> [!IMPORTANT]
> **Rust port is now in progress** on the [`dev/rust`](https://github.com/instructkr/claw-code/tree/dev/rust) branch and is expected to be merged into main today. The Rust implementation aims to deliver a faster, memory-safe harness runtime. Stay tuned — this will be the definitive version of the project.

> If you find this work useful, consider [sponsoring @instructkr on GitHub](https://github.com/sponsors/instructkr) to support continued open-source harness engineering research.

---

## Rust Port

The Rust workspace under `rust/` is the current systems-language port of the project.

It currently includes:

- `crates/api-client` — API client with provider abstraction, OAuth, and streaming support
- `crates/runtime` — session state, compaction, MCP orchestration, prompt construction
- `crates/tools` — tool manifest definitions and execution framework
- `crates/commands` — slash commands, skills discovery, and config inspection
- `crates/plugins` — plugin model, hook pipeline, and bundled plugins
- `crates/compat-harness` — compatibility layer for upstream editor integration
- `crates/claw-cli` — interactive REPL, markdown rendering, and project bootstrap/init flows

Run the Rust build:

```bash
cd rust
cargo build --release
```

## Backstory

At 4 AM on March 31, 2026, I woke up to my phone blowing up with notifications. The Claw Code source had been exposed, and the entire dev community was in a frenzy. My girlfriend in Korea was genuinely worried I might face legal action from the original authors just for having the code on my machine — so I did what any engineer would do under pressure: I sat down, ported the core features to Python from scratch, and pushed it before the sun came up.

The whole thing was orchestrated end-to-end using [oh-my-codex (OmX)](https://github.com/Yeachan-Heo/oh-my-codex) by [@bellman_ych](https://x.com/bellman_ych) — a workflow layer built on top of OpenAI's Codex ([@OpenAIDevs](https://x.com/OpenAIDevs)). I used `$team` mode for parallel code review and `$ralph` mode for persistent execution loops with architect-level verification. The entire porting session — from reading the original harness structure to producing a working Python tree with tests — was driven through OmX orchestration.

The result is a clean-room Python rewrite that captures the architectural patterns of Claw Code's agent harness without copying any proprietary source. I'm now actively collaborating with [@bellman_ych](https://x.com/bellman_ych) — the creator of OmX himself — to push this further. The basic Python foundation is already in place and functional, but we're just getting started. **Stay tuned — a much more capable version is on the way.**

The Rust port was built separately using [oh-my-opencode (OMO)](https://github.com/code-yeongyu/oh-my-opencode) by [@q_yeon_gyu_kim](https://x.com/q_yeon_gyu_kim) ([@code-yeongyu](https://github.com/code-yeongyu)), which orchestrates [opencode](https://opencode.ai) agents. **The scaffolding and architecture direction were established with [oh-my-codex (OmX)](https://github.com/Yeachan-Heo/oh-my-codex),** and the **Sisyphus** agent then handled implementation work across the API client, runtime engine, CLI, plugin system, MCP integration, and the cleanroom pass in `ultrawork` mode.

https://github.com/instructkr/claw-code

![Tweet screenshot](assets/tweet-screenshot.png)

## The Creators Featured in Wall Street Journal For Avid Claw Code Fans

I've been deeply interested in **harness engineering** — studying how agent systems wire tools, orchestrate tasks, and manage runtime context. This isn't a sudden thing. The Wall Street Journal featured my work earlier this month, documenting how I've been one of the most active power users exploring these systems:

> AI startup worker Sigrid Jin, who attended the Seoul dinner, single-handedly used 25 billion of Claw Code tokens last year. At the time, usage limits were looser, allowing early enthusiasts to reach tens of billions of tokens at a very low cost.
>
> Despite his countless hours with Claw Code, Jin isn't faithful to any one AI lab. The tools available have different strengths and weaknesses, he said. Codex is better at reasoning, while Claw Code generates cleaner, more shareable code.
>
> Jin flew to San Francisco in February for Claw Code's first birthday party, where attendees waited in line to compare notes with Cherny. The crowd included a practicing cardiologist from Belgium who had built an app to help patients navigate care, and a California lawyer who made a tool for automating building permit approvals using Claw Code.
>
> "It was basically like a sharing party," Jin said. "There were lawyers, there were doctors, there were dentists. They did not have software engineering backgrounds."
>
> — *The Wall Street Journal*, March 21, 2026, [*"The Trillion Dollar Race to Automate Our Entire Lives"*](https://lnkd.in/gs9td3qd)

![WSJ Feature](assets/wsj-feature.png)

---

## Porting Status

The main source tree is now Python-first.

- `src/` contains the active Python porting workspace
- `tests/` verifies the current Python workspace
- the exposed snapshot is no longer part of the tracked repository state

The current Python workspace is not yet a complete one-to-one replacement for the original system, but the primary implementation surface is now Python.

## Why this rewrite exists

I originally studied the exposed codebase to understand its harness, tool wiring, and agent workflow. After spending more time with the legal and ethical questions—and after reading the essay linked below—I did not want the exposed snapshot itself to remain the main tracked source tree.

This repository now focuses on Python porting work instead.

## Repository Layout

```text
.
├── src/                                # Python porting workspace
│   ├── __init__.py
│   ├── commands.py
│   ├── main.py
│   ├── models.py
│   ├── port_manifest.py
│   ├── query_engine.py
│   ├── task.py
│   └── tools.py
├── rust/                               # Rust port (claw CLI)
│   ├── crates/api/                     # API client + streaming
│   ├── crates/runtime/                 # Session, tools, MCP, config
│   ├── crates/claw-cli/               # Interactive CLI binary
│   ├── crates/plugins/                 # Plugin system
│   ├── crates/commands/                # Slash commands
│   ├── crates/server/                  # HTTP/SSE server (axum)
│   ├── crates/lsp/                    # LSP client integration
│   └── crates/tools/                   # Tool specs
├── tests/                              # Python verification
├── assets/omx/                         # OmX workflow screenshots
├── 2026-03-09-is-legal-the-same-as-legitimate-ai-reimplementation-and-the-erosion-of-copyleft.md
└── README.md
```

## Python Workspace Overview

The new Python `src/` tree currently provides:

- **`port_manifest.py`** — summarizes the current Python workspace structure
- **`models.py`** — dataclasses for subsystems, modules, and backlog state
- **`commands.py`** — Python-side command port metadata
- **`tools.py`** — Python-side tool port metadata
- **`query_engine.py`** — renders a Python porting summary from the active workspace
- **`main.py`** — a CLI entrypoint for manifest and summary output

## Quickstart

Render the Python porting summary:

```bash
python3 -m src.main summary
```

Print the current Python workspace manifest:

```bash
python3 -m src.main manifest
```

List the current Python modules:

```bash
python3 -m src.main subsystems --limit 16
```

Run verification:

```bash
python3 -m unittest discover -s tests -v
```

Run the parity audit against the local ignored archive (when present):

```bash
python3 -m src.main parity-audit
```

Inspect mirrored command/tool inventories:

```bash
python3 -m src.main commands --limit 10
python3 -m src.main tools --limit 10
```

## Current Parity Checkpoint

The port now mirrors the archived root-entry file surface, top-level subsystem names, and command/tool inventories much more closely than before. However, it is **not yet** a full runtime-equivalent replacement for the original TypeScript system; the Python tree still contains fewer executable runtime slices than the archived source.

## Built with `oh-my-codex` and `oh-my-opencode`

This repository's porting, cleanroom hardening, and verification workflow was AI-assisted with Yeachan Heo's tooling stack, with **oh-my-codex (OmX)** as the primary scaffolding and orchestration layer.

- [**oh-my-codex (OmX)**](https://github.com/Yeachan-Heo/oh-my-codex) — main branch credit: primary scaffolding, orchestration, and core porting workflow
- [**oh-my-opencode (OmO)**](https://github.com/instructkr/oh-my-opencode) — implementation acceleration, cleanup passes, and verification support

Key workflow patterns used during the port:

- **`$team` mode:** coordinated parallel review and architectural feedback
- **`$ralph` mode:** persistent execution, verification, and completion discipline
- **Cleanroom passes:** naming/branding cleanup, QA, and release validation across the Rust workspace
- **Manual and live validation:** build, test, manual QA, and real API-path verification before publish

### OmX workflow screenshots

![OmX workflow screenshot 1](assets/omx/omx-readme-review-1.png)

*Ralph/team orchestration view while the README and essay context were being reviewed in terminal panes.*

![OmX workflow screenshot 2](assets/omx/omx-readme-review-2.png)

*Split-pane review and verification flow during the final README wording pass.*

## Community

<p align="center">
  <a href="https://instruct.kr/"><img src="assets/instructkr.png" alt="instructkr" width="400" /></a>
</p>

Join the [**instructkr Discord**](https://instruct.kr/) — the best Korean language model community. Come chat about LLMs, harness engineering, agent workflows, and everything in between.

[![Discord](https://img.shields.io/badge/Join%20Discord-instruct.kr-5865F2?logo=discord&style=for-the-badge)](https://instruct.kr/)

## Star History

See the chart at the top of this README.

## Ownership / Affiliation Disclaimer

- This repository does **not** claim ownership of the original Claw Code source material.
- This repository is **not affiliated with, endorsed by, or maintained by the original authors**.
