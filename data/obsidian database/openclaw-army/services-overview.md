# Services Overview

The OpenClaw Army has **6 supporting services** that provide infrastructure for the 16-agent system.

## Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SERVICES                             │
├─────────────┬─────────────┬─────────────┬───────────────┤
│   Memory    │  Knowledge  │   Agent     │ Notification  │
│  :18820     │   :18850    │  :18860     │    :18870     │
├─────────────┴─────────────┴─────────────┴───────────────┤
│   Ralph :18840    │    VisionClaw Gateway :18830          │
└─────────────────────────────────────────────────────────┘
```

## Memory Service (18820)

**File:** `services/memory-service/main.py`  
**Purpose:** 3-tier memory persistence

### Tiers
1. **Redis** — Recent messages (24h sliding window)
2. **PostgreSQL** — Session summaries
3. **ChromaDB** — Semantic long-term memory

### Features
- PII redaction (emails, phones, SSNs)
- Diary entries per agent
- Provenance tracking
- Vector similarity search

### API
- `memory_store()` — Store with metadata
- `memory_search()` — Vector search
- Session context management

See [[Memory Architecture]] for details.

---

## Knowledge Bridge (18850)

**File:** `services/knowledge-bridge/main.py`  
**Purpose:** Obsidian vault API

### Capabilities
- Search notes by content
- Read/write markdown files
- Tag management
- Template support

### Vault Structure
```
vault/
├── agents/           # Agent documentation
├── research/         # Research notes
├── code-patterns/    # Reusable code
├── decisions/        # ADRs
├── daily-logs/       # Activity logs
├── projects/         # Project docs
├── inbox/            # Incoming
└── templates/        # Templates
```

### API
```python
knowledge_query(action="search", query="architecture")
knowledge_query(action="write", path="notes/topic.md", content="...")
```

---

## Agent Registry (18860)

**File:** `services/agent-registry/main.py`  
**Purpose:** Central agent registration & discovery

### Features
- Self-registration on boot
- Heartbeat monitoring (60s timeout)
- Capability discovery
- Port management

### Registration
Agents register with:
- Name & port
- Capabilities list
- Model info
- Status

### Health Checks
- Heartbeat every 30s
- Marked DOWN if no heartbeat
- Auto-restart via watchdog

---

## Notification Service (18870)

**File:** `services/notification/main.py`  
**Purpose:** Email notifications

### Configuration
- Gmail SMTP
- Requires `GMAIL_APP_PASSWORD` in `.env`
- Default recipient from `OWNER_EMAIL`

### Use Cases
- Task completions
- System alerts
- Daily digests
- User notifications

---

## Ralph (18840)

**File:** `services/ralph/`  
**Purpose:** Autonomous PRD-driven coding

### Workflow
1. **Plan** — Parse PRD requirements
2. **Code** — Generate implementation
3. **Test** — Run validation
4. **Reflect** — Analyze results
5. **Complete** — Deliver output

### Capabilities
- Reads PRD documents
- Generates code automatically
- Self-tests implementations
- Iterates until passing

---

## VisionClaw Gateway (18830)

**File:** Integrated into Orchestrator  
**Purpose:** Meta Ray-Ban glasses integration

### How It Works
1. Glasses stream camera + audio to Gemini Live
2. Gemini delegates to OpenClaw via `/v1/chat/completions`
3. All 101 tools available to glasses user
4. Results returned to glasses display

### Configuration
- Gateway bind mode: `lan` or `loopback`
- Token-based auth
- Session management

### Commands
```python
visionclaw(action="status")     # Active sessions
visionclaw(action="config")     # Current config
visionclaw(action="configure", bind_mode="lan")
visionclaw(action="send", session_id="...", message="...")
visionclaw(action="history", session_id="...")
```

---

## Service Dependencies

```
Orchestrator (18830)
    ├── Memory Service (18820) ──→ Redis, PostgreSQL, ChromaDB
    ├── Knowledge Bridge (18850) ──→ Obsidian vault
    ├── Agent Registry (18860) ──→ In-memory registry
    ├── Notification (18870) ──→ Gmail SMTP
    ├── Ralph (18840) ──→ File system, git
    └── VisionClaw (18830) ──→ Gemini Live
```

## Infrastructure

### Required Services
- **PostgreSQL 17** — Port 5432
- **Redis** — Port 6379
- **ChromaDB** — Embedded

### Auto-Start
All services configured via `setup_launchd()` for macOS auto-start.

## Monitoring

Each service exposes:
- `/health` — Health check endpoint
- Logs — Activity and errors
- Metrics — Performance data

## Related Notes

- [[Memory Architecture]] — 3-tier memory
- [[Meta-Orchestrator]] — Primary service consumer
- [[Self-Healing System]] — Service recovery
- [[Agent Registry]] — Health monitoring

---

**Tags:** #services #infrastructure #memory #knowledge #registry #notification #ralph #visionclaw
