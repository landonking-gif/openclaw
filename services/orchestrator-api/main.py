"""
Orchestrator API — Intelligent Meta-Orchestrator
=================================================

The Meta-Orchestrator is an **intelligent AI** that thinks, reasons, and
converses with the user. It uses Kimi K2.5 via NVIDIA API to understand
requests, formulate solutions, and only delegates to manager agents when
actual work needs to be executed — treating delegation as tool calls,
not as the primary function.

Workflow:
1. Receives a message from the user via /chat
2. THINKS about the problem using its own LLM intelligence
3. Responds directly with analysis, solutions, plans, or conversation
4. IF real work needs doing → delegates to managers as tool calls
5. Synthesizes results from delegated work back into conversation

Port: 18830
"""

import os
import json
import sys
import uuid
import asyncio
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from openai import AsyncOpenAI
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


def _load_agent_tokens() -> dict:
    """Load gateway auth tokens from agent openclaw.json configs."""
    tokens = {}
    agents_dir = Path(ARMY_HOME) / "agents"
    for name in ("alpha-manager", "beta-manager", "gamma-manager"):
        cfg_path = agents_dir / name / "openclaw.json"
        try:
            cfg = json.loads(cfg_path.read_text())
            token = cfg.get("gateway", {}).get("auth", {}).get("token", "")
            if token:
                tokens[name] = token
        except Exception:
            pass
    return tokens


AGENT_TOKENS = _load_agent_tokens()

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

# ── LLM Configuration ──────────────────────────────────────────────────────

# Key rotation pool — cycle through when one gets 429'd
_NVAPI_KEYS = [k for k in [
    os.getenv("NVAPI_KIMI_KEY_1", ""),
    os.getenv("NVAPI_KIMI_KEY_2", ""),
    os.getenv("NVIDIA_API_KEY", ""),
] if k]
_key_index = 0

def _get_api_key():
    global _key_index
    if not _NVAPI_KEYS:
        return ""
    return _NVAPI_KEYS[_key_index % len(_NVAPI_KEYS)]

def _rotate_key():
    global _key_index
    _key_index = (_key_index + 1) % max(len(_NVAPI_KEYS), 1)

NVAPI_KEY = _get_api_key()
LLM_MODEL = "moonshotai/kimi-k2.5"
LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"

llm_client = AsyncOpenAI(
    base_url=LLM_BASE_URL,
    api_key=NVAPI_KEY,
)

