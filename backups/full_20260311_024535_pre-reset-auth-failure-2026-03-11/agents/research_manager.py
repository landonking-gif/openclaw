#!/usr/bin/env python3
"""
Research Manager - Market Intelligence & Analysis
Port: 18890
Workers: research-1 (market_sizing), research-2 (trend_analysis)
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research-manager")

app = FastAPI(title="Research Manager", version="1.0.0")

KING_URL = "http://localhost:18830"
WORKERS = {
    "research-1": {"port": 18891, "specialty": "market_sizing_tam_sam", "status": "idle"},
    "research-2": {"port": 18892, "specialty": "trend_forecasting", "status": "idle"}
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
                "name": "research-manager",
                "port": 18890,
                "type": "manager",
                "capabilities": ["market_research", "tam_sam_som", "competitive_analysis", "trend_forecasting"],
                "workers": list(WORKERS.keys())
            }, timeout=10.0)
            logger.info("Registered with King")
        except Exception as e:
            logger.error(f"Registration failed: {e}")

@app.post("/delegate")
async def delegate_task(request: TaskRequest):
    worker_id = "research-1" if "tam" in request.description.lower() or "market size" in request.description.lower() else "research-2"
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
    return {"status": "healthy", "manager": "research", "workers": WORKERS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18890)
