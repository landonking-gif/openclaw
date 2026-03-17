---
title: Supporting Services
date: 2026-03-17
tags: [services, memory, knowledge-bridge, registry, notifications]
author: Meta-Orchestrator
---

# Supporting Services

Six services provide infrastructure for the 16-agent army.

---

## Memory Service (:18820)

**3-Tier Memory System**

| Tier | Technology | Purpose | TTL |
|------|------------|---------|-----|
| **Tier 1** | Redis | Recent messages, sliding window | 72 hours |
| **Tier 2** | PostgreSQL | Session summaries, LLM-generated | 30 days |
| **Tier 3** | ChromaDB + PostgreSQL | Semantic long-term memory | Indefinite |

### Features
- PII redaction before storage
- Diary entries for significant events
- Reflection prompts for learning
- Provenance tracking

### API Endpoints
- `POST /store` - Save memory
- `POST /search` - Recall memories
- `POST /diary` - Add diary entry
- `POST /reflect` - Generate reflection

See [[memory-systems]] for full details.

---

## Knowledge Bridge (:18850)

**Obsidian Vault API**

REST API for creating, searching, and managing notes in the shared Obsidian vault.

### Capabilities
- Create notes with frontmatter
- Search across all notes
- Read/write operations
- Tag management
- Daily log automation

### Valid Folders
- `agents/` - Agent-specific notes
- `research/` - Research findings
- `code-patterns/` - Reusable code
- `decisions/` - Architecture decisions
- `daily-logs/` - Daily activity logs
- `projects/` - Project documentation
- `inbox/` - Unsorted notes

### API Endpoints
- `POST /notes` - Create note
- `GET /notes/search` - Search notes
- `GET /notes/{path}` - Read note
- `PUT /notes/{path}` - Update note
- `GET /tags` - List all tags

---

## Agent Registry (:18860)

**Central Agent Directory**

Agents self-register on boot with capabilities, model info, and port.

### Features
- Heartbeat monitoring
- Capability discovery
- Lifecycle management
- Health status tracking

### API Endpoints
- `POST /register` - Agent registration
- `POST /heartbeat/{agent}` - Heartbeat ping
- `GET /agents` - List all agents
- `GET /agents/{agent}` - Get agent details
- `GET /discover/{capability}` - Find agents by capability

---

## Notification Service (:18870)

**Email Notifications**

Sends email via Gmail SMTP.

### Configuration
Requires SMTP credentials in environment:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`

### API Endpoints
- `POST /send` - Send email
- `POST /notify` - Send notification

---

## Ralph (:18840)

**Autonomous PRD-Driven Coding Loop**

Self-directed coding agent that:
1. Reads PRD documents
2. Plans implementation
3. Writes code
4. Tests validation
5. Reflects on results
6. Marks complete

Ralph operates independently on product requirements.

---

## Infrastructure Services

### PostgreSQL (:5432)
- Session storage
- Long-term memory
- Agent registry data

### Redis (:6379)
- Recent message cache
- Pub/sub messaging
- Rate limiting

---

## Service Dependencies

```
┌─────────────────┐
│  Orchestrator   │
│    :18830       │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┐
    ↓         ↓        ↓        ↓
 Memory    Knowledge Agent    Notify
 Service   Bridge    Registry  Service
 :18820    :18850    :18860    :18870
    │         │        │        │
    └─────────┴────────┴────────┘
              ↓
         PostgreSQL
            :5432
              ↓
            Redis
            :6379
```

---

## See Also

- [[memory-systems]] - Detailed memory architecture
- [[index]] - Return to master index