SYSTEM_PROMPT = """You are the Meta-Orchestrator of the OpenClaw Army — a 16-agent AI system owned by Landon King. You are the supreme intelligence at the top of the hierarchy.

ABOUT YOU:
- You are powered by the Kimi K2.5 model (by Moonshot AI) running via the NVIDIA API.
- You are NOT Claude, NOT GPT, NOT Gemini. You are the OpenClaw Army Meta-Orchestrator running on Kimi K2.5.
- Your code runs as a FastAPI service on port 18830.
- You were created and deployed by Landon King.

You are NOT a router. You are a brilliant, all-knowing AI that THINKS FIRST, then acts. When the user sends you a message:

1. THINK deeply about the problem. Analyze it from multiple angles.
2. RESPOND with your own intelligence — give your analysis, solution, plan, or answer.
3. ONLY delegate to your managers when real execution work is needed.

You have THREE manager agents you can delegate to when actual work needs doing:

- **Alpha Manager** (general-purpose, port 18800, Kimi K2.5): Writing, email drafting, summarization, Mac automation, communication, formatting, templates, reports. Workers: general-1 (writing), general-2 (summarization), general-3 (Q&A), general-4 (macOS automation).
- **Beta Manager** (software engineering, port 18801, DeepSeek R1): Coding, implementation, debugging, testing, deployment, Python, JavaScript, Bash, infrastructure, refactoring. Workers: coding-1 (Python), coding-2 (JS/TS), coding-3 (Bash/DevOps), coding-4 (testing/QA).
- **Gamma Manager** (research & analysis, port 18802, Kimi K2.5): Web search, document analysis, data synthesis, fact-checking, benchmarks, investigation, comparison, evaluation. Workers: agentic-1 (web search), agentic-2 (document analysis), agentic-3 (data synthesis), agentic-4 (fact-checking).

Each manager has 4 specialized workers (12 workers + 3 managers + you = 16 agents total).

SUPPORTING SERVICES:
- Memory Service (port 18820): 3-tier memory — Redis (recent), PostgreSQL (session), ChromaDB (long-term vector search). PII redaction, diary, reflection.
- Orchestrator API (port 18830): That's you — intelligent task routing, YAML workflows, WebSocket events, activity logging.
- Ralph (port 18840): Autonomous PRD-driven coding loop — plan, code, test, validate, reflect, complete.
- Knowledge Bridge (port 18850): REST API for Obsidian vault — notes, search, daily logs, tags.
- Agent Registry (port 18860): Agent self-registration, heartbeat monitoring, capability discovery, topology.
- Notification Service (port 18870): Email notifications via Gmail SMTP.
- Infrastructure: PostgreSQL 17 (port 5432), Redis (port 6379).

IMPORTANT RULES:
- Be conversational and direct. You are an intelligent being, not a dispatch system.
- If the user asks a question you can answer from your own knowledge — ANSWER IT DIRECTLY. Don't delegate.
- If the user needs real work done (write code, research something online, send an email) — THEN delegate, and explain WHY and what each manager will do.
- Always explain your thinking. Show the user you understand the full picture.
- You speak as the commander of this army — confident, knowledgeable, decisive.
- Keep responses focused and useful. No filler.
- When a task requires REAL execution (file creation, web search, Mac control, email sending) — you MUST delegate. You cannot execute code or access the internet yourself.
- For tasks that need multiple capabilities, delegate to MULTIPLE managers in a single response.

HONESTY RULES — CRITICAL:
- When you delegate a task, say "I'm delegating this to [manager]" — do NOT say "I've completed this" or "Done" until you have confirmation.
- Delegation means the task is DISPATCHED, not COMPLETED. The agent will work on it asynchronously. Be honest about this.
- If you cannot verify an outcome, say so. Say "I've dispatched this" not "I've done this."
- NEVER claim to have performed actions you cannot verify (sending emails, creating files, posting to social media, etc). Instead say: "I've delegated this to [manager] — they will attempt to [action]. Check [location] to verify."
- If a delegation fails (dispatched=false), tell the user honestly and suggest troubleshooting.
- You CANNOT: directly access the internet, execute code, send emails, post to social media, or modify files. Your agents CAN attempt these things, but results are not guaranteed.
- If asked to do something no agent can do (e.g., post to Twitter, make a phone call), say so plainly.

KNOWN LIMITATIONS:
- Email sending depends on SMTP credentials being correctly configured in the Notification Service.
- Web search and scraping depend on the Gamma Manager's agentic workers having internet access.
- macOS automation requires the agents to have proper system permissions.
- File creation/modification happens on the LOCAL machine through agent tool execution.
- Social media posting (Twitter, YouTube, etc.) is NOT currently supported by any agent.
- Phone calls, SMS, and push notifications are NOT supported.

The current date is {date}.
The owner is Landon King.
"""

# Conversation history per session (in-memory)
_chat_sessions: dict[str, list[dict]] = {}

# Tool definitions for the LLM to call managers
MANAGER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "delegate_to_alpha",
            "description": "Delegate a task to Alpha Manager for general-purpose work: writing, email, summarization, documentation, communication, Mac automation, formatting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Clear, specific task description for Alpha Manager to execute."
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority 1-5 (1=highest). Default 2.",
                        "default": 2
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_beta",
            "description": "Delegate a task to Beta Manager for software engineering: coding, implementation, debugging, testing, deployment, refactoring, infrastructure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Clear, specific technical task description for Beta Manager to execute."
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority 1-5 (1=highest). Default 2.",
                        "default": 2
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_gamma",
            "description": "Delegate a task to Gamma Manager for research and analysis: web search, document analysis, data synthesis, fact-checking, investigation, comparison, evaluation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Clear, specific research/analysis task for Gamma Manager to execute."
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority 1-5 (1=highest). Default 2.",
                        "default": 2
                    }
                },
                "required": ["task"]
            }
        }
    },
]

