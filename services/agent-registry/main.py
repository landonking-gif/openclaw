"""
OpenClaw Army — Agent Registry Service
=======================================

Central registry for agent self-registration, capability discovery,
heartbeat monitoring, and lifecycle management.

Port: 18860

Agents register on boot with their capabilities, model info, and port.
The registry tracks liveness via heartbeat and exposes discovery APIs
so any service can find agents by capability.
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Config ──────────────────────────────────────────────────────────────────

REGISTRY_PORT = int(os.getenv("AGENT_REGISTRY_PORT", "18860"))
HEARTBEAT_TIMEOUT_SEC = int(os.getenv("HEARTBEAT_TIMEOUT_SEC", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [agent-registry] %(levelname)s %(message)s",
)
log = logging.getLogger("agent-registry")

# ── Models ──────────────────────────────────────────────────────────────────

class AgentRegistration(BaseModel):
    name: str
    port: int
    role: str  # king, manager, worker
    model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    manager: Optional[str] = None  # parent manager name
    metadata: dict = Field(default_factory=dict)


class AgentRecord(BaseModel):
    name: str
    port: int
    role: str
    model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    manager: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    registered_at: str = ""
    last_heartbeat: float = 0.0
    status: str = "online"  # online, stale, offline


class HeartbeatRequest(BaseModel):
    name: str
    load: float = 0.0  # 0-1 utilization
    active_tasks: int = 0


# ── State ───────────────────────────────────────────────────────────────────

registry: dict[str, AgentRecord] = {}

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Army — Agent Registry",
    description="Central agent registration, heartbeat, and capability discovery.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from shared.logging_middleware import StructuredLoggingMiddleware
    app.add_middleware(StructuredLoggingMiddleware, service_name="agent-registry")
except ImportError:
    pass

# ── Helpers ─────────────────────────────────────────────────────────────────

def _refresh_statuses():
    """Mark agents stale/offline based on heartbeat age."""
    now = time.time()
    for rec in registry.values():
        age = now - rec.last_heartbeat
        if age > HEARTBEAT_TIMEOUT_SEC * 3:
            rec.status = "offline"
        elif age > HEARTBEAT_TIMEOUT_SEC:
            rec.status = "stale"
        else:
            rec.status = "online"


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    _refresh_statuses()
    online = sum(1 for r in registry.values() if r.status == "online")
    return {
        "status": "healthy",
        "service": "agent-registry",
        "registered": len(registry),
        "online": online,
    }


@app.post("/register")
async def register_agent(req: AgentRegistration):
    """Register or re-register an agent."""
    now = time.time()
    rec = AgentRecord(
        name=req.name,
        port=req.port,
        role=req.role,
        model=req.model,
        capabilities=req.capabilities,
        manager=req.manager,
        metadata=req.metadata,
        registered_at=datetime.now(timezone.utc).isoformat(),
        last_heartbeat=now,
        status="online",
    )
    registry[req.name] = rec
    log.info(f"Registered agent: {req.name} (port={req.port}, role={req.role})")
    return {"registered": req.name, "status": "online"}


@app.post("/heartbeat")
async def heartbeat(req: HeartbeatRequest):
    """Update heartbeat for a registered agent."""
    rec = registry.get(req.name)
    if not rec:
        raise HTTPException(404, f"Agent '{req.name}' not registered")
    rec.last_heartbeat = time.time()
    rec.status = "online"
    rec.metadata["load"] = req.load
    rec.metadata["active_tasks"] = req.active_tasks
    return {"name": req.name, "status": "online"}


@app.delete("/agents/{name}")
async def deregister_agent(name: str):
    """Remove an agent from the registry."""
    if name not in registry:
        raise HTTPException(404, f"Agent '{name}' not registered")
    del registry[name]
    log.info(f"Deregistered agent: {name}")
    return {"deregistered": name}


@app.get("/agents")
async def list_agents(
    role: Optional[str] = None,
    status: Optional[str] = None,
    capability: Optional[str] = None,
):
    """List all registered agents with optional filters."""
    _refresh_statuses()
    agents = list(registry.values())

    if role:
        agents = [a for a in agents if a.role == role]
    if status:
        agents = [a for a in agents if a.status == status]
    if capability:
        agents = [a for a in agents if capability in a.capabilities]

    return {
        "total": len(agents),
        "agents": [a.model_dump() for a in agents],
    }


@app.get("/agents/{name}")
async def get_agent(name: str):
    """Get details for a specific agent."""
    _refresh_statuses()
    rec = registry.get(name)
    if not rec:
        raise HTTPException(404, f"Agent '{name}' not registered")
    return rec.model_dump()


@app.get("/discover")
async def discover(capability: str, only_online: bool = True):
    """Find agents that have a specific capability."""
    _refresh_statuses()
    matches = []
    for rec in registry.values():
        if capability in rec.capabilities:
            if only_online and rec.status != "online":
                continue
            matches.append(rec.model_dump())
    return {"capability": capability, "matches": matches}


@app.get("/topology")
async def topology():
    """Return the full agent hierarchy."""
    _refresh_statuses()
    tree: dict = {"king": None, "managers": {}, "workers": {}}
    for rec in registry.values():
        if rec.role == "king":
            tree["king"] = rec.model_dump()
        elif rec.role == "manager":
            tree["managers"][rec.name] = {
                **rec.model_dump(),
                "workers": [],
            }
        elif rec.role == "worker":
            mgr = rec.manager or "unassigned"
            tree["workers"].setdefault(mgr, []).append(rec.model_dump())
    # Link workers to managers
    for mgr_name, worker_list in tree["workers"].items():
        if mgr_name in tree["managers"]:
            tree["managers"][mgr_name]["workers"] = worker_list
    return tree


@app.on_event("startup")
async def startup():
    log.info(f"Agent Registry starting on port {REGISTRY_PORT}")
