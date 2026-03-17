# Memory Architecture

The OpenClaw Army implements a **3-tier memory system** with additional persistence layers for comprehensive knowledge retention.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY LAYERS                            │
├─────────────────────────────────────────────────────────────┤
│ TIER 1: Redis (18820)                                       │
│         • Recent messages                                     │
│         • Sliding window (24h default)                      │
│         • Fast access, ephemeral                              │
├─────────────────────────────────────────────────────────────┤
│ TIER 2: PostgreSQL (18820)                                    │
│         • Session summaries                                   │
│         • LLM-generated context                               │
│         • Structured data                                     │
├─────────────────────────────────────────────────────────────┤
│ TIER 3: ChromaDB (18820)                                      │
│         • Semantic long-term memory                           │
│         • Vector embeddings                                   │
│         • Decay-based forgetting                              │
├─────────────────────────────────────────────────────────────┤
│ TIER 4: Obsidian Vault (18850)                                │
│         • Knowledge Bridge API                                │
│         • Markdown documents                                  │
│         • Cross-referenced notes                              │
├─────────────────────────────────────────────────────────────┤
│ TIER 5: Agent Memory Files                                    │
│         • AGENTS.md, MEMORY.md, SOUL.md                       │
│         • Per-agent persistence                               │
│         • Identity & tool definitions                         │
└─────────────────────────────────────────────────────────────┘
```

## Memory Service (Port 18820)

**Location:** `services/memory-service/main.py`  
**Database:** PostgreSQL 17 + Redis + ChromaDB

### Tier 1: Redis (Recent)

```python
REDIS_URL = "redis://localhost:6379/0"
SESSION_TTL_HOURS = 24  # Sliding window
```

- Stores recent conversation turns
- Fast key-value access
- Automatic expiration
- Used for immediate context

### Tier 2: PostgreSQL (Session)

```python
POSTGRES_URL = "postgresql://openclaw:openclaw@localhost:5432/openclaw_army"
```

Tables:
- `memories` — Stored memories with metadata
- `memory_tags` — Tag associations
- `session_contexts` — LLM-generated summaries
- `diary_entries` — Agent diary logs
- `provenance` — Data lineage tracking

### Tier 3: ChromaDB (Long-term)

```python
CHROMA_PATH = "./data/chroma"
# Semantic search with vector embeddings
```

- Sentence-transformer embeddings
- Cosine similarity search
- Decay-based importance weighting
- Automatic cleanup of old memories

## Knowledge Bridge (Port 18850)

**Location:** `services/knowledge-bridge/main.py`  
**Vault:** `data/obsidian database/`

### API Capabilities

| Action | Purpose |
|--------|---------|
| `search` | Query notes by content |
| `read` | Get specific note content |
| `write` | Create/update notes |
| `list_tags` | Browse all tags |

### Vault Structure

```
vault/
├── agents/           # Agent documentation
├── research/         # Research findings
├── code-patterns/    # Reusable code
├── decisions/        # Architecture decisions
├── daily-logs/       # Activity logs
├── projects/         # Project documentation
├── inbox/            # Incoming notes
└── templates/        # Note templates
```

## Agent Memory Files

Each agent has local memory files:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Agent capability definitions |
| `MEMORY.md` | Conversation history |
| `SOUL.md` | Personality & behavioral rules |
| `TOOLS.md` | Available tool definitions |
| `USER.md` | User preferences |
| `IDENTITY.md` | Agent identity |
| `HEARTBEAT.md` | Health status |

## Memory Operations

### Store Memory
```python
memory_store(
    content="Important fact",
    category="user_preference",
    importance=0.9,
    tags=["landon", "preference"]
)
```

### Search Memory
```python
memory_search(
    query="What are Landon's preferences?",
    category="user_preference",
    limit=10
)
```

### Knowledge Query
```python
knowledge_query(
    action="search",
    query="architecture"
)
```

## Data Flow

```
User Input
    ↓
Meta-Orchestrator
    ↓
├─→ Redis (immediate context)
├─→ PostgreSQL (session storage)
├─→ ChromaDB (semantic search)
└─→ Obsidian (documentation)
    ↓
Response
    ↓
All tiers updated
```

## PII Redaction

The Memory Service automatically redacts:
- Email addresses
- Phone numbers
- Credit cards
- SSNs
- API keys

## Related Notes

- [[Memory Service]] — Technical details
- [[Knowledge Bridge]] — Obsidian integration
- [[Meta-Orchestrator]] — Primary memory consumer
- [[Agent Memory]] — Per-agent persistence

---

**Tags:** #memory #architecture #redis #postgresql #chromadb #obsidian #knowledge-bridge