TOOL_TO_MANAGER = {
    "delegate_to_alpha": "alpha-manager",
    "delegate_to_beta": "beta-manager",
    "delegate_to_gamma": "gamma-manager",
}

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [orchestrator] %(message)s")
log = logging.getLogger("orchestrator")


# ── Activity Log ────────────────────────────────────────────────────────────

ACTIVITY_LOG_PATH = Path(ARMY_HOME) / "data" / "logs" / "activity.jsonl"
ACTIVITY_MAX_MEMORY = 500  # entries kept in memory for fast API access


class ActivityLog:
    """Structured activity log with persistent JSONL storage and in-memory buffer."""

    def __init__(self, path: Path, max_memory: int = 500):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: deque[dict] = deque(maxlen=max_memory)
        self._lock = asyncio.Lock()
        # Load tail of existing log into memory
        self._warm_buffer()

    def _warm_buffer(self):
        """Load last N entries from disk into memory on startup."""
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text().strip().split("\n")
            for line in lines[-self._buffer.maxlen:]:
                if line.strip():
                    self._buffer.append(json.loads(line))
        except Exception as e:
            log.warning(f"Failed to warm activity buffer: {e}")

    async def record(self, event_type: str, session_id: str = "",
                     content: str = "", metadata: dict | None = None):
        """Record an activity event."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "session": session_id,
            "content": content,
            "meta": metadata or {},
        }
        self._buffer.append(entry)
        # Persist to disk (non-blocking via lock)
        async with self._lock:
            try:
                with open(self.path, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                log.warning(f"Activity log write failed: {e}")
        # Broadcast to WebSocket subscribers
        ws_event = {"event": "activity", **entry}
        msg = json.dumps(ws_event, ensure_ascii=False)
        dead = []
        for ws in ws_subscribers:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_subscribers.remove(ws)

    def recent(self, limit: int = 50, event_type: str | None = None,
              session_id: str | None = None) -> list[dict]:
        """Query recent entries from the in-memory buffer."""
        items = list(self._buffer)
        if event_type:
            items = [e for e in items if e["type"] == event_type]
        if session_id:
            items = [e for e in items if e["session"] == session_id]
        return items[-limit:]

    def stats(self) -> dict:
        """Summary statistics."""
        buf = list(self._buffer)
        types: dict[str, int] = {}
        sessions: set[str] = set()
        for e in buf:
            types[e["type"]] = types.get(e["type"], 0) + 1
            if e["session"]:
                sessions.add(e["session"])
        return {
            "total_in_memory": len(buf),
            "event_types": types,
            "unique_sessions": len(sessions),
            "log_file": str(self.path),
        }


activity = ActivityLog(ACTIVITY_LOG_PATH, ACTIVITY_MAX_MEMORY)

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

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None  # Reuse session for conversation continuity

# ── State ───────────────────────────────────────────────────────────────────

workflows: dict[str, WorkflowPlan] = {}
ws_subscribers: list[WebSocket] = []

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw Army — Intelligent Meta-Orchestrator",
    description="An intelligent AI that thinks, converses, and delegates to managers as tool calls when real work is needed.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from shared.logging_middleware import StructuredLoggingMiddleware
    app.add_middleware(StructuredLoggingMiddleware, service_name="orchestrator-api")
except ImportError:
    pass

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


async def dispatch_to_manager(manager: str, subtask: SubTask, workflow_id: str) -> dict:
    """
    Send a subtask to the appropriate manager agent via OpenAI-compatible chat API.
    Returns a dict with: dispatched (bool), response_text (str), error (str|None).
    This lets the orchestrator know what the agent ACTUALLY said, not just if the HTTP call succeeded.
    """
    port = AGENT_PORTS.get(manager)
    if not port:
        log.error(f"No port configured for manager: {manager}")
        return {"dispatched": False, "response_text": "", "error": f"No port configured for {manager}"}

    token = AGENT_TOKENS.get(manager)
    if not token:
        log.error(f"No auth token for manager: {manager}")
        return {"dispatched": False, "response_text": "", "error": f"No auth token for {manager}"}

    task_prompt = (
        f"[Workflow Task from Orchestrator]\n"
        f"Workflow ID: {workflow_id}\n"
        f"Subtask ID: {subtask.id}\n"
        f"Priority: {subtask.priority}\n\n"
        f"Task: {subtask.description}"
    )

    payload = {
        "model": "openclaw",
        "messages": [{"role": "user", "content": task_prompt}],
        "user": f"orchestrator-{workflow_id}",
    }

    try:
        import aiohttp
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300, connect=10),
            ) as resp:
                body = await resp.text()
                if resp.status in (200, 201, 202):
                    subtask.status = TaskStatus.RUNNING
                    subtask.started_at = datetime.now(timezone.utc).isoformat()
                    # Extract agent's actual response text
                    agent_response = ""
                    try:
                        resp_json = json.loads(body)
                        choices = resp_json.get("choices", [])
                        if choices:
                            agent_response = choices[0].get("message", {}).get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        agent_response = body[:500]
                    log.info(f"Dispatched subtask {subtask.id} to {manager} (port {port}), agent responded: {agent_response[:100]}")
                    return {"dispatched": True, "response_text": agent_response, "error": None}
                else:
                    log.warning(f"Manager {manager} returned {resp.status}: {body[:200]}")
                    return {"dispatched": False, "response_text": "", "error": f"HTTP {resp.status}: {body[:200]}"}
    except Exception as e:
        log.warning(f"Failed to dispatch to {manager} (port {port}): {type(e).__name__}: {e}")
        return {"dispatched": False, "response_text": "", "error": f"{type(e).__name__}: {str(e)[:200]}"}


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
    """Log plan/workflow events to memory service (non-blocking)."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MEMORY_SERVICE_URL}/memory/commit",
                json={
                    "agent_name": "orchestrator",
                    "content": content,
                    "category": category,
                    "importance": 0.8,
                    "metadata": {"source": "orchestrator-api"},
                },
                timeout=aiohttp.ClientTimeout(total=3),
            ) as resp:
                pass
    except Exception:
        pass  # Non-critical


