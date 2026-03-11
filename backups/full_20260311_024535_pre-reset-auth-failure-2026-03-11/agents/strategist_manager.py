#!/usr/bin/env python3
"""
Strategist Manager - Business Strategy & Planning
Port: 18880
Workers: strategy-1 (business models), strategy-2 (competitive analysis)
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strategist-manager")

app = FastAPI(title="Strategist Manager", version="1.0.0")

KING_URL = "http://localhost:18830"
WORKERS = {
    "strategy-1": {"port": 18881, "specialty": "business_model_innovation", "status": "idle"},
    "strategy-2": {"port": 18882, "specialty": "competitive_positioning", "status": "idle"}
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
                "name": "strategist-manager",
                "port": 18880,
                "type": "manager",
                "capabilities": ["business_strategy", "market_positioning", "pivot_analysis", "competitive_intelligence"],
                "workers": list(WORKERS.keys())
            }, timeout=10.0)
            logger.info("Registered with King")
        except Exception as e:
            logger.error(f"Registration failed: {e}")

@app.post("/delegate")
async def delegate_task(request: TaskRequest):
    """Delegate strategy tasks to appropriate worker"""
    worker_id = "strategy-1" if "business_model" in request.description.lower() or "revenue" in request.description.lower() else "strategy-2"
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
    return {"status": "healthy", "manager": "strategist", "workers": WORKERS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18880)
