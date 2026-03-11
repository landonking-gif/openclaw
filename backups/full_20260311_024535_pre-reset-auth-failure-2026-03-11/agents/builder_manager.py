#!/usr/bin/env python3
"""
Builder Manager - Technical Architecture & MVP Development
Port: 18900
Workers: builder-1 (prototype_dev), builder-2 (tool_integration)
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("builder-manager")

app = FastAPI(title="Builder Manager", version="1.0.0")

KING_URL = "http://localhost:18830"
WORKERS = {
    "builder-1": {"port": 18901, "specialty": "prototype_development", "status": "idle"},
    "builder-2": {"port": 18902, "specialty": "tool_integration", "status": "idle"}
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
                "name": "builder-manager",
                "port": 18900,
                "type": "manager",
                "capabilities": ["mvp_development", "technical_architecture", "tool_integration", "code_generation"],
                "workers": list(WORKERS.keys())
            }, timeout=10.0)
            logger.info("Registered with King")
        except Exception as e:
            logger.error(f"Registration failed: {e}")

@app.post("/delegate")
async def delegate_task(request: TaskRequest):
    worker_id = "builder-1" if "prototype" in request.description.lower() or "code" in request.description.lower() else "builder-2"
    worker = WORKERS[worker_id]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://localhost:{worker['port']}/execute",
                json={"task": request.description, "context": request.context},
                timeout=120.0
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
    return {"status": "healthy", "manager": "builder", "workers": WORKERS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18900)
