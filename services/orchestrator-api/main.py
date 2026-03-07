"""
Orchestrator API — Meta-Orchestrator Planner Gateway
=====================================================

This is NOT a simple classifier/router. It is the MAIN LARGE-SCALE PLANNER.

Workflow:
1. Receives complex tasks from King AI or external requests
2. Analyzes the task to understand ALL its dimensions
3. Creates a comprehensive plan with sub-tasks
4. Routes ONLY relevant sub-tasks to the correct manager agents
5. Tracks workflow progress and synthesizes final results

Example: "Research best improvements, implement them, and send me an email"
→ Gamma-Manager gets: "Research best improvements to the program"
→ Beta-Manager gets: "Implement the top improvements identified by research"
→ Alpha-Manager gets: "Draft and send an email summarizing proposed changes"

Port: 18830
"""

import os
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Configuration ───────────────────────────────────────────────────────────

ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "18830"))
MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://localhost:18820")
ARMY_HOME = os.getenv("ARMY_HOME", os.path.expanduser("~/openclaw-army"))

# Agent port map
AGENT_PORTS = {
    "king-ai":        int(os.getenv("KING_PORT", "18789")),
    "alpha-manager":  int(os.getenv("ALPHA_MANAGER_PORT", "18800")),
    "beta-manager":   int(os.getenv("BETA_MANAGER_PORT", "18801")),
    "gamma-manager":  int(os.getenv("GAMMA_MANAGER_PORT", "18802")),
    "coding-1":       int(os.getenv("CODING_1_PORT", "18803")),
    "coding-2":       int(os.getenv("CODING_2_PORT", "18804")),
    "coding-3":       int(os.getenv("CODING_3_PORT", "18805")),
    "coding-4":       int(os.getenv("CODING_4_PORT", "18806")),
    "agentic-1":      int(os.getenv("AGENTIC_1_PORT", "18807")),
    "agentic-2":      int(os.getenv("AGENTIC_2_PORT", "18808")),
    "agentic-3":      int(os.getenv("AGENTIC_3_PORT", "18809")),
    "agentic-4":      int(os.getenv("AGENTIC_4_PORT", "18810")),
    "general-1":      int(os.getenv("GENERAL_1_PORT", "18811")),
    "general-2":      int(os.getenv("GENERAL_2_PORT", "18812")),
    "general-3":      int(os.getenv("GENERAL_3_PORT", "18813")),
    "general-4":      int(os.getenv("GENERAL_4_PORT", "18814")),
}

# Manager → Worker pool mapping
MANAGER_POOLS = {
    "alpha-manager": {
        "description": "General-purpose tasks: writing, summarization, Q&A, Mac automation, email, communication",
        "workers": ["general-1", "general-2", "general-3", "general-4"],
        "capabilities": [
            "writing", "prose", "summarization", "summary", "qa", "help",
            "automation", "mac", "email", "communication", "notification",
            "report", "documentation", "draft", "template", "formatting",
        ],
    },
    "beta-manager": {
        "description": "Software engineering: coding, implementation, testing, debugging, infrastructure",
        "workers": ["coding-1", "coding-2", "coding-3", "coding-4"],
        "capabilities": [
            "code", "coding", "implement", "programming", "python", "javascript",
            "typescript", "bash", "script", "debug", "fix", "bug", "test",
            "testing", "deploy", "infrastructure", "refactor", "optimize",
            "build", "compile", "install", "package", "api", "database",
            "schema", "migration", "docker", "git", "version", "ci", "cd",
        ],
    },
    "gamma-manager": {
        "description": "Research & analysis: web search, document analysis, data synthesis, fact-checking",
        "workers": ["agentic-1", "agentic-2", "agentic-3", "agentic-4"],
        "capabilities": [
            "research", "search", "investigate", "analyze", "analysis",
            "document", "data", "synthesis", "fact", "verify", "check",
            "compare", "evaluate", "benchmark", "study", "explore",
            "discover", "find", "look", "scan", "review", "assess",
            "audit", "inspect", "survey",
        ],
    },
}

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [orchestrator] %(message)s")
log = logging.getLogger("orchestrator")

