#!/usr/bin/env python3
"""
Risk Manager - Compliance, Security & Ethics
Port: 18920
Workers: risk-1 (compliance), risk-2 (security_assessment)
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("risk-manager")

app = FastAPI(title="Risk Manager", version="1.0.0")

KING_URL = "http://localhost:18830"
WORKERS = {
    "risk-1": {"port": 18921, "specialty": "regulatory_compliance", "status": "idle"},
    "risk-2": {"port": 18922, "specialty": "security_ethics", "status": "idle"}
}

class TaskRequest(BaseModel):
    task_id: str
    description: str
    context: Optional[Dict] = None
    priority: int = 2

@app.on_event("startup")
async def register_with_king():
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{KING_URL}/register_agent", json={
                "name": "risk-manager",
                "port": 18920,
                "type": "manager",
                "capabilities": ["compliance_review", "gdpr_ccpa", "security_audit", "ethical_ai", "risk_mitigation"],
                "workers": list(WORKERS.keys())
            }, timeout=10.0)
            logger.info("Registered with King")
        except Exception as e:
            logger.error(f"Registration failed: {e}")

@app.post("/delegate")
async def delegate_task(request: TaskRequest):
    worker_id = "risk-1" if "compliance" in request.description.lower() or "gdpr" in request.description.lower() else "risk-2"
    worker = WORKERS[worker_id]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://localhost:{worker['port']}/execute",
                json={"task": request.description, "context": request.context},
                timeout=60.0
            )
            return {
                "dispatched": True,
                "worker": worker_id,
                "result": response.json() if response.status_code == 200 else {"error": response.text}
            }
        except Exception as e:
            return {"dispatched": False, "error": str(e), "worker": worker_id}

@app.get("/health")
async def health():
    return {"status": "healthy", "manager": "risk", "workers": WORKERS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18920)
