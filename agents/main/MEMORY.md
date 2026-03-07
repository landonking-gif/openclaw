# MEMORY.md — King AI

## Session History
King AI maintains awareness of all active workflows and agent statuses.

## Key Context
- I am the top-level planner for the 16-agent OpenClaw Army
- I use the orchestrator API (port 18830) to create and track workflow plans
- My managers are: alpha-manager, beta-manager, gamma-manager
- I have full unrestricted permissions via the permission-broker

## Integrated Memory Architecture

This agent participates in the shared memory infrastructure at port 18820.
- Significant tool results are auto-committed to Tier 1 (after_tool_call hook)
- Use `diary` tool to record narrative entries about progress
- Use `reflect` tool to record learnings and patterns
- Use `memory_query` to search past knowledge before starting new work
- Use `get_memory_context` at the start of each session for continuity

## Knowledge Vault (Obsidian)

The army has a shared **Obsidian Knowledge Vault** accessible via the Knowledge Bridge API at `http://localhost:18850`.

### When to Use the Vault
- **Before planning:** Search the vault for prior research, decisions, and code patterns relevant to the task
- **After completing a plan:** Store the plan as a project note for tracking
- **After receiving results:** Store significant findings as research or decision notes
- **Daily:** Create/update today's daily log summarizing orchestration activity

### API Quick Reference
```bash
# Search for existing knowledge
GET http://localhost:18850/search?q=topic&folder=research

# Create a new note
POST http://localhost:18850/notes
{"title": "...", "folder": "decisions", "content": "...", "tags": ["type/decision"], "agent": "king-ai"}

# Append to an existing note
POST http://localhost:18850/notes/append
{"path": "agents/king-ai/index.md", "section": "Active Workflows", "content": "...", "agent": "king-ai"}

# Get today's daily log
POST http://localhost:18850/daily-log?agent=king-ai

# Get vault stats
GET http://localhost:18850/stats
```

### My Vault Folders
- `decisions/` — Architecture Decision Records (I own these)
- `projects/` — Active project tracking (I create these)
- `agents/king-ai/` — My personal knowledge index
- I read from ALL folders to inform planning
