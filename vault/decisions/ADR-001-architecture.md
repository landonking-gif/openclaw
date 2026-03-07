---
title: "OpenClaw Army Architecture"
date: "2026-03-06"
agent: "king-ai"
tags: [type/decision, status/accepted, priority/high]
---

# ADR-001: OpenClaw Army Architecture

## Context
We need a multi-agent AI system that can handle complex, multi-domain tasks autonomously on macOS.

## Decision
16-agent hierarchical architecture:
- 1 Meta-Orchestrator (King AI) — plans and delegates
- 3 Managers (Alpha, Beta, Gamma) — coordinate domain-specific workers
- 12 Workers — execute tasks in coding, research, and general domains

All agents run as independent OpenClaw instances with unique service labels and ports (18789-18814).

## Infrastructure
- PostgreSQL (5432) — persistent memory tier 2
- Redis (6379) — fast session cache tier 1
- ChromaDB — vector embeddings tier 3
- Obsidian Vault — structured knowledge database

## Consequences
- Can handle any task by routing to the right specialist
- Agents learn independently via memory tiers
- Knowledge persists in Obsidian for human review and agent retrieval
- Requires ~16 node processes + 3 Python services + 2 databases
