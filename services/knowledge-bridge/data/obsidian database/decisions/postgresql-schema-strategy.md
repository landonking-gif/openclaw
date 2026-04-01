# Decision: PostgreSQL Schema Strategy

**Date:** 2026-03-16  
**Status:** Accepted  
**Decision Maker:** Meta-Orchestrator

## Problem
PostgreSQL user `openclaw` lacks CREATE privileges on the `public` schema, preventing table creation for agent heartbeats, task history, and quality metrics.

## Options Considered
1. **Request elevated permissions** — Grant CREATE on public schema
2. **Create dedicated schema** — `CREATE SCHEMA openclaw AUTHORIZATION openclaw`
3. **Use existing schema** — Check if tables already exist under different schema
4. **Use SQLite exclusively** — Defer to SQLite for operational tables

## Decision
**Option 2 + 4 hybrid:** Create dedicated `openclaw` schema when possible, but implement critical tables in SQLite immediately for operational continuity.

## Rationale
- SQLite requires no external permissions
- SQLite sufficient for session tracking and tool usage analytics
- PostgreSQL valuable for multi-agent heartbeat aggregation when available
- No immediate need to escalate database permissions

## Implementation
- SQLite tables: ✅ Created
- PostgreSQL schema: ⏳ Pending permission grant

tags: #type/decision #status/accepted #priority/high