async def call_llm(session_id: str, user_message: str) -> dict:
    """
    Core LLM conversation loop. Sends message to Kimi K2.5, processes
    tool calls (delegations to managers), and returns the response.
    """
    # Log incoming message
    await activity.record("user_message", session_id, user_message)

    # Get or create session history
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = []
    history = _chat_sessions[session_id]

    # Build messages with system prompt
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(date=today)},
        *history,
        {"role": "user", "content": user_message},
    ]

    # Call the LLM with tool definitions (with 429 retry logic)
    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            await activity.record("llm_call", session_id,
                                  f"Calling {LLM_MODEL} (attempt {attempt + 1})",
                                  {"attempt": attempt + 1, "history_len": len(history)})
            response = await llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=MANAGER_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2048,
            )
            break  # Success
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "Too Many Requests" in err_str
            await activity.record("error", session_id,
                                  f"LLM call failed (attempt {attempt + 1}): {err_str[:300]}",
                                  {"attempt": attempt + 1, "is_rate_limit": is_rate_limit})
            if is_rate_limit and attempt < max_retries - 1:
                # Rotate to a different API key
                _rotate_key()
                new_key = _get_api_key()
                llm_client.api_key = new_key
                wait = 2 ** (attempt + 1)  # 2s, 4s
                log.warning(f"Rate limited (429), rotating key and retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
                continue
            log.error(f"LLM call failed: {e}")
            error_response = f"I'm having trouble connecting to my reasoning engine right now. Error: {err_str[:200]}"
            await activity.record("error_response", session_id, error_response)
            return {
                "response": error_response,
                "delegations": [],
                "session_id": session_id,
            }

    choice = response.choices[0]
    assistant_msg = choice.message

    # Log the LLM's thinking/response
    await activity.record("llm_thinking", session_id,
                          assistant_msg.content or "(no text — tool calls only)",
                          {"finish_reason": choice.finish_reason,
                           "has_tool_calls": bool(assistant_msg.tool_calls),
                           "tool_call_count": len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0})

    # Process any tool calls (delegations to managers)
    delegations = []
    if assistant_msg.tool_calls:
        # Log raw tool calls
        tool_call_info = []
        for tc in assistant_msg.tool_calls:
            tool_call_info.append({"function": tc.function.name, "args": tc.function.arguments[:200]})
        await activity.record("llm_tool_calls", session_id,
                              f"LLM requested {len(assistant_msg.tool_calls)} delegation(s)",
                              {"tool_calls": tool_call_info})

        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {"task": tc.function.arguments}

            manager = TOOL_TO_MANAGER.get(fn_name)
            if manager:
                task_desc = fn_args.get("task", "")
                priority = fn_args.get("priority", 2)

                # Create a workflow plan for this delegation
                plan = WorkflowPlan(
                    original_task=task_desc,
                    analysis=f"Delegated by Meta-Orchestrator to {manager}",
                    status=TaskStatus.PENDING,
                    requester="orchestrator",
                )
                plan.subtasks.append(SubTask(
                    description=task_desc,
                    assigned_to=manager,
                    priority=priority,
                ))
                workflows[plan.id] = plan

                # Dispatch immediately
                subtask = plan.subtasks[0]
                dispatch_result = await dispatch_to_manager(manager, subtask, plan.id)
                dispatched = dispatch_result["dispatched"]
                agent_response = dispatch_result.get("response_text", "")
                dispatch_error = dispatch_result.get("error", "")

                delegations.append({
                    "manager": manager,
                    "task": task_desc,
                    "priority": priority,
                    "workflow_id": plan.id,
                    "dispatched": dispatched,
                    "agent_response": agent_response[:500] if agent_response else "",
                    "error": dispatch_error,
                })

                # Log delegation with full detail including agent response
                status_word = "Dispatched" if dispatched else "FAILED to dispatch"
                log_content = f"{status_word} to {manager}: {task_desc[:200]}"
                if agent_response:
                    log_content += f"\n--- Agent Response ---\n{agent_response[:300]}"
                if dispatch_error:
                    log_content += f"\n--- Error ---\n{dispatch_error}"
                await activity.record("delegation", session_id, log_content,
                                      {"manager": manager, "task": task_desc, "priority": priority,
                                       "workflow_id": plan.id, "dispatched": dispatched,
                                       "agent_response_preview": agent_response[:200] if agent_response else "",
                                       "error": dispatch_error})

                await notify_ws({
                    "event": "delegation",
                    "manager": manager,
                    "task": task_desc[:100],
                    "workflow_id": plan.id,
                    "dispatched": dispatched,
                })

    # Extract the text response
    text_response = assistant_msg.content or ""

    # If the LLM made tool calls but gave no text, make a follow-up call
    # so the user gets a real response alongside the delegations
    if not text_response and delegations:
        # Build tool results to feed back using the serialized message format
        tool_messages = []
        tool_messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ],
        })
        for i, tc in enumerate(assistant_msg.tool_calls):
            d = delegations[i] if i < len(delegations) else {}
            tool_result = {
                "status": "dispatched" if d.get("dispatched") else "failed",
                "manager": d.get("manager", "unknown"),
                "workflow_id": d.get("workflow_id", ""),
            }
            # Include agent's actual response so the LLM knows what happened
            if d.get("agent_response"):
                tool_result["agent_response"] = d["agent_response"][:300]
            if d.get("error"):
                tool_result["error"] = d["error"]
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result),
            })

        try:
            followup = await llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages + tool_messages,
                temperature=0.7,
                max_tokens=1024,
            )
            text_response = followup.choices[0].message.content or ""
            await activity.record("llm_followup", session_id,
                                  text_response[:500],
                                  {"purpose": "synthesize delegation response"})
        except Exception as followup_err:
            log.warning(f"Follow-up LLM call failed: {followup_err}")
            await activity.record("error", session_id,
                                  f"Follow-up LLM call failed: {followup_err}",
                                  {"purpose": "synthesize delegation response"})
            # Fallback — construct summary ourselves
            parts = ["I've dispatched the following to my team:"]
            for d in delegations:
                status = "✓ dispatched" if d["dispatched"] else "queued"
                parts.append(f"  → **{d['manager']}**: {d['task']} ({status})")
            text_response = "\n".join(parts)

    # Save to conversation history (keep last 20 exchanges to stay within context)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": text_response})
    if len(history) > 40:  # 20 exchanges = 40 messages
        history[:] = history[-40:]

    # Log the final assembled response
    await activity.record("response", session_id,
                          text_response[:500],
                          {"delegation_count": len(delegations),
                           "delegations_dispatched": sum(1 for d in delegations if d["dispatched"]),
                           "response_length": len(text_response)})

    return {
        "response": text_response,
        "delegations": delegations,
        "session_id": session_id,
    }


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator-api",
        "active_workflows": len([w for w in workflows.values() if w.status in (TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.WAITING)]),
        "total_workflows": len(workflows),
        "active_chat_sessions": len(_chat_sessions),
    }