# ── Models ──────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING   = "pending"
    PLANNING  = "planning"
    RUNNING   = "running"
    WAITING   = "waiting"
    COMPLETE  = "complete"
    FAILED    = "failed"

class SubTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str
    assigned_to: str  # Manager name
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)  # IDs of prerequisite subtasks
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    priority: int = 1  # 1=highest, 5=lowest

class WorkflowPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    original_task: str
    analysis: str = ""
    subtasks: list[SubTask] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    final_result: Optional[str] = None
    requester: str = "king-ai"

class PlanRequest(BaseModel):
    task: str
    requester: str = "king-ai"
    context: Optional[str] = None
    priority: int = 1

class SubTaskUpdate(BaseModel):
    status: TaskStatus
    result: Optional[str] = None

class DispatchRequest(BaseModel):
    workflow_id: str
    subtask_id: Optional[str] = None  # If None, dispatch all ready subtasks

# ── State ───────────────────────────────────────────────────────────────────

workflows: dict[str, WorkflowPlan] = {}
ws_subscribers: list[WebSocket] = []

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Army — Meta-Orchestrator Planner",
    description="Large-scale task planner that decomposes complex tasks and distributes to relevant managers.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helper Functions ────────────────────────────────────────────────────────

def classify_task_to_managers(task_description: str) -> list[str]:
    """
    Determine which managers should handle a task based on keyword analysis.
    Returns list of manager names. Can return multiple managers for complex tasks.
    """
    task_lower = task_description.lower()
    matched_managers: dict[str, int] = {}

    for manager_name, info in MANAGER_POOLS.items():
        score = 0
        for keyword in info["capabilities"]:
            if keyword in task_lower:
                score += 1
        if score > 0:
            matched_managers[manager_name] = score

    if not matched_managers:
        # Default to alpha-manager for unclassified tasks
        return ["alpha-manager"]

    # Return all matched managers, sorted by relevance
    return sorted(matched_managers.keys(), key=lambda m: matched_managers[m], reverse=True)


