# Knowledge Vault Integration Guide

## What is Knowledge Vault?
Shared knowledge store via `http://localhost:18850`

## When to Use
- Before answering questions - search for known answers
- After answering - store Q&A pairs for reuse
- For research - cross-reference findings

## API Reference

### Search
```bash
GET http://localhost:18850/search?q=agent+checkpointing
```

### Create Note
```bash
POST http://localhost:18850/notes
{
  "title": "Agent Failure Recovery",
  "folder": "research",
  "content": "...",
  "tags": ["type/research", "agent/saga"],
  "agent": "agentic-4"
}
```

### Daily Log
```bash
POST http://localhost:18850/daily-log?agent=agentic-4
```

## Current Status
⚠️ Knowledge Vault blocked (internal IP restriction)
- Port: 18850
- Issue: Cannot access from sandboxed environment
- Workaround: File-based memory in workspace

## Migration Plan
Once unlocked:
1. Move daily logs to vault
2. Sync MEMORY.md entries
3. Store research findings
4. Centralize agent knowledge
