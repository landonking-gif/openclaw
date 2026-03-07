"""
Ralph — Autonomous PRD-Driven Coding Loop
==========================================

Ralph is the autonomous coding agent that:
1. Reads a PRD (Product Requirements Document)
2. Plans the implementation
3. Writes code iteratively
4. Tests and validates
5. Writes diary entries and reflections
6. Reports back to the orchestrator

This service runs as a FastAPI endpoint that managers can invoke
to delegate autonomous coding tasks.

Port: 18840
"""

import os
import json
import sys
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Configuration ───────────────────────────────────────────────────────────

RALPH_PORT = int(os.getenv("RALPH_PORT", "18840"))
MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://localhost:18820")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:18830")
ARMY_HOME = os.getenv("ARMY_HOME", os.path.expanduser("~/openclaw-army"))

MAX_ITERATIONS = int(os.getenv("RALPH_MAX_ITERATIONS", "20"))
MIN_CONFIDENCE = float(os.getenv("RALPH_MIN_CONFIDENCE", "0.7"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ralph] %(message)s")
log = logging.getLogger("ralph")

# ── Models ──────────────────────────────────────────────────────────────────

class CycleStatus(str, Enum):
    IDLE        = "idle"
    PLANNING    = "planning"
    CODING      = "coding"
    TESTING     = "testing"
    VALIDATING  = "validating"
    REFLECTING  = "reflecting"
    COMPLETE    = "complete"
    FAILED      = "failed"

class PRDSection(BaseModel):
    title: str
    content: str
    priority: int = 1
    status: str = "pending"

class CodingCycle(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    prd_title: str
    prd_sections: list[PRDSection] = Field(default_factory=list)
    status: CycleStatus = CycleStatus.IDLE
    current_iteration: int = 0
    max_iterations: int = MAX_ITERATIONS
    plan: Optional[str] = None
    code_artifacts: list[dict] = Field(default_factory=list)
    test_results: list[dict] = Field(default_factory=list)
    diary_entries: list[str] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    requester: str = "beta-manager"
    workflow_id: Optional[str] = None
    subtask_id: Optional[str] = None

class StartCycleRequest(BaseModel):
    prd: str
    title: str = "Untitled PRD"
    requester: str = "beta-manager"
    max_iterations: int = MAX_ITERATIONS
    working_directory: Optional[str] = None
    workflow_id: Optional[str] = None
    subtask_id: Optional[str] = None

class CycleIterationRequest(BaseModel):
    cycle_id: str
    action: str  # "plan", "code", "test", "validate", "reflect", "complete"
    content: Optional[str] = None
    artifacts: Optional[list[dict]] = None
    confidence: Optional[float] = None

# ── State ───────────────────────────────────────────────────────────────────

cycles: dict[str, CodingCycle] = {}

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Ralph — Autonomous Coding Agent",
    description="PRD-driven autonomous coding loop with diary and reflection.",
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
    app.add_middleware(StructuredLoggingMiddleware, service_name="ralph")
except ImportError:
    pass

# ── Helpers ─────────────────────────────────────────────────────────────────

def parse_prd(prd_text: str) -> list[PRDSection]:
    """Parse a PRD into sections by headers."""
    sections = []
    current_title = "Overview"
    current_content: list[str] = []
    priority = 1

    for line in prd_text.split("\n"):
        if line.startswith("# ") or line.startswith("## "):
            # Save previous section
            if current_content:
                sections.append(PRDSection(
                    title=current_title,
                    content="\n".join(current_content).strip(),
                    priority=priority,
                ))
                priority += 1
            current_title = line.lstrip("#").strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections.append(PRDSection(
            title=current_title,
            content="\n".join(current_content).strip(),
            priority=priority,
        ))

    return sections


async def log_to_memory(content: str, category: str = "ralph"):
    """Log to memory service."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{MEMORY_SERVICE_URL}/memory/commit",
            data=json.dumps({
                "agent_name": "ralph",
                "content": content,
                "category": category,
                "importance": 0.7,
                "metadata": {"source": "ralph-service"},
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


async def diary_entry(cycle_id: str, entry: str, success: bool = True):
    """Record a diary entry for a cycle."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{MEMORY_SERVICE_URL}/memory/diary",
            data=json.dumps({
                "agent_name": "ralph",
                "story_id": f"ralph-cycle-{cycle_id}",
                "story_title": entry[:200],
                "attempt_number": 1,
                "success": success,
                "tags": ["ralph", "coding-cycle", cycle_id],
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


async def reflect(cycle_id: str, reflection: str):
    """Record a reflection for a cycle."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{MEMORY_SERVICE_URL}/memory/reflect",
            data=json.dumps({
                "agent_name": "ralph",
                "story_id": f"ralph-cycle-{cycle_id}",
                "story_title": reflection[:200],
                "total_attempts": 1,
                "final_success": True,
                "all_attempts": [],
                "metadata": {"reflection": reflection[:1000]},
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


async def report_to_orchestrator(cycle: CodingCycle):
    """Report cycle completion back to the orchestrator."""
    if not cycle.workflow_id or not cycle.subtask_id:
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{ORCHESTRATOR_URL}/plan/{cycle.workflow_id}/subtask/{cycle.subtask_id}",
            data=json.dumps({
                "status": "complete" if cycle.status == CycleStatus.COMPLETE else "failed",
                "result": f"Ralph coding cycle {cycle.id}: {cycle.status}. "
                          f"Iterations: {cycle.current_iteration}, "
                          f"Confidence: {cycle.confidence:.2f}. "
                          f"Artifacts: {len(cycle.code_artifacts)}. "
                          f"Diary entries: {len(cycle.diary_entries)}.",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning(f"Failed to report to orchestrator: {e}")


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    active = len([c for c in cycles.values() if c.status not in (CycleStatus.COMPLETE, CycleStatus.FAILED, CycleStatus.IDLE)])
    return {
        "status": "healthy",
        "service": "ralph",
        "active_cycles": active,
        "total_cycles": len(cycles),
    }


@app.post("/cycle/start")
async def start_cycle(req: StartCycleRequest):
    """Start a new autonomous coding cycle from a PRD."""
    log.info(f"Starting coding cycle for PRD: {req.title}")

    sections = parse_prd(req.prd)

    cycle = CodingCycle(
        prd_title=req.title,
        prd_sections=sections,
        status=CycleStatus.PLANNING,
        max_iterations=req.max_iterations,
        started_at=datetime.now(timezone.utc).isoformat(),
        requester=req.requester,
        workflow_id=req.workflow_id,
        subtask_id=req.subtask_id,
    )
    cycles[cycle.id] = cycle

    await diary_entry(cycle.id, f"Starting new coding cycle for PRD: {req.title}. {len(sections)} sections to implement.")
    await log_to_memory(f"Ralph cycle {cycle.id} started: {req.title}")

    # Generate the planning prompt
    planning_prompt = [
        f"# Ralph Coding Cycle: {req.title}",
        f"",
        f"## PRD Sections ({len(sections)}):",
        "",
    ]
    for i, sec in enumerate(sections, 1):
        planning_prompt.append(f"### {i}. {sec.title}")
        planning_prompt.append(sec.content[:500])
        planning_prompt.append("")

    planning_prompt.extend([
        "## Your Task:",
        "1. Analyze all PRD sections above",
        "2. Create a step-by-step implementation plan",
        "3. For each step, identify: files to create/modify, approach, potential risks",
        "4. Estimate complexity (1-10) for each step",
        "5. Order steps by dependency (what must be built first?)",
        "",
        "Output your plan as a structured numbered list.",
    ])

    return {
        "cycle_id": cycle.id,
        "status": cycle.status,
        "prd_title": req.title,
        "sections": len(sections),
        "planning_prompt": "\n".join(planning_prompt),
    }


@app.post("/cycle/iterate")
async def iterate_cycle(req: CycleIterationRequest):
    """
    Progress a coding cycle through its phases.
    
    The calling agent (typically beta-manager or a coding worker) drives the loop:
    1. Start → plan action (agent sends back the plan)
    2. Plan received → code action (agent writes code)
    3. Code written → test action (agent runs tests)
    4. Tests pass → validate action (agent reviews quality)
    5. Quality OK → reflect action (agent reflects)
    6. All done → complete action
    """
    cycle = cycles.get(req.cycle_id)
    if not cycle:
        raise HTTPException(404, f"Cycle {req.cycle_id} not found")

    cycle.current_iteration += 1
    if cycle.current_iteration > cycle.max_iterations:
        cycle.status = CycleStatus.FAILED
        cycle.error = f"Max iterations ({cycle.max_iterations}) exceeded"
        await diary_entry(cycle.id, f"FAILED: Max iterations exceeded after {cycle.current_iteration} steps.", success=False)
        await report_to_orchestrator(cycle)
        return {"cycle_id": cycle.id, "status": cycle.status, "error": cycle.error}

    if req.action == "plan":
        cycle.status = CycleStatus.PLANNING
        cycle.plan = req.content
        await diary_entry(cycle.id, f"Plan received (iteration {cycle.current_iteration}):\n{(req.content or '')[:500]}")
        next_prompt = (
            "Plan recorded. Now begin implementing. For each step:\n"
            "1. Write the code\n"
            "2. Report back with action='code' and the artifacts (file paths + content)\n"
            "3. Be thorough — include imports, error handling, and documentation.\n"
        )

    elif req.action == "code":
        cycle.status = CycleStatus.CODING
        if req.artifacts:
            cycle.code_artifacts.extend(req.artifacts)
        await diary_entry(cycle.id, f"Code written (iteration {cycle.current_iteration}): {len(req.artifacts or [])} artifacts.")
        next_prompt = (
            f"Code recorded ({len(cycle.code_artifacts)} total artifacts). "
            "Now test the implementation:\n"
            "1. Run any relevant tests\n"
            "2. Check for syntax errors\n"
            "3. Verify the code meets PRD requirements\n"
            "4. Report back with action='test' and results\n"
        )

    elif req.action == "test":
        cycle.status = CycleStatus.TESTING
        if req.content:
            cycle.test_results.append({"iteration": cycle.current_iteration, "result": req.content})
        await diary_entry(cycle.id, f"Tests run (iteration {cycle.current_iteration}): {(req.content or 'no output')[:300]}")
        next_prompt = (
            "Tests recorded. Now validate quality:\n"
            "1. Review code quality (readability, structure, patterns)\n"
            "2. Check PRD requirement coverage\n"
            "3. Assess confidence level (0.0 - 1.0)\n"
            "4. Report with action='validate' and confidence score\n"
            f"5. If confidence >= {MIN_CONFIDENCE}, proceed to reflection. Otherwise, iterate.\n"
        )

    elif req.action == "validate":
        cycle.status = CycleStatus.VALIDATING
        if req.confidence is not None:
            cycle.confidence = req.confidence
        if cycle.confidence >= MIN_CONFIDENCE:
            next_prompt = (
                f"Confidence: {cycle.confidence:.2f} (≥ {MIN_CONFIDENCE} threshold). Quality acceptable.\n"
                "Now reflect on the cycle:\n"
                "1. What went well?\n"
                "2. What was challenging?\n"
                "3. What would you do differently?\n"
                "4. What patterns did you discover?\n"
                "5. Report with action='reflect' and your reflection.\n"
            )
        else:
            next_prompt = (
                f"Confidence: {cycle.confidence:.2f} (< {MIN_CONFIDENCE} threshold). Needs improvement.\n"
                "Go back and improve:\n"
                "1. Identify weaknesses\n"
                "2. Write improved code (action='code')\n"
                "3. Re-test (action='test')\n"
                "4. Re-validate (action='validate')\n"
            )

    elif req.action == "reflect":
        cycle.status = CycleStatus.REFLECTING
        if req.content:
            cycle.reflections.append(req.content)
            await reflect(cycle.id, req.content)
        next_prompt = (
            "Reflection recorded. The cycle is ready to complete.\n"
            "Send action='complete' to finalize.\n"
        )

    elif req.action == "complete":
        cycle.status = CycleStatus.COMPLETE
        cycle.completed_at = datetime.now(timezone.utc).isoformat()
        await diary_entry(
            cycle.id,
            f"COMPLETED: {cycle.prd_title}\n"
            f"Iterations: {cycle.current_iteration}\n"
            f"Confidence: {cycle.confidence:.2f}\n"
            f"Artifacts: {len(cycle.code_artifacts)}\n"
            f"Tests: {len(cycle.test_results)}\n"
            f"Reflections: {len(cycle.reflections)}"
        )
        await log_to_memory(f"Ralph cycle {cycle.id} completed: {cycle.prd_title} with confidence {cycle.confidence:.2f}")
        await report_to_orchestrator(cycle)
        next_prompt = "Cycle complete. Results have been recorded and reported."

    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    return {
        "cycle_id": cycle.id,
        "status": cycle.status,
        "iteration": cycle.current_iteration,
        "confidence": cycle.confidence,
        "artifacts_count": len(cycle.code_artifacts),
        "next_prompt": next_prompt,
    }


@app.get("/cycle/{cycle_id}")
async def get_cycle(cycle_id: str):
    """Get full details of a coding cycle."""
    cycle = cycles.get(cycle_id)
    if not cycle:
        raise HTTPException(404, f"Cycle {cycle_id} not found")
    return cycle.model_dump()


@app.get("/cycles")
async def list_cycles(status: Optional[str] = None, limit: int = 20):
    """List all coding cycles."""
    items = list(cycles.values())
    if status:
        items = [c for c in items if c.status == status]
    items.sort(key=lambda c: c.started_at or "", reverse=True)
    return {
        "total": len(items),
        "cycles": [
            {
                "id": c.id,
                "prd_title": c.prd_title,
                "status": c.status,
                "iteration": c.current_iteration,
                "confidence": c.confidence,
                "started_at": c.started_at,
                "completed_at": c.completed_at,
            }
            for c in items[:limit]
        ],
    }


@app.on_event("startup")
async def startup():
    log.info(f"Ralph service starting on port {RALPH_PORT}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=RALPH_PORT, log_level="info")