def decompose_task(task: str, context: Optional[str] = None) -> WorkflowPlan:
    """
    The CORE PLANNING FUNCTION.

    Analyzes a complex task and breaks it into subtasks, each assigned
    to the most appropriate manager. Handles dependencies between subtasks.
    """
    plan = WorkflowPlan(
        original_task=task,
        status=TaskStatus.PLANNING,
    )

    task_lower = task.lower()

    # ── Analyze the task for multi-dimensional requirements ──
    needs_research  = any(kw in task_lower for kw in ["research", "find", "search", "investigate", "analyze", "discover", "look up", "explore", "compare", "evaluate", "benchmark", "study", "survey", "audit", "review"])
    needs_coding    = any(kw in task_lower for kw in ["implement", "code", "build", "create", "fix", "debug", "write code", "develop", "refactor", "optimize", "deploy", "test", "script", "install", "configure", "setup"])
    needs_writing   = any(kw in task_lower for kw in ["email", "write", "draft", "document", "summarize", "report", "send", "notify", "communicate", "format", "template", "present"])
    needs_general   = any(kw in task_lower for kw in ["help", "explain", "answer", "qa", "automate", "mac"])

    # If none matched, do a broader analysis
    if not any([needs_research, needs_coding, needs_writing, needs_general]):
        managers = classify_task_to_managers(task)
        for mgr in managers:
            plan.subtasks.append(SubTask(
                description=task,
                assigned_to=mgr,
                priority=1,
            ))
        plan.analysis = f"Single-dimension task routed to: {', '.join(managers)}"
        plan.status = TaskStatus.PENDING
        return plan

    # ── Build a multi-phase plan with dependencies ──
    analysis_parts = []
    phase = 0

    # Phase 1: Research (if needed) — always runs first
    research_id = None
    if needs_research:
        phase += 1
        research_subtask = SubTask(
            description=_extract_research_component(task),
            assigned_to="gamma-manager",
            priority=1,
        )
        research_id = research_subtask.id
        plan.subtasks.append(research_subtask)
        analysis_parts.append(f"Phase {phase}: Research & Analysis → gamma-manager")

    # Phase 2: Implementation (if needed) — depends on research
    coding_id = None
    if needs_coding:
        phase += 1
        coding_subtask = SubTask(
            description=_extract_coding_component(task),
            assigned_to="beta-manager",
            depends_on=[research_id] if research_id else [],
            priority=2,
        )
        coding_id = coding_subtask.id
        plan.subtasks.append(coding_subtask)
        analysis_parts.append(f"Phase {phase}: Implementation → beta-manager" + (" (depends on research)" if research_id else ""))

    # Phase 3: Writing/Communication (if needed) — depends on both research and coding
    if needs_writing:
        phase += 1
        deps = []
        if research_id:
            deps.append(research_id)
        if coding_id:
            deps.append(coding_id)
        writing_subtask = SubTask(
            description=_extract_writing_component(task),
            assigned_to="alpha-manager",
            depends_on=deps,
            priority=3,
        )
        plan.subtasks.append(writing_subtask)
        analysis_parts.append(f"Phase {phase}: Communication → alpha-manager" + (f" (depends on phases {', '.join(str(i+1) for i in range(len(deps)))})" if deps else ""))

    # Phase N: General tasks (if needed)
    if needs_general and not needs_writing:
        phase += 1
        plan.subtasks.append(SubTask(
            description=_extract_general_component(task),
            assigned_to="alpha-manager",
            priority=2,
        ))
        analysis_parts.append(f"Phase {phase}: General tasks → alpha-manager")

    plan.analysis = f"Multi-dimensional task decomposed into {len(plan.subtasks)} subtasks:\n" + "\n".join(analysis_parts)
    plan.status = TaskStatus.PENDING

    # Add context if provided
    if context:
        plan.analysis += f"\n\nAdditional context: {context}"

    return plan


def _extract_research_component(task: str) -> str:
    """Extract the research/analysis portion of a complex task."""
    task_lower = task.lower()
    # Look for research-related clauses
    research_verbs = ["research", "find", "search", "investigate", "analyze", "discover", "explore", "compare", "evaluate", "study", "review", "audit"]
    for verb in research_verbs:
        if verb in task_lower:
            # Try to extract the clause containing the research verb
            idx = task_lower.index(verb)
            # Find clause boundaries (comma, "and", period, or end)
            end = len(task)
            for sep in [", ", " and ", ". ", "; "]:
                sep_idx = task_lower.find(sep, idx + len(verb))
                if sep_idx != -1:
                    end = min(end, sep_idx)
            return f"Research and analyze: {task[idx:end].strip().rstrip(',;.')}"
    return f"Research and gather information relevant to: {task}"


def _extract_coding_component(task: str) -> str:
    """Extract the implementation/coding portion of a complex task."""
    task_lower = task.lower()
    coding_verbs = ["implement", "code", "build", "create", "fix", "debug", "develop", "refactor", "optimize", "deploy", "test", "script", "install", "configure", "setup"]
    for verb in coding_verbs:
        if verb in task_lower:
            idx = task_lower.index(verb)
            end = len(task)
            for sep in [", ", " and ", ". ", "; "]:
                sep_idx = task_lower.find(sep, idx + len(verb))
                if sep_idx != -1:
                    end = min(end, sep_idx)
            return f"Implement: {task[idx:end].strip().rstrip(',;.')}"
    return f"Implement the technical aspects of: {task}"


