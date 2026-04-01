# OpenClaw Army Containerization Guide

This guide explains how to run OpenClaw Army on a different computer with Docker.

## Files Added

- `docker-compose.army.yml`: full local stack
- `services/Dockerfile.python-service`: shared Python base image for services
- `.env.army.example`: environment template

## Services in the stack

- `postgres` (5432)
- `redis` (6379)
- `memory-service` (18820)
- `knowledge-bridge` (18850)
- `agent-registry` (18860)
- `notification` (18870)
- `orchestrator-api` (18830)

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Enough RAM for embedding stack (recommended 8GB+)

## Quick Start

1. Copy env template:

```bash
cp .env.army.example .env.army
```

2. Fill in keys in `.env.army` (at minimum one NVAPI key).

3. Start stack:

```bash
docker compose --env-file .env.army -f docker-compose.army.yml up -d --build
```

4. Check health:

```bash
curl http://localhost:18830/health
curl http://localhost:18820/health
```

## Stopping

```bash
docker compose --env-file .env.army -f docker-compose.army.yml down
```

## Data persistence

- Postgres: `army_postgres_data` volume
- Redis: `army_redis_data` volume
- Runtime files are bind-mounted from local repo (`data/`, `agents/`, `vault/`).

## Notes

- Desktop automation tools may have limitations inside containers depending on host OS permissions.
- For full GUI automation, host-native orchestrator execution is often better.
- The compose stack is best for service portability + backend orchestration consistency.

## Troubleshooting

### Orchestrator starts but chat fails

- Verify NVAPI keys in `.env.army`
- Check logs:

```bash
docker compose --env-file .env.army -f docker-compose.army.yml logs -f orchestrator-api
```

### Memory semantic search is empty

- Confirm `sentence-transformers` completed install in memory service logs
- Wait for first embedding model warm-up

### Ports already in use

- Update host-side published ports in `docker-compose.army.yml`
