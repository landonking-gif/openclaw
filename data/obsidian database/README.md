# OpenClaw Army Knowledge Vault

Central knowledge database for the 16-agent OpenClaw Army system.

## Structure

| Folder | Purpose |
|--------|---------|
| `agents/` | Per-agent knowledge logs — each agent writes here |
| `research/` | Research findings, analysis reports |
| `code-patterns/` | Reusable code patterns and solutions |
| `decisions/` | Architecture and design decisions (ADRs) |
| `daily-logs/` | Daily activity summaries from agents |
| `projects/` | Active project knowledge and context |
| `templates/` | Note templates for consistent formatting |
| `inbox/` | Unsorted incoming notes for triage |

## How Agents Use This Vault

Agents interact via the **Knowledge Bridge API** at `http://localhost:18850`:

```bash
# Create a note
POST /notes {title, folder, content, tags, agent}

# Search notes
GET /search?q=keyword&tags=python,api&agent=coding-1

# Get recent notes
GET /recent?limit=10&agent=coding-1

# Get note by path
GET /note?path=research/some-topic.md
```

## Tagging Convention

- `#agent/king-ai`, `#agent/coding-1` — Source agent
- `#type/research`, `#type/code`, `#type/decision` — Note type
- `#project/openclaw-army` — Project scope
- `#status/draft`, `#status/verified` — Note maturity
- `#priority/high`, `#priority/low` — Importance