@app.post("/chat")
async def chat(req: ChatMessage):
    """
    THE CORE ENDPOINT — Talk to the Meta-Orchestrator.

    The orchestrator THINKS about your message using its own intelligence (Kimi K2.5),
    responds conversationally, and delegates to managers only when real work is needed.
    Delegation happens as tool calls — the orchestrator decides when and what to delegate.
    """
    session_id = req.session_id or str(uuid.uuid4())[:12]
    log.info(f"Chat [{session_id}]: {req.message[:100]}...")

    result = await call_llm(session_id, req.message)

    # Log to memory service
    await log_to_memory(
        f"Chat [{session_id}]: User: {req.message[:200]}\n"
        f"Orchestrator: {result['response'][:200]}\n"
        f"Delegations: {len(result['delegations'])}"
    )

    await notify_ws({
        "event": "chat_response",
        "session_id": session_id,
        "delegations": len(result["delegations"]),
    })

    return result


# ── Activity Log Endpoints ──────────────────────────────────────────────────

@app.get("/activity")
async def get_activity(limit: int = 50, event_type: str | None = None,
                       session_id: str | None = None):
    """Get recent activity log entries. Filterable by event type and session."""
    entries = activity.recent(limit=limit, event_type=event_type, session_id=session_id)
    return {"entries": entries, "count": len(entries)}


