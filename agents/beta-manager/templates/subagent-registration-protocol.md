# Subagent Registration Protocol

**Version:** 1.0  
**Created:** 2026-03-20  
**For:** Dynamic Agent Creation & Lifecycle Management  
**Port Range:** 19000-19100

---

## Overview

This protocol enables automatic registration of new manager/worker pairs into the OpenClaw orchestration system with zero manual configuration.

## 1. Port Allocation

### Algorithm
```python
def allocate_port(agent_type: str) -> int:
    """
    Auto-allocate port in range 19000-19100
    Managers: 19000-19049 (reserved block)
    Workers: 19050-19100
    """
    base = 19000 if agent_type == "manager" else 19050
    for offset in range(50):
        port = base + offset
        if not port_in_use(port):
            return port
    raise PortExhaustedError("No available ports in range")
```

### Port Registry (Redis)
- Key: `openclaw:ports:{port}`
- Value: `{agent_name}:{pid}:{timestamp}`
- TTL: 60s (refreshed by heartbeat)

## 2. FastAPI Template

### Manager Template
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio

app = FastAPI(title="{name}-manager")

class HealthReport(BaseModel):
    worker_id: str
    status: str
    cpu_percent: float
    memory_mb: float
    tasks_completed: int

@app.post("/delegate")
async def delegate_task(task: dict):
    """Route task to appropriate worker"""
    pass

@app.get("/health")
async def health():
    return {"status": "healthy", "workers": []}

@app.get("/capabilities")
async def capabilities():
    return {
        "manager_type": "{name}",
        "workers": ["{name}-1", "{name}-2", "{name}-3", "{name}-4"],
        "features": []
    }
```

### Worker Template
```python
from fastapi import FastAPI
import httpx
import asyncio

app = FastAPI(title="{name}-worker-{n}")

@app.post("/execute")
async def execute_task(task: dict):
    """Execute delegated task"""
    pass

@app.get("/health")
async def health():
    return {"status": "ready", "load": 0.0}
```

## 3. Capability Discovery

### Endpoint: GET /capabilities

**Manager Response:**
```json
{
  "agent_type": "manager",
  "name": "custom-manager",
  "port": 19000,
  "workers": [
    {"id": "custom-1", "port": 19050, "specialty": "task_a"},
    {"id": "custom-2", "port": 19051, "specialty": "task_b"}
  ],
  "capabilities": ["capability_1", "capability_2"],
  "version": "1.0.0"
}
```

**Worker Response:**
```json
{
  "agent_type": "worker",
  "name": "custom-1",
  "port": 19050,
  "manager": "custom-manager",
  "specialties": ["task_a"],
  "status": "available"
}
```

## 4. Health Check Integration

### Heartbeat Protocol
- **Interval:** 30 seconds
- **Endpoint:** POST /registry/heartbeat
- **Payload:**
```json
{
  "agent_name": "custom-1",
  "agent_type": "worker",
  "port": 19050,
  "manager": "custom-manager",
  "status": "healthy",
  "metrics": {
    "cpu_percent": 12.5,
    "memory_mb": 256,
    "tasks_active": 2,
    "tasks_completed": 47
  }
}
```

### Registry Behavior
- **First heartbeat:** Registers agent
- **Subsequent:** Refreshes TTL
- **Missed 3 heartbeats:** Marks agent as "suspected"
- **Missed 5 heartbeats:** Removes agent from registry

## 5. YAML Configuration Schema

### Agent Manifest
```yaml
# agent-manifest.yaml
apiVersion: openclaw.io/v1
kind: Agent
metadata:
  name: custom-manager
  labels:
    domain: custom
    tier: manager
spec:
  type: manager
  port_range: 19000-19049
  replicas: 1
  capabilities:
    - custom_capability_1
    - custom_capability_2
  workers:
    - name: custom-1
      specialty: specialty_a
      resources:
        memory: 512Mi
        cpu: 500m
    - name: custom-2
      specialty: specialty_b
    - name: custom-3
    - name: custom-4
  health_check:
    interval: 30
    timeout: 5
    retries: 3
  scaling:
    min_workers: 2
    max_workers: 8
    scale_up_cpu: 70
    scale_down_cpu: 30
```

### Registration Command
```bash
# Register new agent from manifest
python -m openclaw.registry register --manifest agent-manifest.yaml

# Or via API
curl -X POST http://localhost:18860/register \
  -H "Content-Type: application/yaml" \
  --data-binary @agent-manifest.yaml
```

## 6. Lifecycle States

```
REGISTERED → STARTING → HEALTHY → BUSY → DEGRADED → FAILED
                ↓           ↓         ↓
              STOPPED    UNHEALTHY  MAINTENANCE
```

## 7. Integration with Orchestrator

```python
# Auto-discovery on orchestrator startup
agents = registry.discover_agents()
for agent in agents:
    orchestrator.register_agent(agent)

# Dynamic discovery during runtime
@registry.on_new_agent
def handle_new_agent(agent):
    orchestrator.register_agent(agent)
    notify_king_ai(f"New agent registered: {agent.name}")
```

## 8. Security

- **Port binding:** localhost only (127.0.0.1)
- **Registration token:** Required for new agents
- **TLS:** Optional mTLS for agent-to-agent communication

---

**Usage:** Place manifests in `agents/manifests/` for auto-registration on startup.
