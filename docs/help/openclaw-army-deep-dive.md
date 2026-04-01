# OpenClaw Army Deep Dive

This document explains how OpenClaw Army works end-to-end: runtime architecture, services, data flow, tool system, memory model, operations, troubleshooting, and extension points.

## 1) System Overview

OpenClaw Army is a multi-service, multi-agent AI orchestration platform built around a central Meta Orchestrator API. The orchestrator receives natural-language tasks, decides whether to answer directly or invoke tools/delegate, and coordinates supporting services.

Primary runtime components:

- `services/orchestrator-api/main.py` (port `18830`): control plane + tool execution engine.
- `services/memory-service/main.py` (port `18820`): tiered memory + semantic retrieval.
- `services/knowledge-bridge/main.py` (port `18850`): Obsidian/vault notes API.
- `services/agent-registry/main.py` (port `18860`): agent registration + heartbeat.
- `services/notification/main.py` (port `18870`): outbound notifications.
- OpenClaw gateway / channel nodes (for model + channel I/O) around port `18789`.

## 2) Request Lifecycle

1. Client sends NL message to orchestrator `/chat`.
2. Orchestrator composes LLM context, system policy, and recent session state.
3. LLM either:
   - returns final text, or
   - emits tool calls.
4. Orchestrator dispatches tool calls:
   - internal tools (direct function handlers),
   - manager delegation tools,
   - dynamic tools registered at runtime.
5. Tool results are fed back into LLM loop until completion.
6. Final answer is returned; telemetry/activity logs are persisted.
7. High-value content is optionally pushed into memory tiers.

## 3) Orchestrator Internals (`services/orchestrator-api/main.py`)

### 3.1 Tool Surfaces

The orchestrator defines a large internal tool catalog (100+). The execution loop maps tool names to handlers and runs them inside a multi-turn reasoning pipeline.

Important execution categories:

- Self-heal / diagnostics: `run_self_heal`, `run_diagnostic`.
- Code self-modification: `modify_own_code`, `rollback_code_change`.
- Local ops: `run_shell_command`, `eval_python`, file/process/network tooling.
- Knowledge/memory tools: `memory_store`, `memory_search`, `knowledge_query`.
- UI automation: `desktop_control`, `screen_share`, `accessibility`.
- External helper bridge: `github_copilot`.

### 3.2 Chat Loop Behavior

The chat loop supports multi-turn function-calling:

- parse assistant tool intents,
- execute requested tools,
- append structured results,
- continue until LLM emits a final user-facing answer.

This enables recursive and agentic workflows (plan → execute → inspect → refine).

### 3.3 Safety and Guardrails

- Basic shell destructive-command blocklist.
- Tool-level argument validation.
- Structured error return instead of silent drop.
- Activity log with JSONL durability.

## 4) Memory Service Architecture (`services/memory-service/main.py`)

Memory is tiered:

- **Tier 1 (Redis)**
  - short-window interaction memory
  - low-latency, ephemeral

- **Tier 2 (PostgreSQL summaries)**
  - rolling summaries/structured artifacts
  - auditable, queryable

- **Tier 3 (Chroma + Postgres artifacts)**
  - semantic retrieval via embeddings
  - importance score + metadata + provenance

Core APIs:

- `POST /memory/tier1/add`
- `POST /memory/commit`
- `POST /memory/query`
- `GET /memory/stats`
- `GET /health`

Operational note: semantic search requires embedding runtime availability (`sentence-transformers` + Chroma collection initialization).

## 5) Knowledge Bridge (`services/knowledge-bridge/main.py`)

Knowledge Bridge exposes structured notes API over the local vault:

- create/read/update/search notes,
- tag and folder organization,
- safe path resolution to avoid traversal.

This is the long-form knowledge substrate; memory service is the retrieval substrate for fast runtime reasoning.

## 6) Agent Registry (`services/agent-registry/main.py`)

Registry tracks:

- agent metadata,
- capability tags,
- heartbeat freshness,
- online/stale/offline status.

Used for discovery and health mapping in distributed agent deployments.

## 7) Notification Service (`services/notification/main.py`)

Notification service sends alerts and completion updates (SMTP/Gmail flow) and keeps send history for observability.

## 8) Copilot CLI Tool Integration

`github_copilot` tool in orchestrator supports direct Copilot CLI invocation via `gh copilot`.

Configured behavior:

- autopilot mode enabled,
- agent mode set (`--agent general-purpose`),
- model-aware routing and quotas,
- usage reporting action.

Current policy implemented:

- `gpt-5.3-codex`: 100 prompts/month
- `claude-sonnet-4.5`: 100 prompts/month
- `gpt-5-mini`: unlimited

Usage is persisted to `data/copilot_usage.json`.

## 9) Desktop and UI Automation

`desktop_control` supports:

- screenshot + OCR,
- mouse movement/click/drag/scroll,
- typing/hotkeys,
- window listing/focus,
- text finding.

This allows password prompt handling and interactive GUI workflows when host permissions are granted (Accessibility / Screen Recording on macOS).

## 10) Data and Persistence Layout

Common runtime data paths:

- `data/logs/*.jsonl` (activity/failures/quality/memory monitors)
- `data/copilot_usage.json` (Copilot quota accounting)
- service-local data directories (e.g., Chroma store under memory service)

## 11) Health and Diagnostics

Primary checks:

- Orchestrator: `GET /health` on `18830`
- Memory service: `GET /health` on `18820`
- Orchestrator diagnostic: `GET /diagnostic`

Diagnostic behavior now includes fallback from `/health` to `/` when some nodes expose root but not health endpoints.

## 12) Common Failure Modes and Fixes

### 12.1 Python subprocess `Bad file descriptor`

Symptom: `init_sys_streams` / `OSError [Errno 9]` in subprocess-based Python runs.
Fix applied: subprocess handlers now set `stdin=subprocess.DEVNULL` in shell/eval code paths.

### 12.2 Memory search returning 404

Symptom: orchestrator attempted old memory endpoint.
Fix applied: orchestrator uses `POST /memory/query` with JSON payload.

### 12.3 Screenshot region schema mismatch

Symptom: `'w'` key error when region uses `width/height`.
Fix applied: accepts both `w/h` and `width/height`.

## 13) Deployment Modes

- Local host-native services (venv + Python processes)
- Containerized multi-service stack (see `/docker-compose.army.yml`)

## 14) Security and Secrets

Do not hardcode secrets in code/images. Inject via env:

- LLM API keys
- DB credentials
- SMTP credentials

Principles:

- least privilege,
- explicit observability,
- audited changes,
- bounded automation quotas.

## 15) Extending the System

To add capability:

1. Add/extend orchestrator tool schema.
2. Add handler function.
3. Wire into dispatch switch.
4. Add health and error telemetry.
5. Add integration tests and smoke runbook entries.

## 16) Suggested Validation Matrix

- Health checks for all services.
- Tool smoke tests: shell, eval, memory, desktop.
- Copilot tool tests: usage + capped/unlimited model paths.
- Memory retrieval test with synthetic unique tokens.
- End-to-end NL prompts through orchestrator API only.