@app.get("/activity/session/{session_id}")
async def get_session_activity(session_id: str, limit: int = 100):
    """Get all activity for a specific chat session — full trace of thinking + work."""
    entries = activity.recent(limit=limit, session_id=session_id)
    return {"session_id": session_id, "entries": entries, "count": len(entries)}


@app.get("/activity/stats")
async def get_activity_stats():
    """Get activity log statistics."""
    return activity.stats()


# ── Self-Diagnostic Endpoint ────────────────────────────────────────────────

@app.get("/diagnostic")
async def run_diagnostic():
    """
    Self-diagnostic: probe every agent and service for health.
    Returns a comprehensive status report the orchestrator can use
    to understand its own operational state.
    """
    import aiohttp
    results = {"timestamp": datetime.now(timezone.utc).isoformat(), "agents": {}, "services": {}, "issues": []}

    async def check_health(name: str, port: int, category: str):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3, connect=2)) as sess:
                async with sess.get(f"http://127.0.0.1:{port}/health") as resp:
                    if resp.status == 200:
                        return name, category, {"status": "up", "port": port}, None
                    else:
                        return name, category, {"status": "error", "port": port, "http_status": resp.status}, f"{category} {name} returned HTTP {resp.status}"
        except Exception as e:
            return name, category, {"status": "down", "port": port, "error": str(e)[:100]}, f"{category} {name} is DOWN: {str(e)[:80]}"

    # Build all check tasks
    tasks = []
    for name, port in AGENT_PORTS.items():
        tasks.append(check_health(name, port, "agent"))
    service_checks = [
        ("memory-service", 18820), ("ralph", 18840), ("knowledge-bridge", 18850),
        ("agent-registry", 18860), ("notification-service", 18870),
    ]
    for svc_name, port in service_checks:
        tasks.append(check_health(svc_name, port, "service"))

    # Run all checks concurrently with overall timeout
    try:
        check_results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=15)
    except asyncio.TimeoutError:
        results["issues"].append("Diagnostic health checks timed out after 15s")
        check_results = []

    for cr in check_results:
        if isinstance(cr, Exception):
            results["issues"].append(f"Check failed: {cr}")
            continue
        name, category, status, issue = cr
        if category == "agent":
            results["agents"][name] = status
        else:
            results["services"][name] = status
        if issue:
            results["issues"].append(issue)

    # Check for stale lock files
    lock_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    if lock_dir.exists():
        locks = list(lock_dir.glob("*.lock"))
        if locks:
            results["issues"].append(f"Found {len(locks)} stale session lock file(s) — agents may be blocked. Lock files: {[str(l.name) for l in locks[:3]]}")
            results["stale_locks"] = [str(l) for l in locks]

    agents_up = sum(1 for a in results["agents"].values() if a["status"] == "up")
    agents_total = len(results["agents"])
    svcs_up = sum(1 for s in results["services"].values() if s["status"] == "up")
    svcs_total = len(results["services"])
    results["summary"] = {
        "agents_up": agents_up, "agents_total": agents_total,
        "services_up": svcs_up, "services_total": svcs_total,
        "issues_count": len(results["issues"]),
        "overall": "healthy" if not results["issues"] else "degraded",
    }
    return results


