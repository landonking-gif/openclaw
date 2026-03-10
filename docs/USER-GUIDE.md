# OpenClaw Army — User Guide

> **Version:** 1.0 | **Last Updated:** March 7, 2026  
> **Owner:** Landon King | **System:** macOS (Apple Silicon)

---

## Table of Contents

1. [What Is OpenClaw Army?](#what-is-openclaw-army)
2. [Quick Start](#quick-start)
3. [System Requirements](#system-requirements)
4. [First-Time Setup](#first-time-setup)
5. [Daily Operations](#daily-operations)
6. [How the Agent Hierarchy Works](#how-the-agent-hierarchy-works)
7. [Talking to Your Agents](#talking-to-your-agents)
8. [The Knowledge Vault (Obsidian)](#the-knowledge-vault-obsidian)
9. [Notifications](#notifications)
10. [Budget & Cost Management](#budget--cost-management)
11. [Monitoring Health](#monitoring-health)
12. [Workflows](#workflows)
13. [VisionClaw (Smart Glasses)](#visionclaw-smart-glasses)
14. [Troubleshooting](#troubleshooting)
15. [FAQ](#faq)

---

## What Is OpenClaw Army?

OpenClaw Army is a **16-agent AI system** running locally on your Mac. It operates as a military-style hierarchy:

```
                    ┌──────────┐
                    │  King AI │  (You talk to this one)
                    │  :18789  │
                    └────┬─────┘
             ┌───────────┼───────────┐
             ▼           ▼           ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  Alpha   │ │   Beta   │ │  Gamma   │
       │ Manager  │ │ Manager  │ │ Manager  │
       │  :18800  │ │  :18801  │ │  :18802  │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │             │             │
   ┌──┬──┬──┤    ┌──┬──┬──┤    ┌──┬──┬──┤
   ▼  ▼  ▼  ▼    ▼  ▼  ▼  ▼    ▼  ▼  ▼  ▼
  g1 g2 g3 g4   c1 c2 c3 c4   a1 a2 a3 a4
```

- **King AI** receives your requests, decides which manager handles them.
- **Alpha Manager** handles writing, communication, summarization, and automation.
- **Beta Manager** handles all coding tasks — Python, JavaScript, Bash, fullstack.
- **Gamma Manager** handles research, analysis, synthesis, and fact-checking.
- Each manager delegates to **4 specialized workers**.

All models used are **free** via NVIDIA API (NVAPI):
- **Kimi K2.5** — King AI, Alpha, Gamma, and general/agentic workers
- **DeepSeek R1** — Beta and all coding workers
- **GLM-5** — Agentic search and analysis workers

---

## Quick Start

```bash
# First time only
cd ~/openclaw-army
./deploy.sh install

# Every time you want to use the system
./deploy.sh start

# Check everything is running
./deploy.sh health

# When you're done
./deploy.sh stop
```

That's it. After `./deploy.sh start`, all 16 agents and 6 services are running.

---

## System Requirements

| Requirement      | Minimum                          |
|------------------|----------------------------------|
| macOS            | Ventura 13+ (Apple Silicon)      |
| RAM              | 16 GB recommended                |
| Disk             | ~2 GB for project + databases    |
| PostgreSQL       | 17 (installed via Homebrew)      |
| Redis            | Latest (installed via Homebrew)  |
| Python           | 3.14 (with venv)                 |
| OpenClaw binary  | v2026.2.22-2 at `/usr/local/bin/openclaw` |
| NVAPI keys       | 10 keys in `.env` (6 DeepSeek, 2 GLM-5, 2 Kimi) |

---

## First-Time Setup

### 1. Install Dependencies

```bash
./deploy.sh install
```

This will:
- Verify PostgreSQL 17 and Redis are installed via Homebrew
- Create a Python 3.14 virtual environment (`.venv/`)
- Install all Python packages (FastAPI, uvicorn, redis, psycopg2, etc.)
- Set up the PostgreSQL database and tables
- Validate your `.env` configuration

### 2. Configure Your .env

The `.env` file at the project root contains all configuration. Key sections:

**Identity:**
```bash
OWNER_NAME="Landon King"
OWNER_EMAIL="your-email@gmail.com"
```

**NVAPI Keys** (get free keys from build.nvidia.com):
```bash
NVAPI_DEEPSEEK_KEY_1="nvapi-..."
NVAPI_KIMI_KEY_1="nvapi-..."
NVAPI_GLM5_KEY_1="nvapi-..."
# ... (10 keys total)
```

**Budget Limits:**
```bash
DAILY_BUDGET_LIMIT=10.00      # Max $10/day
MONTHLY_BUDGET_LIMIT=100.00   # Max $100/month
```

**Email Notifications:**
```bash
GMAIL_USER="your-email@gmail.com"
GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"   # Google App Password (not your login password)
```

### 3. Start the System

```bash
./deploy.sh start
```

Watch for the health check at the end — you want **24/24 healthy**.

---

## Daily Operations

### Starting Up

```bash
./deploy.sh start
```

This starts, in order:
1. **PostgreSQL** and **Redis** (infrastructure)
2. **6 services** — memory, orchestrator, ralph, knowledge-bridge, agent-registry, notification
3. **16 agents** — King AI, 3 managers, 12 workers

### Checking Status

```bash
# Quick status dashboard
./deploy.sh status

# Full health check with port verification
./deploy.sh health
```

### Viewing Logs

```bash
# All service logs (last 50 lines each)
./deploy.sh logs

# Specific service
./deploy.sh logs memory-service
./deploy.sh logs ralph
./deploy.sh logs king-ai
```

Logs are stored in `data/logs/`.

### Restarting a Single Component

```bash
# Restart just one agent or service
./deploy.sh restart beta-manager
./deploy.sh restart memory-service
```

### Shutting Down

```bash
# Stop agents and services (keeps PostgreSQL and Redis running)
./deploy.sh stop

# Full shutdown including databases
./deploy.sh stop --full
```

---

## How the Agent Hierarchy Works

### Delegation Flow

1. **You** send a task to **King AI** (port 18789)
2. King AI analyzes the task and routes it:
   - Writing/communication → **Alpha Manager**
   - Coding/debugging → **Beta Manager**
   - Research/analysis → **Gamma Manager**
3. The manager decomposes the task and assigns it to the best available worker
4. Workers execute and return results up the chain
5. King AI synthesizes and delivers the final response to you

### Agent Specializations

| Agent | Port | What It Does |
|-------|------|-------------|
| **King AI** | 18789 | Top-level orchestrator — routes tasks, manages priorities |
| **Alpha Manager** | 18800 | Communication coordinator — writing, summarizing, automating |
| **Beta Manager** | 18801 | Code lead — planning, reviewing, coordinating coding tasks |
| **Gamma Manager** | 18802 | Research lead — directing searches, analysis, fact-checking |
| general-1 | 18811 | Content writing, email drafting |
| general-2 | 18812 | Text summarization and synthesis |
| general-3 | 18813 | Quality assurance and review |
| general-4 | 18814 | Workflow automation, scheduling |
| coding-1 | 18803 | Python backend development |
| coding-2 | 18804 | JavaScript / Node.js |
| coding-3 | 18805 | Shell scripting, system automation |
| coding-4 | 18806 | Full-stack integration |
| agentic-1 | 18807 | Internet and knowledge base search |
| agentic-2 | 18808 | Data analysis, pattern recognition |
| agentic-3 | 18809 | Research synthesis |
| agentic-4 | 18810 | Fact-checking, verification |

### Permission System

Workers operate under **least-privilege**. They cannot:
- Execute shell commands without manager approval
- Access files outside their assigned workspace
- Make network requests without permission-broker clearance

If a worker needs elevated access, it requests permission from its manager, who may escalate to King AI. This is handled by the **permission-broker extension**.

---

## Talking to Your Agents

### Via OpenClaw (Primary Method)

Each agent runs as an OpenClaw gateway. You interact with King AI through the OpenClaw interface at port 18789. King AI will delegate to the appropriate manager and workers automatically.

### Via HTTP API (Direct Access)

You can also talk to services directly:

**Ask the orchestrator to plan a task:**
```bash
curl -X POST http://localhost:18830/plan \
  -H "Content-Type: application/json" \
  -d '{"task": "Research the latest Python 3.14 features and write a summary"}'
```

**Start an autonomous coding task with Ralph:**
```bash
curl -X POST http://localhost:18840/start-loop \
  -H "Content-Type: application/json" \
  -d '{"prd": "Build a FastAPI endpoint that returns system health metrics"}'
```

**Search your knowledge vault:**
```bash
curl "http://localhost:18850/search?q=python+async"
```

**Check token budget:**
```bash
curl http://localhost:18820/budget
```

---

## The Knowledge Vault (Obsidian)

The system includes an **Obsidian vault** at `data/obsidian database/` that serves as shared long-term knowledge across all agents.

### Vault Structure

```
data/obsidian database/
├── agents/          # Per-agent knowledge (indexes, learnings)
├── research/        # Research findings from Gamma team
├── code-patterns/   # Reusable code snippets and patterns
├── decisions/       # Architecture Decision Records (ADRs)
├── daily-logs/      # Agent activity logs
├── projects/        # Project tracking notes
├── inbox/           # Quick capture area
└── templates/       # Note templates (daily-log, code-pattern, decision, project, research)
```

### Using the Vault

**Open in Obsidian:** Open the `data/obsidian database/` folder as an Obsidian vault for a visual graph-based view of all knowledge.

**Via REST API (Knowledge Bridge, port 18850):**

```bash
# Create a note
curl -X POST http://localhost:18850/notes \
  -H "Content-Type: application/json" \
  -d '{"folder": "research", "title": "My Finding", "content": "Details here", "agent": "king-ai"}'

# Search notes
curl "http://localhost:18850/search?q=python&folder=code-patterns"

# Get vault statistics
curl http://localhost:18850/stats

# Create today's daily log for an agent
curl -X POST "http://localhost:18850/daily-log?agent=king-ai"
```

### Templates

When creating notes via the API, templates are automatically applied with variable substitution:
- `{{date}}` → current date
- `{{agent}}` → agent name
- `{{title}}` → note title

---

## Notifications

The notification service (port 18870) sends email alerts via Gmail SMTP.

### Setup

In your `.env`, configure:
```bash
GMAIL_USER="your-email@gmail.com"
GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
NOTIFICATION_EMAIL="your-email@gmail.com"
```

To get a Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords.

### Sending Notifications

```bash
curl -X POST http://localhost:18870/send \
  -H "Content-Type: application/json" \
  -d '{"to": "you@gmail.com", "subject": "Task Complete", "body": "Your research task finished."}'
```

Agents can trigger notifications automatically for completed tasks, errors, or budget warnings.

---

## Budget & Cost Management

Even though NVAPI models are free, the system tracks token usage to enforce budgets and monitor consumption.

### Checking Your Budget

```bash
curl http://localhost:18820/budget
```

Returns:
```json
{
  "daily_limit": 10.0,
  "monthly_limit": 100.0,
  "daily_spent": 0.0,
  "monthly_spent": 0.0,
  "daily_remaining": 10.0,
  "monthly_remaining": 100.0
}
```

### Tracking a Request

```bash
curl -X POST http://localhost:18820/budget/track \
  -H "Content-Type: application/json" \
  -d '{"agent": "coding-1", "model": "deepseek-r1", "input_tokens": 1500, "output_tokens": 500}'
```

### Adjusting Limits

Edit `.env`:
```bash
DAILY_BUDGET_LIMIT=20.00
MONTHLY_BUDGET_LIMIT=200.00
DAILY_BUDGET_WARN=16.00
MONTHLY_BUDGET_WARN=160.00
```

Then restart the memory service: `./deploy.sh restart memory-service`

---

## Monitoring Health

### Quick Check

```bash
./deploy.sh health
```

Expected output for a healthy system:
```
══ OpenClaw Army Health Check ══

  PostgreSQL...                  HEALTHY
  Redis...                       HEALTHY
  memory-service (18820)...      HEALTHY
  orchestrator-api (18830)...    HEALTHY
  ralph (18840)...               HEALTHY
  knowledge-bridge (18850)...    HEALTHY
  agent-registry (18860)...      HEALTHY
  notification (18870)...        HEALTHY
  main (18789)...                HEALTHY
  alpha-manager (18800)...       HEALTHY
  ... (12 more agents)
  
Result: 24/24 healthy
```

### Continuous Monitoring

```bash
# Watch mode — checks every 30 seconds
./scripts/health-check.sh --watch

# Watch with auto-restart of failed components
./scripts/health-check.sh --watch --auto-restart
```

### Individual Service Health

```bash
curl http://localhost:18820/health   # Memory service
curl http://localhost:18830/health   # Orchestrator
curl http://localhost:18840/health   # Ralph
curl http://localhost:18850/health   # Knowledge bridge
curl http://localhost:18860/health   # Agent registry
curl http://localhost:18870/health   # Notification
```

### Agent Registry

The agent registry tracks all registered agents and their capabilities:

```bash
# List all registered agents
curl http://localhost:18860/agents

# Find agents with a specific capability
curl "http://localhost:18860/agents?capability=coding"

# View full topology
curl http://localhost:18860/topology
```

---

## Workflows

Predefined YAML workflows automate multi-step processes across the agent hierarchy.

### Available Workflows

**research-implement-report** — Full lifecycle:
1. Gamma Manager researches the topic
2. Beta Manager implements based on findings
3. Alpha Manager writes the report

**full-system-health** — System audit:
1. Check all agent health
2. Fix any issues found
3. Send notification with results

### Running a Workflow

```bash
# List available workflows
curl http://localhost:18830/workflows/manifests

# Run a workflow
curl -X POST http://localhost:18830/workflows/run/research-implement-report \
  -H "Content-Type: application/json" \
  -d '{"topic": "async Python best practices"}'
```

### Creating Custom Workflows

Create a YAML file in `config/workflows/`:

```yaml
name: my-custom-workflow
description: "What this workflow does"
steps:
  - name: step-1
    manager: gamma-manager
    task: "Research the topic: {topic}"
    timeout: 300
  - name: step-2
    manager: beta-manager
    task: "Implement based on step-1 results"
    depends_on: [step-1]
    timeout: 600
```

The orchestrator automatically loads all `.yaml` files from `config/workflows/` on startup.

---

## VisionClaw (Smart Glasses)

OpenClaw Army integrates with **VisionClaw**, an iOS app for Meta Ray-Ban smart glasses. When connected, your glasses become a hands-free interface to all 101 orchestrator tools — ask questions, run commands, take notes, and control your system by voice.

### How It Works

```
Meta Ray-Ban Glasses
        │ (Bluetooth audio + camera)
        ▼
  VisionClaw iOS App
        │ (Gemini Live API — real-time audio + video)
        ▼
  Gemini "execute" tool call
        │
        ▼
  OpenClaw Army Orchestrator (:18830)
        │ /v1/chat/completions (OpenAI-compatible)
        ▼
  101 Tools Available
```

The orchestrator exposes an **OpenAI-compatible** `/v1/chat/completions` endpoint. VisionClaw sends requests here using Bearer token authentication and an `x-openclaw-session-key` header for session continuity.

### Setup

1. **Ensure the orchestrator is running** on port 18830
2. **Configure VisionClaw's `Secrets.swift`** to point at the orchestrator:
   ```swift
   static let openClawHost = "http://YOUR-MAC-HOSTNAME.local"
   static let openClawPort = 18830
   static let openClawGatewayToken = "YOUR_OPENCLAW_TOKEN"
   ```
3. **Set gateway bind to LAN** so your iPhone can reach the Mac:
   - Edit `~/.openclaw/openclaw.json` → set `"bind": "lan"`
   - Restart the OpenClaw gateway
4. **Build and run VisionClaw** in Xcode on your iPhone
5. **Pair your Meta Ray-Ban glasses** via the Meta View app

### Using the VisionClaw Tool

The orchestrator includes a `visionclaw` tool for managing glass connections:

| Action | Description |
|--------|-------------|
| `status` | Show active glass sessions, gateway config, LAN URL |
| `sessions` | List all VisionClaw sessions with message counts |
| `config` | Show gateway configuration and recommended settings |
| `configure` | Update gateway bind mode (lan/loopback) |
| `send` | Push a proactive message to a glass session |
| `history` | Get conversation history for a glass session |

Example: *"Check if my glasses are connected"* → orchestrator uses `visionclaw(action: "status")`

### Verifying the Connection

```bash
# Health check — should return {"status": "ok", "tools": 101}
curl http://localhost:18830/v1/chat/completions

# Test a request (simulating VisionClaw)
curl -X POST http://localhost:18830/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "x-openclaw-session-key: test-session" \
  -d '{"model":"openclaw","messages":[{"role":"user","content":"Hello from glasses"}]}'
```

---

## Troubleshooting

### "X/24 healthy" — Some Components Down

```bash
# Check which are down
./deploy.sh health

# Check logs for the failed component
./deploy.sh logs <component-name>

# Restart just that component
./deploy.sh restart <component-name>
```

### PostgreSQL Won't Start

```bash
# Check if it's already running
pg_isready -p 5432

# Start manually
brew services start postgresql@17

# Check logs
tail -20 /opt/homebrew/var/log/postgresql@17.log
```

### Redis Won't Start

```bash
redis-cli ping    # Should return PONG
brew services start redis
```

### Port Already in Use

```bash
# Find what's using a port
lsof -i :18789

# Kill a stuck process
kill $(lsof -t -i :18789)
```

### Agent Starts But Isn't Responding

```bash
# Check agent log
cat data/logs/main.log | tail -50

# Verify OpenClaw binary
/usr/local/bin/openclaw --version
```

### "ChromaDB Disabled" Warning

This is expected. ChromaDB (Tier 3 vector memory) is incompatible with Python 3.14. The system functions fully with Redis (Tier 1) and PostgreSQL (Tier 2) memory.

### Budget Exceeded

```bash
# Check current spend
curl http://localhost:18820/budget

# Reset is automatic — daily budget resets at midnight, monthly at month start
```

---

## FAQ

**Q: How much does this cost to run?**  
A: $0. All models (Kimi K2.5, DeepSeek R1, GLM-5) are free via NVIDIA API. You only pay for electricity and the Mac itself.

**Q: Can I add more agents?**  
A: Yes. Create a new agent directory under `agents/`, add it to `AGENT_DEFS` in `deploy.sh`, allocate a port, and create the required markdown files (SOUL.md, MEMORY.md, etc.).

**Q: Can I change which model an agent uses?**  
A: Edit the agent's `openclaw.json` and update the NVAPI key mapping in `deploy.sh`.

**Q: Where are logs stored?**  
A: `data/logs/` — one log file per service and agent.

**Q: How do I back up the system?**  
A: Back up the entire `openclaw-army/` directory. The PostgreSQL database can be backed up with `pg_dump openclaw_army > backup.sql`.

**Q: Can agents communicate with each other?**  
A: Yes, via two methods: (1) the `sessions_send()` OpenClaw protocol for direct agent-to-agent messaging, and (2) HTTP requests to service APIs (orchestrator, memory, knowledge-bridge).

**Q: Is my data private?**  
A: Yes. Everything runs locally. The only external calls are to NVIDIA's API for model inference. PII redaction is enabled by default — emails, SSNs, phone numbers, credit cards, and API keys are automatically scrubbed before storage.

**Q: What happens if the Mac sleeps or reboots?**  
A: All agents and services stop. Run `./deploy.sh start` after waking/rebooting.

**Q: Can I use this remotely?**  
A: Services bind to `127.0.0.1` (localhost only) by default. For remote access, you'd need to change the bind address and set up proper authentication — not recommended without a VPN.

---

*For developer-level technical documentation, see the [Developer Guide](DEVELOPER-GUIDE.md).*
