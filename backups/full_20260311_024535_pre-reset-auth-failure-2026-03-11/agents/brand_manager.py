#!/usr/bin/env python3
"""
Brand Manager - Creative Direction & Identity
Port: 18910
Workers: brand-1 (naming_messaging), brand-2 (visual_identity)
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brand-manager")

app = FastAPI(title="Brand Manager", version="1.0.0")

KING_URL = "http://localhost:18830"
WORKERS = {
    "brand-1": {"port": 18911, "specialty": "naming_copywriting", "status": "idle"},
    "brand-2": {"port": 18912, "specialty": "visual_design", "status": "idle"}
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
                "name": "brand-manager",
                "port": 18910,
                "type": "manager",
                "capabilities": ["brand_identity", "naming", "copywriting", "visual_design", "positioning"],
                "workers": list(WORKERS.keys())
            }, timeout=10.0)
            logger.info("Registered with King")
        except Exception as e:
            logger.error(f"Registration failed: {e}")

@app.post("/delegate")
async def delegate_task(request: TaskRequest):
    worker_id = "brand-1" if "name" in request.description.lower() or "message" in request.description.lower() else "brand-2"
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
    return {"status": "healthy", "manager": "brand", "workers": WORKERS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18910)