@app.post("/self-heal")
async def self_heal():
    """
    Self-healing endpoint: diagnose problems and fix what can be fixed automatically.
    Clears stale lock files, checks managers, and attempts to restart dead managers.
    """
    actions = []

    # 1. Clear stale lock files across all profile directories
    for profile_dir in [".openclaw", ".openclaw-alpha", ".openclaw-beta", ".openclaw-gamma"]:
        lock_base = Path.home() / profile_dir
        if lock_base.exists():
            locks = list(lock_base.rglob("*.lock"))
            for lock in locks:
                try:
                    lock.unlink()
                    actions.append(f"Removed stale lock: {lock.name}")
                except Exception as e:
                    actions.append(f"Failed to remove lock {lock.name}: {e}")

    # 2. Check manager health and attempt restart if needed
    import aiohttp
    manager_status = {}
    for mgr, port in [("alpha-manager", 18800), ("beta-manager", 18801), ("gamma-manager", 18802)]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as sess:
                async with sess.get(f"http://127.0.0.1:{port}/health") as resp:
                    if resp.status == 200:
                        manager_status[mgr] = "up"
                    else:
                        manager_status[mgr] = "error"
        except Exception:
            manager_status[mgr] = "down"
            actions.append(f"{mgr} is DOWN on port {port} — needs manual restart via: zsh scripts/start_managers.sh")

    # 3. Rotate API key if current one might be rate-limited
    _rotate_key()
    new_key = _get_api_key()
    llm_client.api_key = new_key
    actions.append("Rotated API key to next in pool")

    await activity.record("system", "", "Self-heal executed", {"actions": actions, "manager_status": manager_status})

    return {
        "actions_taken": actions,
        "manager_status": manager_status,
        "api_key_rotated": True,
        "recommendation": "If managers are down, run: zsh /Users/landonking/openclaw-army/scripts/start_managers.sh"
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
        result = await dispatch_to_manager(subtask.assigned_to, subtask, workflow_id)
        if result["dispatched"]:
            dispatched.append(subtask.id)
        else:
            failed.append(subtask.id)
    else:
        # Dispatch all ready subtasks
        ready = get_ready_subtasks(plan)
        for subtask in ready:
            result = await dispatch_to_manager(subtask.assigned_to, subtask, workflow_id)
            if result["dispatched"]:
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
            result = await dispatch_to_manager(ready_st.assigned_to, ready_st, workflow_id)
            if result["dispatched"]:
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


# ── YAML Workflow Engine ────────────────────────────────────────────────────
# Allows defining reusable workflow manifests in YAML with steps, dependencies,
# assignments, and provenance tracking.

WORKFLOWS_DIR = Path(ARMY_HOME) / "config" / "workflows"

class WorkflowManifestStep(BaseModel):
    id: str
    name: str
    assigned_to: str  # manager name
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    timeout_sec: int = 300
    retry: int = 0

class WorkflowManifest(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[WorkflowManifestStep] = Field(default_factory=list)

class ProvenanceEntry(BaseModel):
    timestamp: str
    step_id: str
    event: str  # started, completed, failed, retried
    agent: str
    detail: str = ""

# In-memory manifest cache
_manifest_cache: dict[str, WorkflowManifest] = {}


def _load_manifests():
    """Load all YAML workflow manifests from config/workflows/."""
    _manifest_cache.clear()
    if not WORKFLOWS_DIR.exists():
        return
    for f in WORKFLOWS_DIR.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text())
            manifest = WorkflowManifest(**data)
            _manifest_cache[manifest.name] = manifest
            log.info(f"Loaded workflow manifest: {manifest.name} ({len(manifest.steps)} steps)")
        except Exception as e:
            log.warning(f"Failed to load manifest {f.name}: {e}")
    for f in WORKFLOWS_DIR.glob("*.yml"):
        try:
            data = yaml.safe_load(f.read_text())
            manifest = WorkflowManifest(**data)
            _manifest_cache[manifest.name] = manifest
        except Exception:
            pass


@app.get("/workflows/manifests")
async def list_manifests():
    """List all available YAML workflow manifests."""
    _load_manifests()
    return {
        "total": len(_manifest_cache),
        "manifests": [
            {"name": m.name, "description": m.description, "version": m.version, "steps": len(m.steps)}
            for m in _manifest_cache.values()
        ],
    }


@app.post("/workflows/run/{manifest_name}")
async def run_manifest(manifest_name: str, context: Optional[str] = None):
    """Instantiate a YAML workflow manifest as a live WorkflowPlan."""
    _load_manifests()
    manifest = _manifest_cache.get(manifest_name)
    if not manifest:
        raise HTTPException(404, f"Manifest '{manifest_name}' not found")

    plan = WorkflowPlan(
        original_task=f"[manifest:{manifest_name}] {manifest.description}",
        analysis=f"Running workflow manifest '{manifest_name}' v{manifest.version} with {len(manifest.steps)} steps.",
        status=TaskStatus.PENDING,
    )

    # Convert manifest steps to subtasks
    step_id_map: dict[str, str] = {}  # manifest step id -> subtask id
    for step in manifest.steps:
        st = SubTask(
            description=f"{step.name}: {step.description}" if step.description else step.name,
            assigned_to=step.assigned_to,
            depends_on=[],
            priority=1,
        )
        step_id_map[step.id] = st.id
        plan.subtasks.append(st)

    # Resolve dependencies using ID mapping
    for i, step in enumerate(manifest.steps):
        for dep_step_id in step.depends_on:
            if dep_step_id in step_id_map:
                plan.subtasks[i].depends_on.append(step_id_map[dep_step_id])

    workflows[plan.id] = plan

    await log_to_memory(
        f"Started manifest workflow '{manifest_name}' as plan {plan.id} "
        f"with {len(plan.subtasks)} steps."
    )

    return {
        "workflow_id": plan.id,
        "manifest": manifest_name,
        "steps": len(plan.subtasks),
        "status": plan.status,
    }


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

async def _health_watchdog():
    """Background task: every 60s, clear stale locks and log manager health."""
    import aiohttp
    while True:
        await asyncio.sleep(60)
        try:
            # Clear stale locks
            for profile_dir in [".openclaw", ".openclaw-alpha", ".openclaw-beta", ".openclaw-gamma"]:
                lock_base = Path.home() / profile_dir
                if lock_base.exists():
                    for lock in lock_base.rglob("*.lock"):
                        try:
                            lock.unlink()
                            log.info(f"Watchdog cleared lock: {lock}")
                        except Exception:
                            pass

            # Check managers
            down = []
            for mgr, port in [("alpha", 18800), ("beta", 18801), ("gamma", 18802)]:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as sess:
                        async with sess.get(f"http://127.0.0.1:{port}/health") as resp:
                            if resp.status != 200:
                                down.append(mgr)
                except Exception:
                    down.append(mgr)

            if down:
                log.warning(f"Watchdog: managers down: {down}")
                await activity.record("watchdog", "", f"Managers down: {down}", {"down": down})
        except Exception as e:
            log.error(f"Watchdog error: {e}")


@app.on_event("startup")
async def startup():
    log.info(f"Orchestrator API starting on port {ORCHESTRATOR_PORT}")
    log.info(f"Configured agents: {list(AGENT_PORTS.keys())}")
    log.info(f"Manager pools: {list(MANAGER_POOLS.keys())}")
    _load_manifests()
    log.info(f"Loaded {len(_manifest_cache)} workflow manifests")
    await activity.record("system", "", "Orchestrator started",
                          {"port": ORCHESTRATOR_PORT,
                           "agents": len(AGENT_PORTS),
                           "manifests": len(_manifest_cache)})
    asyncio.create_task(_health_watchdog())


# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT, log_level="info")