def _extract_writing_component(task: str) -> str:
    """Extract the writing/communication portion of a complex task."""
    task_lower = task.lower()
    writing_verbs = ["email", "write", "draft", "document", "summarize", "report", "send", "notify", "communicate", "format", "present"]
    for verb in writing_verbs:
        if verb in task_lower:
            idx = task_lower.index(verb)
            end = len(task)
            for sep in [", ", " and ", ". ", "; "]:
                sep_idx = task_lower.find(sep, idx + len(verb))
                if sep_idx != -1:
                    end = min(end, sep_idx)
            return f"Communication: {task[idx:end].strip().rstrip(',;.')}"
    return f"Draft communication about: {task}"


def _extract_general_component(task: str) -> str:
    """Extract general-purpose tasks."""
    return f"Handle general aspects of: {task}"


def get_ready_subtasks(plan: WorkflowPlan) -> list[SubTask]:
    """Get subtasks that are ready to execute (all dependencies complete)."""
    completed_ids = {st.id for st in plan.subtasks if st.status == TaskStatus.COMPLETE}
    ready = []
    for st in plan.subtasks:
        if st.status != TaskStatus.PENDING:
            continue
        if all(dep_id in completed_ids for dep_id in st.depends_on):
            ready.append(st)
    return ready


async def dispatch_to_manager(manager: str, subtask: SubTask, workflow_id: str) -> bool:
    """Send a subtask to the appropriate manager agent via HTTP."""
    port = AGENT_PORTS.get(manager)
    if not port:
        log.error(f"No port configured for manager: {manager}")
        return False

    # Build the message to send to the manager
    message = {
        "type": "workflow_task",
        "workflow_id": workflow_id,
        "subtask_id": subtask.id,
        "task": subtask.description,
        "priority": subtask.priority,
        "from": "orchestrator",
    }

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{port}/api/v1/messages",
                json=message,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status in (200, 201, 202):
                    subtask.status = TaskStatus.RUNNING
                    subtask.started_at = datetime.now(timezone.utc).isoformat()
                    log.info(f"Dispatched subtask {subtask.id} to {manager} (port {port})")
                    return True
                else:
                    log.warning(f"Manager {manager} returned {resp.status}")
                    return False
    except ImportError:
        # Fallback without aiohttp
        import urllib.request
        try:
            req = urllib.request.Request(
                f"http://localhost:{port}/api/v1/messages",
                data=json.dumps(message).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            subtask.status = TaskStatus.RUNNING
            subtask.started_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as e:
            log.warning(f"Failed to dispatch to {manager}: {e}")
            return False
    except Exception as e:
        log.warning(f"Failed to dispatch to {manager}: {e}")
        return False


async def notify_ws(event: dict):
    """Broadcast workflow event to WebSocket subscribers."""
    if not ws_subscribers:
        return
    message = json.dumps(event)
    dead = []
    for ws in ws_subscribers:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_subscribers.remove(ws)


async def log_to_memory(content: str, category: str = "orchestrator"):
    """Log plan/workflow events to memory service."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{MEMORY_SERVICE_URL}/memory/commit",
            data=json.dumps({
                "agent_name": "orchestrator",
                "content": content,
                "category": category,
                "importance": 0.8,
                "metadata": {"source": "orchestrator-api"},
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass  # Non-critical


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator-api",
        "active_workflows": len([w for w in workflows.values() if w.status in (TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.WAITING)]),
        "total_workflows": len(workflows),
    }


@app.post("/plan")
async def create_plan(req: PlanRequest):
    """
    THE CORE ENDPOINT — Takes a complex task, decomposes it into subtasks,
    and assigns each to the appropriate manager.
    """
    log.info(f"Planning task: {req.task[:100]}...")

    plan = decompose_task(req.task, req.context)
    plan.requester = req.requester
    workflows[plan.id] = plan

    await log_to_memory(
        f"Created workflow plan '{plan.id}': {req.task}\n"
        f"Decomposed into {len(plan.subtasks)} subtasks:\n"
        + "\n".join(f"  - [{st.assigned_to}] {st.description}" for st in plan.subtasks)
    )

    await notify_ws({
        "event": "plan_created",
        "workflow_id": plan.id,
        "subtask_count": len(plan.subtasks),
        "analysis": plan.analysis,
    })

    return {
        "workflow_id": plan.id,
        "analysis": plan.analysis,
        "subtasks": [
            {
                "id": st.id,
                "description": st.description,
                "assigned_to": st.assigned_to,
                "depends_on": st.depends_on,
                "priority": st.priority,
            }
            for st in plan.subtasks
        ],
        "status": plan.status,
    }


@app.post("/plan/{workflow_id}/dispatch")
async def dispatch_workflow(workflow_id: str, req: Optional[DispatchRequest] = None):
    """
    Dispatch ready subtasks to their assigned managers.
    If subtask_id is specified, dispatch only that subtask.
    Otherwise, dispatch all subtasks whose dependencies are met.
    """
    plan = workflows.get(workflow_id)
    if not plan:
        raise HTTPException(404, f"Workflow {workflow_id} not found")

    dispatched = []
    failed = []

    if req and req.subtask_id:
        # Dispatch specific subtask
        subtask = next((st for st in plan.subtasks if st.id == req.subtask_id), None)
        if not subtask:
            raise HTTPException(404, f"Subtask {req.subtask_id} not found")
        success = await dispatch_to_manager(subtask.assigned_to, subtask, workflow_id)
        if success:
            dispatched.append(subtask.id)
        else:
            failed.append(subtask.id)
    else:
        # Dispatch all ready subtasks
        ready = get_ready_subtasks(plan)
        for subtask in ready:
            success = await dispatch_to_manager(subtask.assigned_to, subtask, workflow_id)
            if success:
                dispatched.append(subtask.id)
            else:
                failed.append(subtask.id)

    if dispatched:
        plan.status = TaskStatus.RUNNING

    await notify_ws({
        "event": "subtasks_dispatched",
        "workflow_id": workflow_id,
        "dispatched": dispatched,
        "failed": failed,
    })

    return {
        "dispatched": dispatched,
        "failed": failed,
        "remaining": [st.id for st in plan.subtasks if st.status == TaskStatus.PENDING],
    }


@app.put("/plan/{workflow_id}/subtask/{subtask_id}")
async def update_subtask(workflow_id: str, subtask_id: str, update: SubTaskUpdate):
    """
    Update a subtask's status (called by managers when they complete work).
    Automatically dispatches next-phase subtasks when dependencies are met.
    """
    plan = workflows.get(workflow_id)
    if not plan:
        raise HTTPException(404, f"Workflow {workflow_id} not found")

    subtask = next((st for st in plan.subtasks if st.id == subtask_id), None)
    if not subtask:
        raise HTTPException(404, f"Subtask {subtask_id} not found")

    subtask.status = update.status
    if update.result:
        subtask.result = update.result
    if update.status == TaskStatus.COMPLETE:
        subtask.completed_at = datetime.now(timezone.utc).isoformat()

    log.info(f"Subtask {subtask_id} updated to {update.status} in workflow {workflow_id}")

    # Check if all subtasks are complete
    all_complete = all(st.status == TaskStatus.COMPLETE for st in plan.subtasks)
    any_failed = any(st.status == TaskStatus.FAILED for st in plan.subtasks)

    if all_complete:
        plan.status = TaskStatus.COMPLETE
        plan.completed_at = datetime.now(timezone.utc).isoformat()
        # Synthesize final result from all subtask results
        results = [f"[{st.assigned_to}] {st.description}:\n{st.result or '(no result)'}" for st in plan.subtasks]
        plan.final_result = "\n\n---\n\n".join(results)

        await log_to_memory(
            f"Workflow '{workflow_id}' COMPLETED: {plan.original_task}\n"
            f"Results from {len(plan.subtasks)} subtasks synthesized."
        )
    elif any_failed:
        plan.status = TaskStatus.FAILED

    # Auto-dispatch newly ready subtasks
    auto_dispatched = []
    if update.status == TaskStatus.COMPLETE:
        ready = get_ready_subtasks(plan)
        for ready_st in ready:
            success = await dispatch_to_manager(ready_st.assigned_to, ready_st, workflow_id)
            if success:
                auto_dispatched.append(ready_st.id)

    await notify_ws({
        "event": "subtask_updated",
        "workflow_id": workflow_id,
        "subtask_id": subtask_id,
        "new_status": update.status,
        "workflow_complete": all_complete,
        "auto_dispatched": auto_dispatched,
    })

    return {
        "subtask_id": subtask_id,
        "status": update.status,
        "workflow_status": plan.status,
        "workflow_complete": all_complete,
        "auto_dispatched": auto_dispatched,
    }


@app.get("/plan/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get full workflow status and all subtask details."""
    plan = workflows.get(workflow_id)
    if not plan:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return plan.model_dump()


@app.get("/plans")
async def list_workflows(status: Optional[str] = None, limit: int = 20):
    """List all workflows, optionally filtered by status."""
    items = list(workflows.values())
    if status:
        items = [w for w in items if w.status == status]
    items.sort(key=lambda w: w.created_at, reverse=True)
    return {
        "total": len(items),
        "workflows": [
            {
                "id": w.id,
                "original_task": w.original_task[:100],
                "status": w.status,
                "subtask_count": len(w.subtasks),
                "created_at": w.created_at,
                "completed_at": w.completed_at,
            }
            for w in items[:limit]
        ],
    }


@app.post("/classify")
async def classify_task(req: PlanRequest):
    """
    Quick classification of which managers would handle a task.
    Useful for King AI to preview routing before creating a full plan.
    """
    managers = classify_task_to_managers(req.task)
    return {
        "task": req.task,
        "managers": managers,
        "details": {
            mgr: MANAGER_POOLS[mgr]["description"]
            for mgr in managers
            if mgr in MANAGER_POOLS
        },
    }


@app.get("/agents")
async def list_agents():
    """List all agents and their roles/ports."""
    agents = []
    for name, port in AGENT_PORTS.items():
        role = "king" if name == "king-ai" else ("manager" if "manager" in name else "worker")
        manager = None
        if role == "worker":
            for mgr, info in MANAGER_POOLS.items():
                if name in info["workers"]:
                    manager = mgr
                    break
        agents.append({
            "name": name,
            "port": port,
            "role": role,
            "manager": manager,
        })
    return {"agents": agents}


@app.get("/agents/{agent_name}/status")
async def agent_status(agent_name: str):
    """Check if a specific agent is alive and responsive."""
    port = AGENT_PORTS.get(agent_name)
    if not port:
        raise HTTPException(404, f"Unknown agent: {agent_name}")

    try:
        import urllib.request
        resp = urllib.request.urlopen(f"http://localhost:{port}/", timeout=5)
        status_code = resp.getcode()
        # OpenClaw agents serve HTML on root — a 200 means alive
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            data = json.loads(resp.read())
            return {"agent": agent_name, "status": "alive", "port": port, "health": data}
        else:
            return {"agent": agent_name, "status": "alive", "port": port, "http_status": status_code}
    except Exception as e:
        return {"agent": agent_name, "status": "unreachable", "port": port, "error": str(e)}


# ── WebSocket for real-time workflow updates ────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_subscribers.append(ws)
    log.info(f"WebSocket client connected ({len(ws_subscribers)} total)")
    try:
        while True:
            # Keep connection alive, accept pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_subscribers.remove(ws)
        log.info(f"WebSocket client disconnected ({len(ws_subscribers)} remaining)")


# ── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    log.info(f"Orchestrator API starting on port {ORCHESTRATOR_PORT}")
    log.info(f"Configured agents: {list(AGENT_PORTS.keys())}")
    log.info(f"Manager pools: {list(MANAGER_POOLS.keys())}")


# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT, log_level="info")
