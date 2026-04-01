#!/usr/bin/env python3
"""Dynamic Agent Spawner - Creates and registers new agents automatically."""

import socket
import requests
import json
import uuid
from datetime import datetime
from pathlib import Path

ORCHESTRATOR_URL = "http://localhost:18830"
AGENT_TEMPLATE = '''#!/usr/bin/env python3
"""Auto-generated agent: {name}"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="{name}")

@app.get("/health")
async def health():
    return {{"status": "up", "agent": "{name}", "port": {port}}}

@app.post("/execute")
async def execute(task: dict):
    return {{"result": "executed", "agent": "{name}", "task": task}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port={port})
'''

def find_free_port(start=19000, end=19100):
    """Find first available port in range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise RuntimeError("No free ports available")

def spawn_agent(agent_type: str, name: str = None) -> dict:
    """Spawn a new agent with auto-configuration."""
    port = find_free_port()
    agent_name = name or f"{agent_type}-{uuid.uuid4().hex[:8]}"
    
    # Generate agent file
    agent_code = AGENT_TEMPLATE.format(name=agent_name, port=port)
    agent_path = Path(f"agents/generated/{agent_name}.py")
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(agent_code)
    
    # Register with orchestrator
    registration = {
        "name": agent_name,
        "port": port,
        "type": agent_type,
        "status": "up",
        "registered_at": datetime.now().isoformat()
    }
    
    # Store registration locally
    registry_path = Path("data/agent-registry.json")
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    registry[agent_name] = registration
    registry_path.write_text(json.dumps(registry, indent=2))
    
    return registration

def health_check_all():
    """Check health of all registered agents."""
    registry_path = Path("data/agent-registry.json")
    if not registry_path.exists():
        return {"status": "no_registry"}
    
    registry = json.loads(registry_path.read_text())
    results = {}
    
    for name, info in registry.items():
        try:
            resp = requests.get(f"http://localhost:{info['port']}/health", timeout=5)
            results[name] = {"status": "up" if resp.status_code == 200 else "down"}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
    
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        print(json.dumps(health_check_all(), indent=2))
    else:
        # Demo spawn
        result = spawn_agent("demo")
        print(f"Spawned: {result}")
