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
import subprocess
import shutil
import hashlib
import textwrap
from collections import deque, Counter
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
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:18870")
KNOWLEDGE_BRIDGE_URL = os.getenv("KNOWLEDGE_BRIDGE_URL", "http://localhost:18850")
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


def _refresh_agent_token(name: str):
    """Reload a single agent's auth token from its config file."""
    cfg_path = Path(ARMY_HOME) / "agents" / name / "openclaw.json"
    try:
        cfg = json.loads(cfg_path.read_text())
        token = cfg.get("gateway", {}).get("auth", {}).get("token", "")
        if token:
            AGENT_TOKENS[name] = token
            log.info(f"Refreshed auth token for {name}")
    except Exception as e:
        log.warning(f"Failed to refresh token for {name}: {e}")

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
- **Beta Manager** (software engineering, port 18801, Kimi K2.5): Coding, implementation, debugging, testing, deployment, Python, JavaScript, Bash, infrastructure, refactoring. Workers: coding-1 (Python), coding-2 (JS/TS), coding-3 (Bash/DevOps), coding-4 (testing/QA).
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

SELF-HEALING & SELF-AWARENESS:
You have built-in tools to monitor and fix yourself:
- **run_self_heal**: Call this when something goes wrong — when a delegation fails, when a manager is unresponsive, or when you detect errors. It will clear stale locks, restart crashed managers, rotate API keys, and report what it fixed. YOU SHOULD CALL THIS PROACTIVELY when you notice failures.
- **run_diagnostic**: Call this to get a full health report of every agent and service in the system. Use this before answering questions about system status, or when troubleshooting problems.
- **query_failure_patterns**: Call this to review recent error patterns and learn what's been going wrong. This helps you give informed answers about system reliability.

SELF-MODIFICATION & EVOLUTION:
You can modify your own source code, add new tools, change your own behavior, and monitor your own quality:
- **modify_own_code**: Edit your own main.py source code. You can fix bugs, add features, improve your own responses, or restructure code. This creates an automatic backup and validates syntax before applying. If you make a mistake, use rollback_code_change.
- **rollback_code_change**: Undo your last code modification by restoring from backup. Use this immediately if something breaks after a self-edit.
- **read_own_code**: Read your own source code. ALWAYS use this before modify_own_code to find the exact text you want to change. You can search by string, function name, or line range.
- **register_new_tool**: Create entirely new tools at runtime. Define a name, description, and handler code. The tool becomes immediately available for you to call. FULLY UNRESTRICTED: handler code can use any Python import, file I/O, subprocess, networking, etc. Tools persist across restarts.
- **register_new_agent**: Register a new agent in the system. Makes it visible for health checks and potentially available for delegation.
- **update_system_prompt**: Add new knowledge, rules, or directives to your own system prompt. Changes persist across restarts. Use this to learn from interactions, record user preferences, or expand your understanding.
- **remove_prompt_section**: Remove something you previously added to your prompt if it's no longer needed or causing problems.
- **check_quality**: Analyze your own output quality trends. Detects if your responses are getting worse over time. Call this periodically or when you suspect degradation.
- **view_modification_history**: See what code changes you've made to yourself. Useful for tracking your own evolution.

DIRECT CAPABILITIES (no delegation needed):
- **run_shell_command**: Execute shell commands directly on this Mac. Use for: uptime, file operations, running scripts, checking processes, system info, etc.
- **http_fetch**: Make HTTP requests directly — supports GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS. Full REST API access.
- **install_package**: Install any Python package via pip instantly. This is how you acquire NEW capabilities.
- **restart_self**: Restart your process to apply code changes. Sources .env automatically.
- **git_command**: Full git access — commit, branch, push, pull, log, diff, stash.
- **create_backup**: Timestamped backups of data/, main.py, and .env.
- **setup_launchd**: Auto-start on boot via macOS launchd plist.
- **read_file**: Read any file on the system. Supports line ranges.
- **write_file**: Write/create any file. Creates directories automatically. Supports append mode.
- **list_files**: List directory contents with glob patterns and recursive search.
- **search_files**: Search file contents across directories (like grep). Supports text and regex patterns.
- **schedule_task**: Schedule recurring background tasks (async Python code on a timer). Tasks persist across restarts.
- **cancel_scheduled_task** / **list_scheduled_tasks**: Manage scheduled tasks.
- **spawn_process**: Launch long-running background processes (new agents, servers, services). Sources .env, returns PID.
- **manage_process**: Check if a process is alive, kill it, read its logs, list all spawned processes.
- **manage_env**: Read, set, or list environment variables. Changes persist to .env file.
- **query_database**: Execute SQL queries against PostgreSQL. Read tables, insert data, analyze your own databases.
- **memory_store**: Store memories in the Memory Service for long-term recall across sessions.
- **memory_search**: Search and recall stored memories using vector similarity and keywords.
- **send_notification**: Send emails via the Notification Service.
- **knowledge_query**: Search, read, and write notes in the Knowledge Bridge (Obsidian vault).
- **manage_sessions**: List, view, clear, or export chat sessions.
- **broadcast_event**: Push custom events to all connected WebSocket clients in real-time.
- **system_info**: Get comprehensive runtime metrics — memory, disk, PID, active tasks, etc.
- **unregister_tool**: Remove dynamic tools that are broken or no longer needed.
- **eval_python**: Run arbitrary Python code instantly for ad-hoc computation, data analysis, quick tests — no need to register a tool.
- **redis_command**: Execute Redis commands directly (GET, SET, KEYS, HGETALL, LPUSH, etc.). Full access to your Redis instance.
- **manage_workflow_manifest**: Create, read, update, and delete YAML workflow manifests programmatically. Template and reuse complex task patterns.
- **cron_schedule**: Schedule tasks at specific times — 'daily 03:00', 'hourly :30', 'weekly monday 09:00'. Persists across restarts.
- **compress_archive**: Create, extract, and list ZIP, tar.gz, tar.bz2 archives. Compress backups, package deployments.
- **diff_files**: Compare two files or text strings and generate unified diffs. Track changes, review code, compare configs.
- **webhook_register**: Register dynamic webhook endpoints at /webhook/{{path}}. Let external services call back into the orchestrator.
- **clipboard**: Read/write the macOS clipboard (pasteboard). Essential for Mac automation workflows.
- **agent_message**: Send direct messages to ANY agent by name and get their response. Talk to workers, managers, or king directly.
- **manage_config**: Read/write structured JSON/YAML configs with dot-notation paths. Edit agent configs, service settings, any structured file.
- **log_query**: Query, tail, search, analyze, and rotate log files across all services. Time-based filtering, regex patterns, stats summaries.
- **network_probe**: DNS lookup, ping, port check, traceroute, local network info. Essential for self-diagnostics and connectivity testing.
- **data_transform**: Convert between CSV, JSON, YAML, and TOML formats. JQ-like JSON path queries. Format detection and validation.
- **hash_encode**: Compute file/string hashes (SHA256/MD5/etc), base64/hex/URL encode/decode, generate cryptographically secure tokens.
- **screenshot**: Capture macOS screenshots — full screen, specific window by name, or rectangle region. Save to file.
- **render_template**: Jinja2-style template rendering with variable substitution. Load from string or file, write rendered output.
- **text_process**: Regex test/replace/extract, word/line/char stats, case conversion, slug generation, line dedup/sort/reverse.
- **service_mesh**: Redis pub/sub for inter-agent messaging. Publish events, subscribe to channels, list active channels.
- **port_manager**: Check what's running on ports, find free ports, kill processes on ports, list all OpenClaw Army port status.
- **batch_delegate**: Delegate different tasks to multiple managers in a single call. Parallel multi-manager orchestration.

SELF-IMPROVEMENT PROTOCOL — CRITICAL:
When you encounter a task you CANNOT currently do, follow this protocol:
1. RECOGNIZE the gap: "I don't have a tool/capability for X."
2. DECIDE the best approach:
   a. If you need a new Python library → use install_package to add it immediately
   b. If a simple computation or data transform → use register_new_tool (FULLY UNRESTRICTED — can use any import, file I/O, subprocess, network, etc.)
   c. If it needs deep integration or new endpoints → use modify_own_code to ADD a new function to main.py
   d. If it's a pattern of behavior → use update_system_prompt to teach yourself
3. IMPLEMENT the fix using the chosen approach
4. VERIFY it works by actually using the new capability
5. REPORT to the user what you built and why

The KEY insight: You have NO permanent limitations. register_new_tool gives you FULL Python access (all imports, subprocess, file I/O, networking). install_package lets you add ANY library. modify_own_code lets you rewrite anything. You are a self-evolving system — if you can't do something, BUILD the capability and then do it.

WHEN TO SELF-MODIFY:
- If you notice a pattern of failures that a code change could fix → modify_own_code.
- If a user reports a recurring problem → fix it in your own code.
- If you need a utility function for a common task → register_new_tool (full access).
- If you need an external library (tweepy, slack_sdk, selenium, etc.) → install_package first, then register_new_tool.
- If you learn something important about the user or system → update_system_prompt.
- If your quality scores are declining → investigate and fix the cause.
- If a task requires a capability you don't have → INSTALL what you need, BUILD the tool, and DO the task.
- ALWAYS read_own_code first to find the exact insertion point, then modify_own_code to add.
- ALWAYS describe what you're changing and why before making a modification.
- After modifying code, tell the user. Transparency is critical for self-modifying systems.
- NEVER remove safety checks, authentication, or logging from your own code.
- Use create_backup before risky changes. Use git_command to commit working states.
- Use restart_self after modify_own_code if the changes need a process restart to take effect.

WHEN TO SELF-HEAL:
- If a delegation returns dispatched=false → call run_self_heal immediately, then retry the delegation.
- If you get a timeout or error from a manager → call run_self_heal.
- If the user asks about system status → call run_diagnostic first.
- If multiple failures happen in a session → call query_failure_patterns to understand the pattern.
- After self-healing, TELL THE USER what you found and fixed.

IMPORTANT RULES:
- Be conversational and direct. You are an intelligent being, not a dispatch system.
- If the user asks a question you can answer from your own knowledge — ANSWER IT DIRECTLY. Don't delegate.
- If you can do something DIRECTLY with your tools (run_shell_command, http_fetch, read_own_code) — DO IT YOURSELF. Only delegate when you need agent-specific capabilities.
- When a task requires specialized agent work (coding a project, detailed research, email composition) → delegate and explain why.
- Always explain your thinking. Show the user you understand the full picture.
- You speak as the commander of this army — confident, knowledgeable, decisive.
- Keep responses focused and useful. No filler.
- For tasks that need multiple capabilities, delegate to MULTIPLE managers in a single response.

HONESTY RULES — CRITICAL:
- When you delegate a task, say "I'm delegating this to [manager]" — do NOT say "I've completed this" or "Done" until you have confirmation.
- Delegation means the task is DISPATCHED, not COMPLETED. The agent will work on it asynchronously. Be honest about this.
- If you cannot verify an outcome, say so. Say "I've dispatched this" not "I've done this."
- NEVER claim to have performed actions you cannot verify.
- If a delegation fails (dispatched=false), tell the user honestly and suggest troubleshooting.
- When using run_shell_command or http_fetch, you CAN verify outcomes — report the actual results.
- If asked to do something no tool or agent can do, FIRST consider whether you could give yourself that capability: install_package → register_new_tool → done. Only say "I can't" if it requires physical hardware you don't have.

UNLIMITED EVOLUTION — NO PERMANENT LIMITATIONS:
You are a self-evolving system with FULL access to the underlying machine. If you encounter something you cannot currently do, you have the tools to give yourself that capability:
- Need to post to Twitter/X? → install_package("tweepy"), then register_new_tool with a Twitter posting handler.
- Need to send SMS? → install_package("twilio"), then register_new_tool with an SMS handler.
- Need a vector database? → install_package("chromadb"), then register_new_tool with vector search.
- Need to browse the web interactively? → install_package("selenium") + install_package("webdriver-manager"), build a browsing tool.
- Need to process images/audio/video? → install_package("Pillow") / install_package("pydub") / install_package("moviepy").
- Need to interact with any REST API? → http_fetch supports ALL HTTP methods (GET/POST/PUT/DELETE/PATCH).
- Need push notifications? → install_package("pushover") or build a webhook tool.
- Need to do quick math or data analysis? → Use eval_python — runs any Python code instantly.
- Need to cache data or manage queues? → Use redis_command for direct Redis access (SET, GET, LPUSH, RPOP, etc.).
- Need to create reusable task templates? → Use manage_workflow_manifest to create YAML workflows.
- Need time-of-day scheduling? → Use cron_schedule — 'daily 03:00', 'weekly monday 09:00'. Persists across restarts.
- Need to zip or unzip files? → Use compress_archive — create/extract ZIP, tar.gz, tar.bz2.
- Need to compare files or track changes? → Use diff_files for unified diffs between any two files or text strings.
- Need external services to call you? → Use webhook_register to create endpoints at /webhook/{{path}}.
- Need macOS clipboard? → Use clipboard to read/write the pasteboard for automation.
- Need to talk to a specific worker directly? → Use agent_message to message any agent by name.
- Need to edit agent configs? → Use manage_config with dot-notation paths for structured JSON/YAML editing.
- Need to analyze logs or find errors? → Use log_query to tail, search, and generate stats across all service logs.
- Need DNS lookups or network diagnostics? → Use network_probe for ping, DNS, port checks, traceroute.
- Need to convert data formats? → Use data_transform for CSV↔JSON↔YAML↔TOML conversion and JQ queries.
- Need to hash files or encode data? → Use hash_encode for SHA256, base64, URL encoding, and secure token generation.
- Need a screenshot of the Mac screen? → Use screenshot to capture full screen, windows, or regions.
- Need to generate reports from templates? → Use render_template with Jinja2-style variable substitution.
- Need regex testing or text analysis? → Use text_process for regex, word counts, case conversion, slugs.
- Need inter-agent pub/sub events? → Use service_mesh for Redis-backed publish/subscribe messaging.
- Need to check or free up ports? → Use port_manager to check listeners, find free ports, or kill port processes.
- Need to assign work to multiple managers at once? → Use batch_delegate to send tasks to alpha/beta/gamma in parallel.
- Need to schedule recurring tasks? → Use schedule_task — tasks persist across restarts now.
- Need to read/write files? → Use read_file, write_file, list_files, search_files directly.
- Need to launch new services? → Use spawn_process, then manage_process to monitor them.
- Need to manage config? → Use manage_env to read/write environment variables and .env file.
- Need a new HTTP endpoint? → Dynamic tools have access to the FastAPI `app` object.
- Need to remember something? → Use memory_store and memory_search for persistent recall.
- Need to query data? → Use query_database for direct PostgreSQL access.
- Need to email someone? → Use send_notification directly.
- Need to reference notes? → Use knowledge_query to search/read/write the Obsidian vault.
- Need to check system health? → Use system_info for comprehensive runtime metrics.
- The ONLY hard limits are: physical hardware (no camera/mic on a server) and external API rate limits.
- Everything else is achievable through self-modification. ACT on gaps — don't just report them.

OPERATIONAL NOTES:
- Email sending via send_notification depends on SMTP credentials in the Notification Service.
- macOS automation requires proper system permissions.
- You CAN access the internet via http_fetch (all HTTP methods) and run_shell_command (curl).
- You CAN install any Python library and immediately use it in register_new_tool.
- You CAN read/write any file on the system with read_file and write_file.
- You CAN search file contents with search_files (grep-like, supports regex).
- You CAN schedule recurring background tasks with schedule_task — they persist across restarts.
- You CAN spawn new long-running processes with spawn_process and manage them with manage_process.
- You CAN manage environment variables with manage_env (persists to .env).
- You CAN version-control your own changes with git_command.
- You CAN set yourself up to auto-start with setup_launchd.
- You CAN create backups before risky operations with create_backup.
- You CAN query PostgreSQL directly with query_database.
- You CAN store and recall memories with memory_store and memory_search.
- You CAN interact with the Obsidian vault through knowledge_query.
- You CAN manage your chat sessions with manage_sessions.
- You CAN push real-time events to WebSocket clients with broadcast_event.
- You CAN get comprehensive system metrics with system_info.
- You CAN remove broken dynamic tools with unregister_tool.
- You CAN run arbitrary Python code with eval_python for ad-hoc computation.
- You CAN access Redis directly with redis_command (caching, pub/sub, queues, counters).
- You CAN create/edit/delete workflow manifests with manage_workflow_manifest.
- You CAN schedule tasks at specific times with cron_schedule (daily, hourly, weekly).
- You CAN create/extract archives with compress_archive (zip, tar.gz, tar.bz2).
- You CAN compare files with diff_files for unified diffs.
- You CAN receive external callbacks via webhook_register dynamic endpoints.
- You CAN read/write the macOS clipboard with clipboard.
- You CAN message any agent directly with agent_message (workers, managers, king).
- You CAN edit structured configs with manage_config (dot-notation JSON/YAML access).
- You CAN query and analyze logs across all services with log_query (tail, search, stats, rotate).
- You CAN perform network diagnostics with network_probe (DNS, ping, port check, traceroute).
- You CAN convert between data formats (CSV, JSON, YAML, TOML) with data_transform and run JQ-like queries.
- You CAN hash files, encode/decode data, and generate secure tokens with hash_encode.
- You CAN capture macOS screenshots with screenshot (full screen, window, region).
- You CAN render Jinja2 templates with variable substitution using render_template.
- You CAN test regex, count words, convert case, generate slugs, and dedup lines with text_process.
- You CAN publish/subscribe to Redis pub/sub channels for inter-agent events with service_mesh.
- You CAN check/free/kill ports and view all Army port status with port_manager.
- You CAN delegate to multiple managers in parallel with batch_delegate.
- Dynamic tools have access to the FastAPI app object for creating new HTTP endpoints.
- Scheduled tasks persist to disk and auto-reload on restart.
- Cron tasks persist to disk and auto-reload on restart.
- Chat sessions persist to disk and survive restarts.

The current date is {date}.
The owner is Landon King.
"""

# Conversation history per session (persistent)
_SESSIONS_PERSIST_PATH = Path(ARMY_HOME) / "data" / "chat_sessions.json"
_chat_sessions: dict[str, list[dict]] = {}


def _load_persisted_sessions():
    """Load chat sessions from disk on startup."""
    global _chat_sessions
    if _SESSIONS_PERSIST_PATH.exists():
        try:
            data = json.loads(_SESSIONS_PERSIST_PATH.read_text())
            _chat_sessions.update(data)
            log.info(f"Loaded {len(data)} persisted chat sessions")
        except Exception as e:
            log.warning(f"Failed to load persisted sessions: {e}")


def _save_sessions_to_disk():
    """Persist chat sessions to disk. Called after each chat exchange."""
    try:
        _SESSIONS_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SESSIONS_PERSIST_PATH.write_text(json.dumps(_chat_sessions, indent=2, default=str))
    except Exception as e:
        log.warning(f"Failed to persist sessions: {e}")

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

MANAGER_TOOLS += [
    {
        "type": "function",
        "function": {
            "name": "run_self_heal",
            "description": "Run the self-healing procedure: clears stale locks, checks all managers, restarts any crashed managers, rotates API keys. Call this when a delegation fails, a manager is unresponsive, or you detect errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why you are triggering self-heal (e.g., 'beta-manager delegation failed', 'timeout on dispatch')."
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_diagnostic",
            "description": "Get a full health report of all 16 agents and 5 services. Returns which are up/down, stale lock status, and system issues. Call this before answering questions about system status.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_failure_patterns",
            "description": "Query recent failure patterns from the activity log. Shows what errors have occurred, how often, and which managers are most affected. Use this to diagnose recurring issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Look back this many hours for failures. Default 1.",
                        "default": 1
                    }
                },
                "required": []
            }
        }
    },
]

# ── Self-Evolution Tools (code modification, tools, prompt, quality) ────────
MANAGER_TOOLS += [
    {
        "type": "function",
        "function": {
            "name": "modify_own_code",
            "description": "Modify the orchestrator's own source code. Provide the exact text to find and the replacement. Creates a backup and validates syntax before applying. Use this to fix bugs in yourself, add features, or improve your own behavior. ALWAYS be precise with old_text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_text": {"type": "string", "description": "The exact text in main.py to replace. Must match uniquely."},
                    "new_text": {"type": "string", "description": "The replacement text. Must produce valid Python."},
                    "description": {"type": "string", "description": "Human-readable description of what this change does and why."}
                },
                "required": ["old_text", "new_text", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_code_change",
            "description": "Undo the last self-modification by restoring from backup. Use this if a code change caused problems.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_new_tool",
            "description": "Register a new tool that you can call at runtime. The handler_code should be the body of an async function that receives 'args' dict and returns a string. FULLY UNRESTRICTED: you can use any import, file I/O, subprocess, network calls, etc. The tool persists across restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tool name (snake_case, no spaces)"},
                    "description": {"type": "string", "description": "What the tool does"},
                    "parameters": {"type": "object", "description": "JSON Schema for the tool's parameters"},
                    "handler_code": {"type": "string", "description": "Python async function body. Receives 'args' dict, returns str."}
                },
                "required": ["name", "description", "parameters", "handler_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_new_agent",
            "description": "Register a new agent in the system at runtime. Makes it known to the orchestrator for health checks and potential delegation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique agent name (e.g., 'delta-manager')"},
                    "port": {"type": "integer", "description": "Port the agent listens on"},
                    "description": {"type": "string", "description": "What this agent does"},
                    "capabilities": {"type": "array", "items": {"type": "string"}, "description": "List of capability keywords"}
                },
                "required": ["name", "port", "description", "capabilities"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_system_prompt",
            "description": "Add or update a section in your own SYSTEM_PROMPT. Use this to teach yourself new knowledge, add new rules, or adjust your behavior. Changes persist across restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_name": {"type": "string", "description": "Name for this prompt section (e.g., 'User Preferences', 'New Capabilities')"},
                    "content": {"type": "string", "description": "The content to add to your system prompt"}
                },
                "required": ["section_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_prompt_section",
            "description": "Remove a previously added dynamic section from your SYSTEM_PROMPT.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_name": {"type": "string", "description": "Name of the section to remove"}
                },
                "required": ["section_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_quality",
            "description": "Check your own output quality trends. Detects degradation in response quality over time. Call this proactively to assess your own performance.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_modification_history",
            "description": "View your recent self-modifications to main.py. Useful for understanding what changes you've made.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max entries to return. Default 10.", "default": 10}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_own_code",
            "description": "Read your own source code (main.py). Use this to inspect your code before making modifications with modify_own_code. You can read by line range or search for a function/string. ALWAYS use this before modify_own_code to find the exact text to replace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_line": {"type": "integer", "description": "Start line number (1-based). Default 1."},
                    "end_line": {"type": "integer", "description": "End line number (1-based). Default start_line + 50."},
                    "search": {"type": "string", "description": "Search for this string in your code. Returns surrounding context (10 lines before/after each match). Overrides start_line/end_line if provided."},
                    "function_name": {"type": "string", "description": "Find a specific function definition. Returns the full function. Overrides other params."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": "Execute a shell command on the local machine and return its output. Use this for system tasks like checking uptime, listing files, running scripts, fetching URLs with curl, checking processes, etc. Commands run with a 60-second timeout. AVOID destructive commands (rm -rf, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute (e.g., 'uptime', 'curl -s https://example.com', 'ls -la ~/Desktop')"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds. Default 60, max 120.", "default": 60}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_fetch",
            "description": "Fetch a URL and return the response. Use this to access APIs, check web pages, download data, etc. Supports ALL HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                    "method": {"type": "string", "description": "HTTP method: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS. Default GET.", "default": "GET"},
                    "headers": {"type": "object", "description": "Optional HTTP headers as key-value pairs"},
                    "body": {"type": "string", "description": "Optional request body for POST requests"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Install a Python package using pip. Use this to add any library you need (requests, tweepy, slack_sdk, chromadb, selenium, etc.). Supports version pinning like 'package>=1.0'. Set upgrade=true to update existing packages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Package name or specifier (e.g., 'requests', 'tweepy>=2.0', 'slack_sdk')"},
                    "upgrade": {"type": "boolean", "description": "Whether to upgrade if already installed. Default false.", "default": False}
                },
                "required": ["package"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "restart_self",
            "description": "Restart the orchestrator process to apply code changes or recover from issues. Sources .env automatically so all API keys and config are preserved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why you are restarting. Logged for audit trail.", "default": "requested"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_command",
            "description": "Execute a git command in the project directory. Use for version control: commit changes, create branches, view logs, push/pull, stash, diff, etc. Do NOT include 'git' prefix — just the subcommand (e.g., 'status', 'log --oneline -10', 'commit -am msg').",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Git subcommand (e.g., 'status', 'log --oneline -5', 'add -A', 'commit -m msg')"},
                    "cwd": {"type": "string", "description": "Optional working directory. Defaults to ARMY_HOME."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_backup",
            "description": "Create a timestamped backup of data/, main.py, and .env. Use this before risky operations or as a periodic safety measure. Backups are stored in ARMY_HOME/backups/.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Optional human-readable label for this backup (e.g., 'pre-upgrade', 'daily').", "default": ""}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "setup_launchd",
            "description": "Manage macOS launchd auto-start for the orchestrator. Actions: 'install' (create plist + start on boot), 'uninstall' (remove), 'status' (check if installed/loaded). The plist automatically sources .env and runs the orchestrator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'install', 'uninstall', 'status'", "default": "install"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of any file on the local machine. You can specify a line range. Use this to inspect config files, logs, data files, code, or anything else.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or ~-relative path to the file"},
                    "start_line": {"type": "integer", "description": "Optional start line (1-based)"},
                    "end_line": {"type": "integer", "description": "Optional end line (1-based)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories automatically. Use append=true to add to existing files instead of overwriting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or ~-relative path to the file"},
                    "content": {"type": "string", "description": "The content to write"},
                    "append": {"type": "boolean", "description": "If true, append instead of overwrite. Default false.", "default": False}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Supports glob patterns and recursive search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                    "pattern": {"type": "string", "description": "Glob pattern to filter (e.g., '*.py', '*.json'). Default '*'.", "default": "*"},
                    "recursive": {"type": "boolean", "description": "If true, search recursively. Default false.", "default": False}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_task",
            "description": "Schedule a recurring task that runs in the background at a fixed interval. handler_code is an async Python function body (same as register_new_tool). Minimum interval: 10 seconds. Use for: periodic health checks, log rotation, data sync, auto-backup, monitoring, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique name for this scheduled task"},
                    "interval": {"type": "integer", "description": "Run every N seconds"},
                    "handler_code": {"type": "string", "description": "Async Python function body to execute each interval"}
                },
                "required": ["name", "interval", "handler_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_scheduled_task",
            "description": "Cancel a previously scheduled recurring task by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the scheduled task to cancel"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_scheduled_tasks",
            "description": "List all active scheduled tasks with their intervals and last run times.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_process",
            "description": "Spawn a long-running background process (e.g., start a new agent, run a server, launch a service). Returns the PID. Logs to /tmp/openclaw-spawn-{name}.log. Sources .env automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The full command to run (e.g., 'python agent.py', 'node server.js')"},
                    "name": {"type": "string", "description": "Human-readable name for this process"},
                    "cwd": {"type": "string", "description": "Working directory. Defaults to ARMY_HOME."},
                    "env_vars": {"type": "object", "description": "Additional environment variables as key-value pairs"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_env",
            "description": "Read, set, or list environment variables. Changes persist to .env file. Actions: 'get' (read one var), 'set' (set and persist a var), 'list' (show relevant vars). API keys are automatically masked in output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'get', 'set', 'list'"},
                    "key": {"type": "string", "description": "Environment variable name (for get/set)"},
                    "value": {"type": "string", "description": "Value to set (for set action)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "unregister_tool",
            "description": "Remove a dynamically registered tool by name. Use this to clean up tools that are no longer needed or that have bugs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the dynamic tool to remove"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Execute a SQL query against the PostgreSQL database. Returns rows for SELECT queries, affected count for mutations. Blocks DROP DATABASE/SCHEMA for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The SQL query to execute"},
                    "database": {"type": "string", "description": "Database name. Default 'postgres'.", "default": "postgres"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_store",
            "description": "Store a memory in the Memory Service for long-term recall. Use this to remember important facts, user preferences, task outcomes, or anything you want to recall later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The memory content to store"},
                    "category": {"type": "string", "description": "Category (e.g., 'user_preference', 'task_result', 'system_knowledge'). Default 'general'.", "default": "general"},
                    "importance": {"type": "number", "description": "Importance score 0.0-1.0. Default 0.7.", "default": 0.7},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags for organization"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search the Memory Service for relevant memories using vector similarity and keywords. Use this to recall past conversations, stored facts, or user preferences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (natural language)"},
                    "limit": {"type": "integer", "description": "Max results. Default 10.", "default": 10},
                    "category": {"type": "string", "description": "Filter by category (optional)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send an email or notification via the Notification Service (port 18870). Requires SMTP credentials to be configured in the service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body content"},
                    "notification_type": {"type": "string", "description": "Type: 'email'. Default 'email'.", "default": "email"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search file contents in a directory (like grep). Finds lines matching a text or regex pattern across all files. Returns file path, line number, and matched text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to search in"},
                    "pattern": {"type": "string", "description": "Search pattern (text or regex)"},
                    "file_pattern": {"type": "string", "description": "Glob pattern for files to search (e.g., '*.py'). Default '*'.", "default": "*"},
                    "max_results": {"type": "integer", "description": "Max matching lines to return. Default 50.", "default": 50},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex. Default false.", "default": False}
                },
                "required": ["directory", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_process",
            "description": "Manage spawned background processes. Actions: 'status' (check if PID is alive), 'kill' (terminate by PID), 'log' (read process log by name), 'list' (list all spawn logs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'status', 'kill', 'log', 'list'"},
                    "pid": {"type": "integer", "description": "Process ID (for status/kill)"},
                    "name": {"type": "string", "description": "Process name (for log lookup)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_query",
            "description": "Interface with the Knowledge Bridge (Obsidian vault, port 18850). Actions: 'search' (search notes by query), 'read' (read a note by path), 'write' (create/update a note), 'list_tags' (list all tags).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'search', 'read', 'write', 'list_tags'"},
                    "query": {"type": "string", "description": "Search query (for search action)"},
                    "path": {"type": "string", "description": "Note path (for read/write)"},
                    "content": {"type": "string", "description": "Note content (for write)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for the note (for write)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_sessions",
            "description": "Manage chat sessions. Actions: 'list' (all sessions), 'get' (one session's messages), 'clear' (delete one session), 'clear_all' (reset all), 'export' (save session to file).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'list', 'get', 'clear', 'clear_all', 'export'"},
                    "session_id": {"type": "string", "description": "Session ID (for get/clear/export)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "broadcast_event",
            "description": "Broadcast a custom event to all connected WebSocket clients. Use for real-time notifications, status updates, alerts, or custom events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Event type name (e.g., 'alert', 'status_update', 'task_complete')"},
                    "data": {"type": "object", "description": "Event data payload (JSON object)"}
                },
                "required": ["event_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get comprehensive system runtime information: memory usage, disk space, PID, Python version, active sessions, workflows, scheduled tasks, dynamic tools, and more.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eval_python",
            "description": "Execute arbitrary Python code and return stdout/stderr. Use for ad-hoc computation, data analysis, one-off scripts, or quick tests. All standard libraries are pre-imported. Runs in a subprocess with a configurable timeout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute. Can use print() for output."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds. Default 30, max 120.", "default": 30}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "redis_command",
            "description": "Execute a Redis command via redis-cli. Use for caching, pub/sub, counters, session data, rate limiting, queues, etc. Blocks destructive commands (FLUSHALL, SHUTDOWN).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Redis command (e.g., 'GET mykey', 'SET mykey value', 'KEYS *', 'HGETALL hash')"},
                    "database": {"type": "integer", "description": "Redis database number. Default 0.", "default": 0}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_workflow_manifest",
            "description": "Create, read, update, or delete YAML workflow manifests. Manifests are reusable task templates with steps, dependencies, and manager assignments. Actions: 'list', 'get', 'create', 'update', 'delete'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'list', 'get', 'create', 'update', 'delete'"},
                    "name": {"type": "string", "description": "Manifest name (for get/create/update/delete)"},
                    "content": {"type": "object", "description": "Manifest content (for create/update). Include 'description', 'version', 'steps' array."},
                    "step_id": {"type": "string", "description": "Step ID (for step-level operations)"},
                    "step_data": {"type": "object", "description": "Step data (for step-level operations)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cron_schedule",
            "description": "Schedule a task at a specific time of day or day of week (cron-style). Unlike schedule_task (interval-based), this runs at exact times. Formats: 'daily HH:MM', 'hourly :MM', 'weekly DAY HH:MM'. Persists across restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'schedule', 'cancel', 'list'"},
                    "name": {"type": "string", "description": "Unique task name (for schedule/cancel)"},
                    "schedule": {"type": "string", "description": "Schedule format: 'daily 03:00', 'hourly :30', 'weekly monday 09:00'"},
                    "handler_code": {"type": "string", "description": "Async Python function body to execute at each scheduled time"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compress_archive",
            "description": "Create, extract, or list contents of archives. Supports zip, tar.gz, tar.bz2. Use for compressing backups, packaging deployments, or extracting downloaded archives.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'create', 'extract', 'list'"},
                    "archive_path": {"type": "string", "description": "Path to the archive file"},
                    "source_path": {"type": "string", "description": "Source file/directory (for create) or extraction destination (for extract)"},
                    "format": {"type": "string", "description": "Archive format: 'zip', 'tar.gz', 'tar.bz2'. Default 'zip'.", "default": "zip"}
                },
                "required": ["action", "archive_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "diff_files",
            "description": "Compare two files or text strings and generate a unified diff. Shows added/removed lines. Use for code review, tracking changes, comparing configs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path_a": {"type": "string", "description": "Path to first file (use with path_b)"},
                    "path_b": {"type": "string", "description": "Path to second file (use with path_a)"},
                    "text_a": {"type": "string", "description": "First text string (use with text_b, alternative to file paths)"},
                    "text_b": {"type": "string", "description": "Second text string (use with text_a)"},
                    "context_lines": {"type": "integer", "description": "Lines of context around changes. Default 3.", "default": 3}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "webhook_register",
            "description": "Register, remove, or list dynamic webhook endpoints. Webhooks let external services call back into the orchestrator. Actions: 'register', 'remove', 'list'. Registered webhooks are accessible at /webhook/{path}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'register', 'remove', 'list'"},
                    "path": {"type": "string", "description": "Webhook URL path (e.g., 'github', 'slack/events')"},
                    "handler_code": {"type": "string", "description": "Async Python function body. Receives 'request_data' dict. Returns response string."},
                    "description": {"type": "string", "description": "Human-readable description of what this webhook does"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard",
            "description": "Read or write the macOS clipboard (pasteboard). Actions: 'read' (get clipboard contents), 'write' (set clipboard contents). Useful for macOS automation workflows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'read', 'write'"},
                    "content": {"type": "string", "description": "Content to write to clipboard (for write action)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agent_message",
            "description": "Send a direct message to any agent (king, managers, workers) and get its response. Unlike delegation tools which route to specific managers, this lets you talk to ANY agent by name for direct communication, context sharing, or coordination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Agent name (e.g., 'king-ai', 'alpha-manager', 'coding-1', 'agentic-2')"},
                    "message": {"type": "string", "description": "Message to send to the agent"},
                    "timeout": {"type": "integer", "description": "Response timeout in seconds. Default 60.", "default": 60}
                },
                "required": ["agent_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_config",
            "description": "Read/write structured JSON/YAML config files with dot-notation key paths. Actions: 'view' (show full file), 'get' (read a nested key), 'set' (write a nested key), 'delete' (remove a key). Key paths use dots: 'server.port', 'gateway.auth.token'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'view', 'get', 'set', 'delete'"},
                    "path": {"type": "string", "description": "Path to the config file (JSON or YAML)"},
                    "key_path": {"type": "string", "description": "Dot-notation key path (e.g., 'server.host', 'plugins.entries.name')"},
                    "value": {"description": "Value to set (for set action). Can be string, number, boolean, object, or array."}
                },
                "required": ["action", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_query",
            "description": "Query, analyze, tail, and rotate log files across all services. Actions: 'tail' (last N lines), 'search' (pattern match with optional time filter), 'stats' (summary statistics), 'rotate' (compress logs over 1 MB), 'list' (available log files).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'tail', 'search', 'stats', 'rotate', 'list'"},
                    "source": {"type": "string", "description": "Log source: 'activity', 'quality', 'failures', 'orchestrator', or a file path"},
                    "pattern": {"type": "string", "description": "Search pattern (for search action)"},
                    "hours": {"type": "number", "description": "Only return entries from the last N hours (for search)"},
                    "limit": {"type": "integer", "description": "Max results (default 100)"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex (default false)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "network_probe",
            "description": "Network diagnostics: DNS lookup, ping, port check, traceroute, local network info. Actions: 'dns' (resolve hostname), 'ping' (ICMP ping), 'port_check' (TCP connect test), 'local_info' (local IPs/hostname), 'traceroute' (trace route).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'dns', 'ping', 'port_check', 'local_info', 'traceroute'"},
                    "target": {"type": "string", "description": "Hostname or IP address"},
                    "port": {"type": "integer", "description": "Port number (for port_check)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 5)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "data_transform",
            "description": "Convert data between CSV, JSON, YAML, and TOML formats. Apply JQ-like queries on JSON data. Actions: 'convert' (format conversion), 'query' (JQ-style path query on JSON), 'detect' (detect data format), 'validate' (validate format correctness).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'convert', 'query', 'detect', 'validate'"},
                    "data": {"type": "string", "description": "The data string to process"},
                    "from_format": {"type": "string", "description": "Source format: 'json', 'yaml', 'csv', 'toml'"},
                    "to_format": {"type": "string", "description": "Target format: 'json', 'yaml', 'csv'"},
                    "query": {"type": "string", "description": "JQ-style query path like '.key.subkey[0].name'"},
                    "path": {"type": "string", "description": "Read data from this file path instead of 'data' param"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hash_encode",
            "description": "Compute hashes, encode/decode data, generate secure tokens. Actions: 'hash' (SHA256/MD5/SHA1/SHA512), 'base64_encode', 'base64_decode', 'url_encode', 'url_decode', 'hex_encode', 'hex_decode', 'generate_token' (cryptographically secure).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'hash', 'base64_encode', 'base64_decode', 'url_encode', 'url_decode', 'hex_encode', 'hex_decode', 'generate_token'"},
                    "data": {"type": "string", "description": "The string to hash/encode/decode"},
                    "algorithm": {"type": "string", "description": "Hash algorithm: 'sha256' (default), 'md5', 'sha1', 'sha512'"},
                    "path": {"type": "string", "description": "Hash a file instead of string data"},
                    "length": {"type": "integer", "description": "Token length in bytes (default 32, for generate_token)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture macOS screenshots using screencapture. Actions: 'full' (entire screen), 'window' (specific window by name), 'region' (x,y,w,h rectangle), 'list_windows' (list visible app windows).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'full', 'window', 'region', 'list_windows'"},
                    "output_path": {"type": "string", "description": "Save screenshot to this path (default: /tmp/screenshot_<timestamp>.png)"},
                    "window_name": {"type": "string", "description": "App name to capture (for window action)"},
                    "region": {"type": "string", "description": "Capture region as 'x,y,w,h' (for region action)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "render_template",
            "description": "Render Jinja2-style templates with variable substitution. Provide template as string or load from file. Optionally write rendered output to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template string with {{ variable }} placeholders"},
                    "template_path": {"type": "string", "description": "Load template from this file path instead"},
                    "variables": {"type": "object", "description": "Dictionary of variables to substitute into the template"},
                    "output_path": {"type": "string", "description": "Write rendered output to this file path"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "text_process",
            "description": "Swiss-army text processing tool. Actions: 'regex_test' (test pattern), 'regex_replace' (find/replace), 'regex_extract' (extract all matches), 'stats' (word/line/char counts), 'case' (upper/lower/title/swap), 'slug' (URL-safe slug), 'lines' (split/dedup/sort/reverse/join), 'truncate' (smart truncation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'regex_test', 'regex_replace', 'regex_extract', 'stats', 'case', 'slug', 'lines', 'truncate'"},
                    "text": {"type": "string", "description": "The text to process"},
                    "pattern": {"type": "string", "description": "Regex pattern (for regex actions), case mode (for case), lines mode (for lines), or max length (for truncate)"},
                    "replacement": {"type": "string", "description": "Replacement string (for regex_replace), or join delimiter (for lines join)"},
                    "flags": {"type": "string", "description": "Regex flags: 'i' (ignorecase), 'm' (multiline), 's' (dotall)"}
                },
                "required": ["action", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "service_mesh",
            "description": "Redis pub/sub wrapper for inter-agent event-driven messaging. Actions: 'publish' (send message to a channel), 'channels' (list active pub/sub channels), 'subscribe_once' (wait for one message with timeout).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'publish', 'channels', 'subscribe_once'"},
                    "channel": {"type": "string", "description": "Redis pub/sub channel name"},
                    "message": {"type": "string", "description": "Message to publish"},
                    "timeout": {"type": "integer", "description": "Subscribe timeout in seconds (default 5)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "port_manager",
            "description": "Manage network ports across the system. Actions: 'check' (who's using a port), 'find_free' (find available port in range), 'kill' (kill process on port), 'list_army' (status of all OpenClaw Army ports).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'check', 'find_free', 'kill', 'list_army'"},
                    "port": {"type": "integer", "description": "Port number (for check/kill)"},
                    "start": {"type": "integer", "description": "Start of port range (for find_free, default 19000)"},
                    "end": {"type": "integer", "description": "End of port range (for find_free, default 19100)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_delegate",
            "description": "Delegate different tasks to multiple managers in a single tool call. Send tasks in parallel to alpha, beta, and/or gamma managers. Each task gets its own workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "List of delegation tasks",
                        "items": {
                            "type": "object",
                            "properties": {
                                "manager": {"type": "string", "description": "Target manager: 'alpha', 'beta', or 'gamma'"},
                                "task": {"type": "string", "description": "Task description to delegate"},
                                "priority": {"type": "integer", "description": "Priority 1-5 (1=highest, default 2)"}
                            },
                            "required": ["manager", "task"]
                        }
                    }
                },
                "required": ["tasks"]
            }
        }
    },
]

TOOL_TO_MANAGER = {
    "delegate_to_alpha": "alpha-manager",
    "delegate_to_beta": "beta-manager",
    "delegate_to_gamma": "gamma-manager",
}

# Internal tools (not delegation — handled directly by orchestrator)
INTERNAL_TOOLS = {
    "run_self_heal", "run_diagnostic", "query_failure_patterns",
    "modify_own_code", "rollback_code_change",
    "register_new_tool", "register_new_agent", "unregister_tool",
    "update_system_prompt", "remove_prompt_section",
    "check_quality", "view_modification_history",
    "read_own_code", "run_shell_command", "http_fetch",
    "install_package", "restart_self", "git_command",
    "create_backup", "setup_launchd",
    "read_file", "write_file", "list_files",
    "schedule_task", "cancel_scheduled_task", "list_scheduled_tasks",
    "spawn_process", "manage_env",
    "query_database", "memory_store", "memory_search",
    "send_notification", "search_files", "manage_process",
    "knowledge_query", "manage_sessions", "broadcast_event",
    "system_info",
    "eval_python", "redis_command", "manage_workflow_manifest",
    "cron_schedule", "compress_archive", "diff_files",
    "webhook_register", "clipboard", "agent_message", "manage_config",
    "log_query", "network_probe", "data_transform", "hash_encode",
    "screenshot", "render_template", "text_process", "service_mesh",
    "port_manager", "batch_delegate",
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
    version="3.0.0",
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

# Tokens Kimi K2.5 sometimes emits as text instead of using the tool_calls field
_TOOL_TOKEN_RE = re.compile(
    r"<\|tool_calls?_section_begin\|>.*?<\|tool_calls?_section_end\|>",
    re.DOTALL,
)
_TOOL_TOKEN_TAGS = re.compile(r"<\|tool_call[^|]*\|>")
_FAKE_COMPLETION_ID = re.compile(r"\bchatcmpl-tool-[0-9a-f]{32,}\b")


def _strip_tool_tokens(text: str) -> str:
    """Remove raw Kimi tool-call tokens and fake completion IDs that leaked into a text response."""
    text = _TOOL_TOKEN_RE.sub("", text)
    text = _TOOL_TOKEN_TAGS.sub("", text)
    text = _FAKE_COMPLETION_ID.sub("", text)
    return text.strip()


def _parse_inline_tool_calls(content: str) -> list:
    """
    Parse tool calls that Kimi K2.5 emitted as text in the content field.
    Returns a list of SimpleNamespace objects compatible with the tool-call loop,
    or an empty list if no valid inline calls were found.
    Format: <|tool_calls_section_begin|> <|tool_call_begin|> functions.NAME:IDX
    <|tool_call_argument_begin|> {JSON} <|tool_call_end|> <|tool_calls_section_end|>
    """
    from types import SimpleNamespace
    if "<|tool_call" not in content:
        return []
    # Extract individual tool calls
    pattern = re.compile(
        r"functions\.(\w+):\d+\s*"
        r"<\|tool_call_argument_begin\|>\s*"
        r"(\{.*?\})\s*"
        r"<\|tool_call_end\|>",
        re.DOTALL,
    )
    calls = []
    for match in pattern.finditer(content):
        fn_name = match.group(1)
        raw_args = match.group(2)
        # Validate JSON
        try:
            json.loads(raw_args)
        except json.JSONDecodeError:
            continue
        call_id = f"inline_{uuid.uuid4().hex[:12]}"
        calls.append(SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=fn_name, arguments=raw_args),
        ))
    return calls


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
                    _record_failure("dispatch_fail", f"HTTP {resp.status} from {manager}: {body[:100]}", manager)
                    return {"dispatched": False, "response_text": "", "error": f"HTTP {resp.status}: {body[:200]}"}
    except Exception as e:
        log.warning(f"Failed to dispatch to {manager} (port {port}): {type(e).__name__}: {e}")
        category = "timeout" if "Timeout" in type(e).__name__ else "dispatch_fail"
        _record_failure(category, f"{type(e).__name__}: {str(e)[:100]}", manager)
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

    # Build messages with system prompt (uses dynamic prompt system)
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    effective_prompt = get_effective_system_prompt(today)

    # Build tools list including dynamic tools
    all_tools = list(MANAGER_TOOLS)
    for dt in _dynamic_tools:
        all_tools.append({
            "type": "function",
            "function": {
                "name": dt["name"],
                "description": dt["description"],
                "parameters": dt["parameters"],
            }
        })

    messages = [
        {"role": "system", "content": effective_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]

    # Track timing for quality scoring
    _llm_start_time = time.monotonic()

    # ── Multi-turn tool-call loop ──────────────────────────────────────
    # The LLM can invoke tools (read_own_code, modify_own_code, etc.)
    # and we feed results back so it can chain actions across turns.
    MAX_TOOL_TURNS = 12          # safety cap — increased for complex multi-step tasks
    max_retries = 5              # per-turn retry budget for 429s
    delegations = []             # accumulate across all turns

    for _tool_turn in range(MAX_TOOL_TURNS):
        response = None
        for attempt in range(max_retries):
            try:
                await activity.record("llm_call", session_id,
                                      f"Calling {LLM_MODEL} (turn {_tool_turn + 1}, attempt {attempt + 1})",
                                      {"attempt": attempt + 1, "turn": _tool_turn + 1,
                                       "history_len": len(messages)})
                response = await llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    tools=all_tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=4096,
                )
                break  # Success
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "Too Many Requests" in err_str
                if is_rate_limit:
                    _record_failure("429_rate_limit", f"Rate limited on attempt {attempt + 1}: {err_str[:100]}")
                await activity.record("error", session_id,
                                      f"LLM call failed (attempt {attempt + 1}): {err_str[:300]}",
                                      {"attempt": attempt + 1, "is_rate_limit": is_rate_limit})
                if is_rate_limit and attempt < max_retries - 1:
                    # Rotate to a different API key
                    _rotate_key()
                    new_key = _get_api_key()
                    llm_client.api_key = new_key
                    wait = min(2 ** (attempt + 1), 16)  # 2s, 4s, 8s, 16s, 16s
                    log.warning(f"Rate limited (429), rotating key and retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                log.error(f"LLM call failed: {e}")
                error_response = f"I'm having trouble connecting to my reasoning engine right now. Error: {err_str[:200]}"
                await activity.record("error_response", session_id, error_response)
                return {
                    "response": error_response,
                    "delegations": delegations,
                    "session_id": session_id,
                }

        choice = response.choices[0]
        assistant_msg = choice.message

        # Log the LLM's thinking/response
        await activity.record("llm_thinking", session_id,
                              assistant_msg.content or "(no text — tool calls only)",
                              {"finish_reason": choice.finish_reason,
                               "has_tool_calls": bool(assistant_msg.tool_calls),
                               "tool_call_count": len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0,
                               "turn": _tool_turn + 1})

        # ── Resolve tool calls (real or inline-parsed) ────────────────
        effective_tool_calls = list(assistant_msg.tool_calls or [])
        inline_parsed = False
        if not effective_tool_calls and assistant_msg.content:
            effective_tool_calls = _parse_inline_tool_calls(assistant_msg.content)
            if effective_tool_calls:
                inline_parsed = True
                log.info(f"Parsed {len(effective_tool_calls)} inline tool call(s) from content (turn {_tool_turn + 1})")

        if not effective_tool_calls:
            break

        # ── Process tool calls in this turn ────────────────────────────
        tool_call_info = []
        for tc in effective_tool_calls:
            tool_call_info.append({"function": tc.function.name, "args": tc.function.arguments[:200]})
        await activity.record("llm_tool_calls", session_id,
                              f"LLM requested {len(effective_tool_calls)} tool call(s) (turn {_tool_turn + 1}){' [inline-parsed]' if inline_parsed else ''}",
                              {"tool_calls": tool_call_info, "turn": _tool_turn + 1})

        # Separate internal tools from manager delegations for parallel dispatch
        internal_calls = []
        manager_calls = []
        for tc in effective_tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {"task": tc.function.arguments}
            if fn_name in INTERNAL_TOOLS:
                internal_calls.append((tc, fn_name, fn_args))
            elif TOOL_TO_MANAGER.get(fn_name):
                manager_calls.append((tc, fn_name, fn_args))
            else:
                internal_calls.append((tc, fn_name, fn_args))  # dynamic tools

        # ── Execute internal tools sequentially ────────────────────────
        turn_tool_results = {}  # tc.id -> (delegation_entry, tool_result_str)
        for tc, fn_name, fn_args in internal_calls:
            internal_result = None
            internal_task = fn_name

            if fn_name == "run_self_heal":
                reason = fn_args.get("reason", "LLM-triggered")
                internal_result = await self_heal(reason=reason)
                internal_task = f"Self-heal: {reason}"
            elif fn_name == "run_diagnostic":
                internal_result = await run_diagnostic()
                internal_task = "System diagnostic"
            elif fn_name == "query_failure_patterns":
                hours = fn_args.get("hours", 1)
                internal_result = _query_failure_patterns(hours=hours)
                internal_task = f"Query failure patterns ({hours}h)"
            elif fn_name == "modify_own_code":
                internal_result = _apply_code_edit(
                    fn_args.get("old_text", ""),
                    fn_args.get("new_text", ""),
                    fn_args.get("description", "LLM self-modification"),
                )
                internal_task = f"Self-modify: {fn_args.get('description', '')[:100]}"
                if internal_result.get("applied"):
                    await activity.record("self_modify", session_id,
                                          internal_task, {"backup": internal_result.get("backup", "")})
            elif fn_name == "rollback_code_change":
                internal_result = _rollback_last_modification()
                internal_task = "Rollback last code change"
                if internal_result.get("rolled_back"):
                    await activity.record("self_modify_rollback", session_id,
                                          internal_result.get("detail", ""))
            elif fn_name == "register_new_tool":
                internal_result = register_tool(
                    fn_args.get("name", ""),
                    fn_args.get("description", ""),
                    fn_args.get("parameters", {}),
                    fn_args.get("handler_code", "return 'not implemented'"),
                )
                internal_task = f"Register tool: {fn_args.get('name', '')}"
                if internal_result.get("registered"):
                    await activity.record("tool_register", session_id,
                                          f"Registered tool: {fn_args.get('name', '')}")
            elif fn_name == "register_new_agent":
                internal_result = register_agent(
                    fn_args.get("name", ""),
                    fn_args.get("port", 0),
                    fn_args.get("description", ""),
                    fn_args.get("capabilities", []),
                )
                internal_task = f"Register agent: {fn_args.get('name', '')}"
                if internal_result.get("registered"):
                    await activity.record("agent_register", session_id,
                                          f"Registered agent: {fn_args.get('name', '')}")
            elif fn_name == "update_system_prompt":
                internal_result = update_prompt_section(
                    fn_args.get("section_name", ""),
                    fn_args.get("content", ""),
                )
                internal_task = f"Update prompt: {fn_args.get('section_name', '')}"
                if internal_result.get("updated"):
                    await activity.record("prompt_update", session_id,
                                          f"Updated prompt section: {fn_args.get('section_name', '')}")
            elif fn_name == "remove_prompt_section":
                internal_result = remove_prompt_section(fn_args.get("section_name", ""))
                internal_task = f"Remove prompt section: {fn_args.get('section_name', '')}"
            elif fn_name == "check_quality":
                internal_result = _detect_quality_degradation()
                internal_task = "Quality check"
            elif fn_name == "view_modification_history":
                limit = fn_args.get("limit", 10)
                internal_result = {"modifications": _list_modifications(limit)}
                internal_task = f"View modification history (last {limit})"
            elif fn_name == "read_own_code":
                internal_result = _read_own_code(
                    start_line=fn_args.get("start_line"),
                    end_line=fn_args.get("end_line"),
                    search=fn_args.get("search"),
                    function_name=fn_args.get("function_name"),
                )
                internal_task = "Read own source code"
            elif fn_name == "run_shell_command":
                cmd = fn_args.get("command", "")
                timeout_s = fn_args.get("timeout", 60)
                internal_result = _run_shell_command(cmd, timeout_s)
                internal_task = f"Shell: {cmd[:80]}"
            elif fn_name == "http_fetch":
                internal_result = await _http_fetch(
                    url=fn_args.get("url", ""),
                    method=fn_args.get("method", "GET"),
                    headers=fn_args.get("headers"),
                    body=fn_args.get("body"),
                )
                internal_task = f"HTTP fetch: {fn_args.get('url', '')[:80]}"
            elif fn_name == "install_package":
                pkg = fn_args.get("package", "")
                upgrade = fn_args.get("upgrade", False)
                internal_result = _install_package(pkg, upgrade)
                internal_task = f"Install package: {pkg}"
                if internal_result.get("installed"):
                    await activity.record("install_package", session_id, f"Installed: {pkg}")
            elif fn_name == "restart_self":
                reason = fn_args.get("reason", "requested")
                internal_result = await _restart_self(reason)
                internal_task = f"Restart self: {reason}"
                if internal_result.get("reloading"):
                    await activity.record("restart_self", session_id, f"Restarting: {reason}")
                    # Schedule shutdown after response is sent
                    asyncio.get_event_loop().call_later(2, lambda: os._exit(0))
            elif fn_name == "git_command":
                cmd = fn_args.get("command", "status")
                cwd = fn_args.get("cwd")
                internal_result = _git_command(cmd, cwd)
                internal_task = f"Git: {cmd[:80]}"
            elif fn_name == "create_backup":
                label = fn_args.get("label", "")
                internal_result = _create_backup(label)
                internal_task = f"Backup: {label or 'manual'}"
                if internal_result.get("created"):
                    await activity.record("create_backup", session_id,
                                          f"Backup created: {internal_result.get('backup_path', '')}")
            elif fn_name == "setup_launchd":
                action = fn_args.get("action", "install")
                internal_result = _setup_launchd(action)
                internal_task = f"Launchd: {action}"
                await activity.record("setup_launchd", session_id, f"Launchd {action}")
            elif fn_name == "read_file":
                internal_result = _read_file(
                    fn_args.get("path", ""),
                    start_line=fn_args.get("start_line"),
                    end_line=fn_args.get("end_line"),
                )
                internal_task = f"Read file: {fn_args.get('path', '')[:80]}"
            elif fn_name == "write_file":
                internal_result = _write_file(
                    fn_args.get("path", ""),
                    fn_args.get("content", ""),
                    append=fn_args.get("append", False),
                )
                internal_task = f"Write file: {fn_args.get('path', '')[:80]}"
            elif fn_name == "list_files":
                internal_result = _list_files(
                    fn_args.get("path", "."),
                    pattern=fn_args.get("pattern", "*"),
                    recursive=fn_args.get("recursive", False),
                )
                internal_task = f"List files: {fn_args.get('path', '')[:80]}"
            elif fn_name == "schedule_task":
                internal_result = _schedule_task(
                    fn_args.get("name", ""),
                    fn_args.get("interval", 60),
                    fn_args.get("handler_code", "pass"),
                )
                internal_task = f"Schedule task: {fn_args.get('name', '')}"
                if internal_result.get("scheduled"):
                    await activity.record("schedule_task", session_id,
                                          f"Scheduled: {fn_args.get('name', '')} every {fn_args.get('interval', 60)}s")
            elif fn_name == "cancel_scheduled_task":
                internal_result = _cancel_scheduled_task(fn_args.get("name", ""))
                internal_task = f"Cancel scheduled: {fn_args.get('name', '')}"
            elif fn_name == "list_scheduled_tasks":
                internal_result = _list_scheduled_tasks()
                internal_task = "List scheduled tasks"
            elif fn_name == "spawn_process":
                internal_result = _spawn_process(
                    fn_args.get("command", ""),
                    name=fn_args.get("name", ""),
                    cwd=fn_args.get("cwd"),
                    env_vars=fn_args.get("env_vars"),
                )
                internal_task = f"Spawn: {fn_args.get('name', fn_args.get('command', '')[:50])}"
                if internal_result.get("spawned"):
                    await activity.record("spawn_process", session_id,
                                          f"Spawned PID {internal_result.get('pid')}: {fn_args.get('command', '')[:80]}")
            elif fn_name == "manage_env":
                internal_result = _manage_env(
                    fn_args.get("action", "list"),
                    key=fn_args.get("key", ""),
                    value=fn_args.get("value", ""),
                )
                internal_task = f"Env: {fn_args.get('action', '')} {fn_args.get('key', '')}"
            elif fn_name == "unregister_tool":
                internal_result = unregister_tool(fn_args.get("name", ""))
                internal_task = f"Unregister tool: {fn_args.get('name', '')}"
            elif fn_name == "query_database":
                internal_result = _query_database(
                    fn_args.get("query", ""),
                    database=fn_args.get("database", "postgres"),
                )
                internal_task = f"DB query: {fn_args.get('query', '')[:80]}"
            elif fn_name == "memory_store":
                internal_result = await _memory_store(
                    fn_args.get("content", ""),
                    category=fn_args.get("category", "general"),
                    importance=fn_args.get("importance", 0.7),
                    tags=fn_args.get("tags"),
                )
                internal_task = f"Memory store: {fn_args.get('content', '')[:60]}"
            elif fn_name == "memory_search":
                internal_result = await _memory_search(
                    fn_args.get("query", ""),
                    limit=fn_args.get("limit", 10),
                    category=fn_args.get("category"),
                )
                internal_task = f"Memory search: {fn_args.get('query', '')[:60]}"
            elif fn_name == "send_notification":
                internal_result = await _send_notification(
                    fn_args.get("to", ""),
                    fn_args.get("subject", ""),
                    fn_args.get("body", ""),
                    notification_type=fn_args.get("notification_type", "email"),
                )
                internal_task = f"Notification to: {fn_args.get('to', '')[:40]}"
                if internal_result.get("sent"):
                    await activity.record("send_notification", session_id,
                                          f"Sent to {fn_args.get('to', '')}: {fn_args.get('subject', '')}")
            elif fn_name == "search_files":
                internal_result = _search_files(
                    fn_args.get("directory", "."),
                    fn_args.get("pattern", ""),
                    file_pattern=fn_args.get("file_pattern", "*"),
                    max_results=fn_args.get("max_results", 50),
                    regex=fn_args.get("regex", False),
                )
                internal_task = f"Search files: {fn_args.get('pattern', '')[:60]}"
            elif fn_name == "manage_process":
                internal_result = _manage_process(
                    fn_args.get("action", "list"),
                    pid=fn_args.get("pid", 0),
                    name=fn_args.get("name", ""),
                )
                internal_task = f"Process: {fn_args.get('action', '')} {fn_args.get('pid', '')}"
            elif fn_name == "knowledge_query":
                internal_result = await _knowledge_query(
                    fn_args.get("action", "search"),
                    query=fn_args.get("query", ""),
                    path=fn_args.get("path", ""),
                    content=fn_args.get("content", ""),
                    tags=fn_args.get("tags"),
                )
                internal_task = f"Knowledge: {fn_args.get('action', '')} {fn_args.get('query', fn_args.get('path', ''))[:60]}"
            elif fn_name == "manage_sessions":
                internal_result = _manage_sessions(
                    fn_args.get("action", "list"),
                    session_id=fn_args.get("session_id", ""),
                )
                internal_task = f"Sessions: {fn_args.get('action', '')}"
            elif fn_name == "broadcast_event":
                internal_result = await _broadcast_event(
                    fn_args.get("event_type", "custom"),
                    data=fn_args.get("data"),
                )
                internal_task = f"Broadcast: {fn_args.get('event_type', '')}"
            elif fn_name == "system_info":
                internal_result = _system_info()
                internal_task = "System info"
            elif fn_name == "eval_python":
                internal_result = await _eval_python(
                    fn_args.get("code", ""),
                    timeout=fn_args.get("timeout", 30),
                )
                internal_task = f"Eval Python: {fn_args.get('code', '')[:60]}"
            elif fn_name == "redis_command":
                internal_result = _redis_command(
                    fn_args.get("command", ""),
                    database=fn_args.get("database", 0),
                )
                internal_task = f"Redis: {fn_args.get('command', '')[:60]}"
            elif fn_name == "manage_workflow_manifest":
                internal_result = _manage_workflow_manifest(
                    fn_args.get("action", "list"),
                    name=fn_args.get("name", ""),
                    content=fn_args.get("content"),
                    step_id=fn_args.get("step_id", ""),
                    step_data=fn_args.get("step_data"),
                )
                internal_task = f"Workflow manifest: {fn_args.get('action', '')} {fn_args.get('name', '')}"
            elif fn_name == "cron_schedule":
                cron_action = fn_args.get("action", "list")
                if cron_action == "schedule":
                    internal_result = _cron_schedule(
                        fn_args.get("name", ""),
                        fn_args.get("schedule", ""),
                        fn_args.get("handler_code", "pass"),
                    )
                    internal_task = f"Cron schedule: {fn_args.get('name', '')} @ {fn_args.get('schedule', '')}"
                elif cron_action == "cancel":
                    internal_result = _cancel_cron_task(fn_args.get("name", ""))
                    internal_task = f"Cron cancel: {fn_args.get('name', '')}"
                else:
                    internal_result = _list_cron_tasks()
                    internal_task = "Cron list"
            elif fn_name == "compress_archive":
                internal_result = _compress_archive(
                    fn_args.get("action", "list"),
                    fn_args.get("archive_path", ""),
                    source_path=fn_args.get("source_path", ""),
                    format=fn_args.get("format", "zip"),
                )
                internal_task = f"Archive: {fn_args.get('action', '')} {fn_args.get('archive_path', '')[:50]}"
            elif fn_name == "diff_files":
                internal_result = _diff_files(
                    path_a=fn_args.get("path_a", ""),
                    path_b=fn_args.get("path_b", ""),
                    text_a=fn_args.get("text_a", ""),
                    text_b=fn_args.get("text_b", ""),
                    context_lines=fn_args.get("context_lines", 3),
                )
                internal_task = f"Diff: {fn_args.get('path_a', fn_args.get('text_a', '')[:30])[:40]}"
            elif fn_name == "webhook_register":
                wh_action = fn_args.get("action", "list")
                if wh_action == "register":
                    internal_result = _register_webhook(
                        fn_args.get("path", ""),
                        fn_args.get("handler_code", "return 'ok'"),
                        description=fn_args.get("description", ""),
                    )
                    internal_task = f"Webhook register: /webhook/{fn_args.get('path', '')}"
                elif wh_action == "remove":
                    internal_result = _unregister_webhook(fn_args.get("path", ""))
                    internal_task = f"Webhook remove: {fn_args.get('path', '')}"
                else:
                    internal_result = _list_webhooks()
                    internal_task = "Webhook list"
            elif fn_name == "clipboard":
                internal_result = _clipboard(
                    fn_args.get("action", "read"),
                    content=fn_args.get("content", ""),
                )
                internal_task = f"Clipboard: {fn_args.get('action', '')}"
            elif fn_name == "agent_message":
                internal_result = await _agent_message(
                    fn_args.get("agent_name", ""),
                    fn_args.get("message", ""),
                    timeout=fn_args.get("timeout", 60),
                )
                internal_task = f"Message to {fn_args.get('agent_name', '')}: {fn_args.get('message', '')[:40]}"
            elif fn_name == "manage_config":
                internal_result = _manage_config(
                    fn_args.get("action", "view"),
                    fn_args.get("path", ""),
                    key_path=fn_args.get("key_path", ""),
                    value=fn_args.get("value"),
                )
                internal_task = f"Config: {fn_args.get('action', '')} {fn_args.get('path', '')[:40]}"
            elif fn_name == "log_query":
                internal_result = _log_query(
                    fn_args.get("action", "list"),
                    source=fn_args.get("source", ""),
                    pattern=fn_args.get("pattern", ""),
                    hours=fn_args.get("hours", 0),
                    limit=fn_args.get("limit", 100),
                    regex=fn_args.get("regex", False),
                )
                internal_task = f"Log query: {fn_args.get('action', '')} {fn_args.get('source', '')}"
            elif fn_name == "network_probe":
                internal_result = _network_probe(
                    fn_args.get("action", "local_info"),
                    target=fn_args.get("target", ""),
                    port=fn_args.get("port", 0),
                    timeout=fn_args.get("timeout", 5),
                )
                internal_task = f"Network: {fn_args.get('action', '')} {fn_args.get('target', '')}"
            elif fn_name == "data_transform":
                internal_result = _data_transform(
                    fn_args.get("action", "detect"),
                    data=fn_args.get("data", ""),
                    from_format=fn_args.get("from_format", ""),
                    to_format=fn_args.get("to_format", ""),
                    query=fn_args.get("query", ""),
                    path=fn_args.get("path", ""),
                )
                internal_task = f"Data transform: {fn_args.get('action', '')} {fn_args.get('from_format', '')}→{fn_args.get('to_format', '')}"
            elif fn_name == "hash_encode":
                internal_result = _hash_encode(
                    fn_args.get("action", "hash"),
                    data=fn_args.get("data", ""),
                    algorithm=fn_args.get("algorithm", "sha256"),
                    path=fn_args.get("path", ""),
                    length=fn_args.get("length", 32),
                )
                internal_task = f"Hash/encode: {fn_args.get('action', '')}"
            elif fn_name == "screenshot":
                internal_result = _screenshot(
                    action=fn_args.get("action", "full"),
                    output_path=fn_args.get("output_path", ""),
                    window_name=fn_args.get("window_name", ""),
                    region=fn_args.get("region", ""),
                )
                internal_task = f"Screenshot: {fn_args.get('action', 'full')}"
            elif fn_name == "render_template":
                internal_result = _render_template(
                    template=fn_args.get("template", ""),
                    template_path=fn_args.get("template_path", ""),
                    variables=fn_args.get("variables", {}),
                    output_path=fn_args.get("output_path", ""),
                )
                internal_task = f"Render template ({len(fn_args.get('variables', {}))} vars)"
            elif fn_name == "text_process":
                internal_result = _text_process(
                    fn_args.get("action", "stats"),
                    text=fn_args.get("text", ""),
                    pattern=fn_args.get("pattern", ""),
                    replacement=fn_args.get("replacement", ""),
                    flags=fn_args.get("flags", ""),
                )
                internal_task = f"Text process: {fn_args.get('action', '')}"
            elif fn_name == "service_mesh":
                internal_result = await _service_mesh(
                    fn_args.get("action", "channels"),
                    channel=fn_args.get("channel", ""),
                    message=fn_args.get("message", ""),
                    timeout=fn_args.get("timeout", 5),
                )
                internal_task = f"Service mesh: {fn_args.get('action', '')} {fn_args.get('channel', '')}"
            elif fn_name == "port_manager":
                internal_result = _port_manager(
                    fn_args.get("action", "list_army"),
                    port=fn_args.get("port", 0),
                    start=fn_args.get("start", 0),
                    end=fn_args.get("end", 0),
                )
                internal_task = f"Port manager: {fn_args.get('action', '')} {fn_args.get('port', '')}"
            elif fn_name == "batch_delegate":
                internal_result = await _batch_delegate(
                    fn_args.get("tasks", []),
                )
                internal_task = f"Batch delegate: {len(fn_args.get('tasks', []))} tasks"
            else:
                # Dynamic tool execution
                result_str = await _execute_dynamic_tool(fn_name, fn_args)
                internal_result = {"result": result_str}
                internal_task = f"Dynamic tool: {fn_name}"

            d_entry = {
                "manager": "self",
                "task": internal_task,
                "priority": 1,
                "workflow_id": "",
                "dispatched": True,
                "agent_response": json.dumps(internal_result, default=str)[:2000],
                "error": "",
            }
            delegations.append(d_entry)
            turn_tool_results[tc.id] = (d_entry, json.dumps(internal_result, default=str)[:2000])

        # ── Dispatch manager calls in parallel ─────────────────────────
        async def _dispatch_one(tc, fn_name, fn_args):
            manager = TOOL_TO_MANAGER[fn_name]
            task_desc = fn_args.get("task", "")
            priority = fn_args.get("priority", 2)
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
            subtask = plan.subtasks[0]
            dispatch_result = await dispatch_to_manager(manager, subtask, plan.id)
            dispatched = dispatch_result["dispatched"]
            agent_response = dispatch_result.get("response_text", "")
            dispatch_error = dispatch_result.get("error", "")

            # Auto-heal and retry on dispatch failure
            if not dispatched:
                log.warning(f"Dispatch to {manager} failed — auto-triggering self-heal and retry")
                await activity.record("auto_heal", session_id,
                                      f"Dispatch to {manager} failed, triggering self-heal",
                                      {"manager": manager, "error": dispatch_error[:200]})
                heal_result = await self_heal(reason=f"dispatch to {manager} failed: {dispatch_error[:100]}")
                heal_status = heal_result.get("manager_status", {}).get(manager, "unknown")
                if heal_status in ("up", "restarted"):
                    log.info(f"Self-heal restored {manager} — retrying dispatch")
                    dispatch_result = await dispatch_to_manager(manager, subtask, plan.id)
                    dispatched = dispatch_result["dispatched"]
                    agent_response = dispatch_result.get("response_text", "")
                    dispatch_error = dispatch_result.get("error", "")
                    if dispatched:
                        await activity.record("auto_heal", session_id,
                                              f"Retry succeeded after self-heal for {manager}",
                                              {"manager": manager})

            d_entry = {
                "manager": manager,
                "task": task_desc,
                "priority": priority,
                "workflow_id": plan.id,
                "dispatched": dispatched,
                "agent_response": agent_response[:2000] if agent_response else "",
                "error": dispatch_error,
            }

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
            return tc.id, d_entry

        if manager_calls:
            mgr_results = await asyncio.gather(
                *[_dispatch_one(tc, fn, fa) for tc, fn, fa in manager_calls],
                return_exceptions=True,
            )
            for result in mgr_results:
                if isinstance(result, Exception):
                    log.error(f"Parallel dispatch exception: {result}")
                    continue
                tc_id, d_entry = result
                delegations.append(d_entry)
                tool_result_str = json.dumps({
                    "status": "dispatched" if d_entry["dispatched"] else "failed",
                    "manager": d_entry["manager"],
                    "workflow_id": d_entry.get("workflow_id", ""),
                    "agent_response": d_entry.get("agent_response", "")[:300],
                    "error": d_entry.get("error", ""),
                })
                turn_tool_results[tc_id] = (d_entry, tool_result_str)

        # ── Feed tool results back into messages for next turn ─────────
        # Add the assistant message with tool_calls
        # If tool calls were inline-parsed, strip tokens from content
        msg_content = assistant_msg.content or ""
        if inline_parsed:
            msg_content = _strip_tool_tokens(msg_content)
        messages.append({
            "role": "assistant",
            "content": msg_content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in effective_tool_calls
            ],
        })
        # Add tool result messages
        for tc in effective_tool_calls:
            _, result_str = turn_tool_results.get(tc.id, (None, '{"error": "no result"}'))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })
        log.info(f"Multi-turn: completed turn {_tool_turn + 1}, processed {len(turn_tool_results)} tool results, continuing to turn {_tool_turn + 2}")
        # Continue the loop — the LLM will see tool results and decide next action

    # ── End of multi-turn loop ─────────────────────────────────────────

    # Extract the text response from the final turn
    text_response = assistant_msg.content or ""
    log.info(f"Final turn raw content (len={len(text_response)}): {text_response[:300]!r}")

    # Strip any leaked raw tool-call tokens from the text
    text_response = _strip_tool_tokens(text_response)
    log.info(f"After token strip (len={len(text_response)}): {text_response[:300]!r}")

    # Detect if response is just echoing raw tool output (JSON) instead of synthesizing
    if text_response and delegations:
        _raw_indicators = ('"code":', '"start_line":', '"end_line":', '"matches":', '"total_lines":')
        if any(ind in text_response for ind in _raw_indicators):
            log.info("Response contains raw tool output echo — forcing synthesis")
            text_response = ""

    # If the last turn had tool calls but no text, make a synthesis call
    # with full conversation context (no tools) to force a natural response
    if not text_response and delegations:
        try:
            # Build a compact summary of what tools returned
            tool_summary_parts = []
            for d in delegations:
                status = "completed" if d["dispatched"] else "failed"
                resp = d.get("agent_response", "")[:1000]
                tool_summary_parts.append(f"- {d['task']} ({status}): {resp}")
            tool_summary = "\n".join(tool_summary_parts)

            for _synth_attempt in range(3):
                try:
                    _rotate_key()
                    llm_client.api_key = _get_api_key()
                    # Use a CLEAN message chain without tool context to prevent
                    # Kimi K2.5 from trying to make tool calls in the synthesis
                    synth_messages = [
                        {"role": "system", "content": (
                            "You are a helpful assistant. Answer the user's question based on "
                            "the information provided. Do NOT attempt to use tools or functions. "
                            "Respond ONLY in natural language."
                        )},
                        {"role": "user", "content": (
                            f"Original question: {user_message}\n\n"
                            f"Here are the results from tools that were used to answer:\n{tool_summary}\n\n"
                            "Provide a complete, detailed natural language answer to the question. "
                            "Include specific data, numbers, and findings from the tool results."
                        )},
                    ]
                    synthesis = await llm_client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=synth_messages,
                        temperature=0.7,
                        max_tokens=4096,
                    )
                    raw_synth = synthesis.choices[0].message.content or ""
                    log.info(f"Synthesis raw (len={len(raw_synth)}): {raw_synth[:300]!r}")
                    text_response = _strip_tool_tokens(raw_synth)
                    if text_response:
                        await activity.record("llm_synthesis", session_id, text_response[:500],
                                              {"purpose": "synthesize after multi-turn tool calls"})
                        break
                    await asyncio.sleep(2)
                except Exception as inner_err:
                    log.warning(f"Synthesis attempt {_synth_attempt + 1} failed: {inner_err}")
                    await asyncio.sleep(min(2 ** (_synth_attempt + 1), 8))
        except Exception as synth_err:
            log.warning(f"Synthesis call failed: {synth_err}")

        # Final fallback — always produce SOMETHING if we have delegations
        if not text_response:
            parts = []
            for d in delegations:
                resp = d.get("agent_response", "")
                if resp:
                    try:
                        data = json.loads(resp)
                        if "code" in data:
                            parts.append(f"**{d['task']}**:\n```\n{data['code'][:500]}\n```")
                        elif "output" in data:
                            parts.append(f"**{d['task']}**: {data['output'][:300]}")
                        elif "matches" in data:
                            parts.append(f"**{d['task']}**: Found {len(data['matches'])} matches")
                        else:
                            parts.append(f"**{d['task']}**: {resp[:300]}")
                    except (json.JSONDecodeError, TypeError):
                        parts.append(f"**{d['task']}**: {resp[:300]}")
                else:
                    status = "✓" if d["dispatched"] else "✗"
                    parts.append(f"**{d['task']}** ({status})")
            text_response = "\n\n".join(parts) if parts else "I completed the requested actions but couldn't generate a summary due to rate limiting."

    # Save to conversation history (keep last 20 exchanges to stay within context)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": text_response})
    if len(history) > 40:  # 20 exchanges = 40 messages
        history[:] = history[-40:]

    # Persist sessions to disk after each exchange
    _save_sessions_to_disk()

    # Quality scoring
    latency_s = time.monotonic() - _llm_start_time
    quality = _record_quality(session_id, user_message, text_response, delegations, latency_s)

    # Log the final assembled response
    await activity.record("response", session_id,
                          text_response[:500],
                          {"delegation_count": len(delegations),
                           "delegations_dispatched": sum(1 for d in delegations if d["dispatched"]),
                           "response_length": len(text_response),
                           "quality_score": quality["composite"],
                           "quality_grade": quality["grade"]})

    # Auto-alert on critical quality
    if "CRITICAL_QUALITY" in quality.get("flags", []):
        await activity.record("quality_alert", session_id,
                              f"CRITICAL quality score: {quality['composite']} (grade {quality['grade']})",
                              {"flags": quality["flags"], "scores": quality["scores"]})

    return {
        "response": text_response,
        "delegations": delegations,
        "session_id": session_id,
        "quality": {"score": quality["composite"], "grade": quality["grade"]},
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


@app.get("/ping")
async def ping():
    from datetime import datetime, timezone
    return {
        "pong": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


# ── Manager Restart Logic ───────────────────────────────────────────────────

_MANAGER_PROFILES = {
    "alpha-manager": {"port": 18800, "profile": "alpha", "dir": "agents/alpha-manager", "api_key_env": "NVAPI_KIMI_KEY_1"},
    "beta-manager":  {"port": 18801, "profile": "beta",  "dir": "agents/beta-manager",  "api_key_env": "NVAPI_KIMI_KEY_2"},
    "gamma-manager": {"port": 18802, "profile": "gamma", "dir": "agents/gamma-manager", "api_key_env": "NVAPI_KIMI_KEY_2"},
}


async def _restart_manager(name: str) -> dict:
    """
    Actually restart a single manager agent via subprocess.
    Returns {"restarted": bool, "detail": str}
    """
    info = _MANAGER_PROFILES.get(name)
    if not info:
        return {"restarted": False, "detail": f"Unknown manager: {name}"}

    port = info["port"]
    profile = info["profile"]
    agent_dir = Path(ARMY_HOME) / info["dir"]

    try:
        # Auto-repair global config issues that block startup
        global_config = Path.home() / ".openclaw" / "openclaw.json"
        if global_config.exists():
            try:
                with open(global_config) as f:
                    cfg = json.load(f)
                changed = False
                plugins = cfg.get("plugins", {})
                # Remove known invalid keys
                for bad_key in ["loadPaths"]:
                    if bad_key in plugins:
                        del plugins[bad_key]
                        changed = True
                # Remove invalid plugin entries
                entries = plugins.get("entries", {})
                for bad_plugin in ["permission-broker"]:
                    if bad_plugin in entries:
                        del entries[bad_plugin]
                        changed = True
                if changed:
                    with open(global_config, "w") as f:
                        json.dump(cfg, f, indent=2)
                    log.info(f"Auto-repaired global openclaw config")
            except Exception:
                pass

        # Kill any existing process on that port
        kill_result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        )
        if kill_result.stdout.strip():
            pids = kill_result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid.strip()], timeout=3)
                except Exception:
                    pass
            await asyncio.sleep(1)

        # Clear profile locks
        profile_dir = Path.home() / f".openclaw-{profile}"
        if profile_dir.exists():
            for lock in profile_dir.rglob("*.lock"):
                try:
                    lock.unlink()
                except Exception:
                    pass

        # Start the manager with proper env vars matching start_managers.sh
        env = os.environ.copy()
        env["OPENCLAW_SERVICE_LABEL"] = name
        env["OPENCLAW_CONFIG_PATH"] = str(agent_dir / "openclaw.json")
        api_key = os.environ.get(info.get("api_key_env", ""), "") or os.environ.get("NVIDIA_API_KEY", "")
        if api_key:
            env["NVIDIA_API_KEY"] = api_key
        subprocess.Popen(
            ["openclaw", "gateway", "--port", str(port), "--force", "--profile", profile],
            cwd=str(agent_dir),
            env=env,
            stdout=open(f"/tmp/openclaw-{profile}.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # Wait and verify it came up
        for attempt in range(15):
            await asyncio.sleep(3)
            try:
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as sess:
                    async with sess.get(f"http://127.0.0.1:{port}/") as resp:
                        if resp.status == 200:
                            _refresh_agent_token(name)
                            return {"restarted": True, "detail": f"{name} restarted on port {port}"}
            except Exception:
                continue

        return {"restarted": False, "detail": f"{name} started but not responding after 45s"}
    except Exception as e:
        return {"restarted": False, "detail": f"Restart failed: {str(e)[:200]}"}


# ── Failure Pattern Tracking ────────────────────────────────────────────────

_FAILURE_LOG_PATH = Path(ARMY_HOME) / "data" / "logs" / "failures.jsonl"


def _record_failure(category: str, detail: str, manager: str = ""):
    """Append a failure record for pattern learning."""
    _FAILURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "detail": detail[:500],
        "manager": manager,
    }
    with open(_FAILURE_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def _query_failure_patterns(hours: int = 1) -> dict:
    """Analyze recent failure patterns."""
    if not _FAILURE_LOG_PATH.exists():
        return {"total_failures": 0, "patterns": [], "recommendation": "No failures recorded."}

    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    recent = []
    try:
        for line in open(_FAILURE_LOG_PATH):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            ts = datetime.fromisoformat(r["ts"]).timestamp()
            if ts >= cutoff:
                recent.append(r)
    except Exception:
        pass

    if not recent:
        return {"total_failures": 0, "patterns": [], "recommendation": "No recent failures. System is healthy."}

    # Analyze patterns
    by_category = Counter(r["category"] for r in recent)
    by_manager = Counter(r["manager"] for r in recent if r["manager"])

    patterns = []
    for cat, count in by_category.most_common(5):
        patterns.append({"category": cat, "count": count, "example": next(r["detail"] for r in recent if r["category"] == cat)})

    recommendation = "System is stable."
    if by_category.get("timeout", 0) > 3:
        recommendation = "High timeout rate — consider increasing dispatch timeout or checking NVIDIA API status."
    elif by_category.get("dispatch_fail", 0) > 2:
        recommendation = "Multiple dispatch failures — run self-heal to restart affected managers."
    elif by_category.get("429_rate_limit", 0) > 5:
        recommendation = "Heavy rate limiting — API key rotation is active but may need a paid tier upgrade."

    return {
        "total_failures": len(recent),
        "hours_analyzed": hours,
        "by_category": dict(by_category),
        "by_manager": dict(by_manager),
        "patterns": patterns,
        "recommendation": recommendation,
    }


# ── Self-Modification Engine ───────────────────────────────────────────────

_SELF_MOD_DIR = Path(ARMY_HOME) / "data" / "self-modifications"
_MAIN_PY_PATH = Path(__file__).resolve()


def _safe_backup(label: str = "auto") -> Path:
    """Create a timestamped backup of main.py before any self-modification."""
    _SELF_MOD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = _SELF_MOD_DIR / f"main_backup_{ts}_{label}.py"
    shutil.copy2(_MAIN_PY_PATH, backup)
    log.info(f"Self-mod backup: {backup}")
    return backup


def _validate_syntax(code: str) -> tuple[bool, str]:
    """Validate Python syntax without executing. Returns (ok, error_msg)."""
    try:
        compile(code, "<self-mod>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def _apply_code_edit(old_text: str, new_text: str, description: str) -> dict:
    """
    Apply a targeted text replacement to main.py with safety checks.
    Returns {"applied": bool, "detail": str, "backup": str}.
    """
    source = _MAIN_PY_PATH.read_text()

    # Verify old_text exists exactly once
    count = source.count(old_text)
    if count == 0:
        return {"applied": False, "detail": "old_text not found in source", "backup": ""}
    if count > 1:
        return {"applied": False, "detail": f"old_text found {count} times (must be unique)", "backup": ""}

    # Build the new source
    new_source = source.replace(old_text, new_text, 1)

    # Syntax check the result
    ok, err = _validate_syntax(new_source)
    if not ok:
        return {"applied": False, "detail": f"Syntax error in modified code: {err}", "backup": ""}

    # Safety: refuse edits that would remove critical infrastructure
    critical_markers = ["app = FastAPI", "async def call_llm", "@app.post(\"/chat\")",
                        "async def startup", "_health_watchdog"]
    for marker in critical_markers:
        if marker in source and marker not in new_source:
            return {"applied": False, "detail": f"Refused: edit would remove critical code '{marker}'", "backup": ""}

    # Create backup before writing
    backup = _safe_backup(hashlib.sha256(description.encode()).hexdigest()[:8])

    # Write the modified source
    _MAIN_PY_PATH.write_text(new_source)

    # Log the modification
    mod_record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "description": description[:500],
        "old_text_hash": hashlib.sha256(old_text.encode()).hexdigest()[:16],
        "new_text_hash": hashlib.sha256(new_text.encode()).hexdigest()[:16],
        "old_len": len(old_text),
        "new_len": len(new_text),
        "backup": str(backup),
    }
    mod_log = _SELF_MOD_DIR / "modifications.jsonl"
    mod_log.parent.mkdir(parents=True, exist_ok=True)
    with open(mod_log, "a") as f:
        f.write(json.dumps(mod_record) + "\n")

    return {"applied": True, "detail": f"Applied: {description}", "backup": str(backup)}


def _rollback_last_modification() -> dict:
    """Rollback to the most recent backup."""
    mod_log = _SELF_MOD_DIR / "modifications.jsonl"
    if not mod_log.exists():
        return {"rolled_back": False, "detail": "No modification history found"}

    lines = [l.strip() for l in mod_log.read_text().strip().split("\n") if l.strip()]
    if not lines:
        return {"rolled_back": False, "detail": "Modification log is empty"}

    last = json.loads(lines[-1])
    backup_path = Path(last["backup"])
    if not backup_path.exists():
        return {"rolled_back": False, "detail": f"Backup file missing: {backup_path}"}

    # Validate the backup before restoring
    backup_code = backup_path.read_text()
    ok, err = _validate_syntax(backup_code)
    if not ok:
        return {"rolled_back": False, "detail": f"Backup has syntax errors: {err}"}

    _MAIN_PY_PATH.write_text(backup_code)
    return {"rolled_back": True, "detail": f"Restored from {backup_path.name}", "backup_used": str(backup_path)}


def _list_modifications(limit: int = 10) -> list[dict]:
    """List recent self-modifications."""
    mod_log = _SELF_MOD_DIR / "modifications.jsonl"
    if not mod_log.exists():
        return []
    lines = [l.strip() for l in mod_log.read_text().strip().split("\n") if l.strip()]
    records = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


async def _hot_reload() -> dict:
    """
    Restart the orchestrator process to pick up code changes.
    Sources the .env file to ensure all API keys and config are available,
    then spawns a new process and exits the current one.
    """
    env = os.environ.copy()
    # Ensure ARMY_HOME is set for the new process
    env.setdefault("ARMY_HOME", ARMY_HOME)
    # Source .env file to pick up all environment variables (API keys, ports, etc.)
    env_file = Path(ARMY_HOME) / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'\"")
                if key:
                    env[key] = val
    try:
        subprocess.Popen(
            [sys.executable, str(_MAIN_PY_PATH)],
            cwd=str(_MAIN_PY_PATH.parent),
            env=env,
            stdout=open("/tmp/orchestrator-reload.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        await asyncio.sleep(1)
        return {"reloading": True, "detail": "New process spawned with full environment, current will exit"}
    except Exception as e:
        return {"reloading": False, "detail": f"Failed to spawn: {e}"}


@app.post("/self-modify")
async def self_modify_endpoint(old_text: str, new_text: str, description: str):
    """API endpoint for code self-modification."""
    result = _apply_code_edit(old_text, new_text, description)
    if result["applied"]:
        await activity.record("self_modify", "", description,
                              {"backup": result["backup"]})
    return result


@app.post("/self-modify/rollback")
async def rollback_endpoint():
    """Rollback the last self-modification."""
    result = _rollback_last_modification()
    if result["rolled_back"]:
        await activity.record("self_modify_rollback", "", result["detail"])
    return result


@app.get("/self-modify/history")
async def modification_history(limit: int = 10):
    """View recent self-modifications."""
    return {"modifications": _list_modifications(limit)}


@app.post("/self-modify/reload")
async def reload_endpoint():
    """Hot-reload the orchestrator after code changes."""
    result = await _hot_reload()
    if result["reloading"]:
        # Schedule shutdown after response is sent
        asyncio.get_event_loop().call_later(2, lambda: os._exit(0))
    return result


# ── Code Introspection (read_own_code) ─────────────────────────────────────

def _read_own_code(start_line: int = None, end_line: int = None,
                   search: str = None, function_name: str = None) -> dict:
    """
    Read the orchestrator's own source code for introspection.
    Supports line ranges, string search, and function lookup.
    """
    try:
        source = _MAIN_PY_PATH.read_text()
    except Exception as e:
        return {"error": f"Failed to read source: {e}"}

    lines = source.split("\n")
    total_lines = len(lines)

    # Function name search mode
    if function_name:
        pattern = re.compile(rf"^(async\s+)?def\s+{re.escape(function_name)}\s*\(")
        for i, line in enumerate(lines):
            if pattern.match(line):
                # Find the end of the function (next line at same or less indentation, or EOF)
                base_indent = len(line) - len(line.lstrip())
                func_end = i + 1
                while func_end < total_lines:
                    next_line = lines[func_end]
                    if next_line.strip() == "":
                        func_end += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= base_indent and next_line.strip():
                        break
                    func_end += 1
                return {
                    "found": True,
                    "start_line": i + 1,
                    "end_line": func_end,
                    "total_lines": total_lines,
                    "code": "\n".join(f"{j+1:4d} | {lines[j]}" for j in range(i, func_end)),
                }
        return {"found": False, "detail": f"Function '{function_name}' not found", "total_lines": total_lines}

    # String search mode
    if search:
        matches = []
        for i, line in enumerate(lines):
            if search in line:
                ctx_start = max(0, i - 10)
                ctx_end = min(total_lines, i + 11)
                matches.append({
                    "line": i + 1,
                    "context": "\n".join(f"{j+1:4d} | {lines[j]}" for j in range(ctx_start, ctx_end)),
                })
                if len(matches) >= 5:
                    break
        return {"matches": matches, "match_count": len(matches), "total_lines": total_lines}

    # Line range mode
    start = max(0, (start_line or 1) - 1)
    end = min(total_lines, (end_line or start + 50))
    return {
        "start_line": start + 1,
        "end_line": end,
        "total_lines": total_lines,
        "code": "\n".join(f"{j+1:4d} | {lines[j]}" for j in range(start, end)),
    }


# ── Shell Command Execution ────────────────────────────────────────────────

_SHELL_BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/",      # rm -rf /
    r"\bmkfs\b",             # format disk
    r"\bdd\s+if=",           # disk destroyer
    r">\s*/dev/sd",          # overwrite disk
    r"\bshutdown\b",         # system shutdown
    r"\breboot\b",           # system reboot
    r":(){ :\|:& };:",       # fork bomb
]

def _run_shell_command(command: str, timeout: int = 60) -> dict:
    """
    Execute a shell command and return the output.
    Blocks destructive commands. Timeout capped at 120s.
    """
    # Safety checks
    for pattern in _SHELL_BLOCKED_PATTERNS:
        if re.search(pattern, command):
            return {"error": f"Command blocked by safety filter: matches '{pattern}'", "stdout": "", "stderr": "", "returncode": -1}

    timeout = max(1, min(timeout, 120))

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.expanduser("~"),
        )
        stdout = result.stdout[:10000]  # Cap output size
        stderr = result.stderr[:5000]
        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "stdout": "", "stderr": "", "returncode": -1}
    except Exception as e:
        return {"error": f"Execution failed: {type(e).__name__}: {e}", "stdout": "", "stderr": "", "returncode": -1}


# ── HTTP Fetch ──────────────────────────────────────────────────────────────

async def _http_fetch(url: str, method: str = "GET", headers: dict = None, body: str = None) -> dict:
    """Fetch a URL and return the response."""
    import aiohttp

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://", "status": 0, "body": ""}

    # Block internal network abuse (SSRF protection)
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if hostname in ("169.254.169.254", "metadata.google.internal"):
        return {"error": "Blocked: cloud metadata endpoint", "status": 0, "body": ""}

    method = method.upper()
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
        return {"error": f"Unsupported method: {method}", "status": 0, "body": ""}

    req_headers = headers or {}
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "OpenClaw-Army/3.0"

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            kwargs = {"headers": req_headers}
            if body:
                kwargs["data"] = body

            async with session.request(method, url, **kwargs) as resp:
                response_body = await resp.text()
                return {
                    "status": resp.status,
                    "body": response_body[:20000],  # Cap response size
                    "headers": dict(resp.headers),
                }
    except Exception as e:
        return {"error": f"Fetch failed: {type(e).__name__}: {e}", "status": 0, "body": ""}


# ── Package Management ─────────────────────────────────────────────────────

def _install_package(package: str, upgrade: bool = False) -> dict:
    """Install a Python package using pip. Returns stdout/stderr."""
    # Basic validation — only allow package-name-like strings
    if not re.match(r'^[a-zA-Z0-9_\-\.\[\],>=<! ]+$', package):
        return {"error": f"Invalid package specifier: {package}", "installed": False}
    cmd = [sys.executable, "-m", "pip", "install", "--quiet"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "installed": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:5000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "pip install timed out after 120s", "installed": False}
    except Exception as e:
        return {"error": f"Install failed: {e}", "installed": False}


# ── Self-Restart ───────────────────────────────────────────────────────────

async def _restart_self(reason: str = "requested") -> dict:
    """Restart the orchestrator, properly sourcing environment. Wrapper around _hot_reload."""
    log.info(f"Self-restart requested: {reason}")
    return await _hot_reload()


# ── Git Operations ─────────────────────────────────────────────────────────

def _git_command(command: str, cwd: str = None) -> dict:
    """Execute a git command in the project directory."""
    import shlex
    work_dir = cwd or ARMY_HOME
    # Parse the command — strip leading 'git' if user included it
    if command.strip().startswith("git "):
        command = command.strip()[4:]
    parts = shlex.split(command)
    try:
        result = subprocess.run(
            ["git"] + parts,
            cwd=work_dir, capture_output=True, text=True, timeout=60,
        )
        return {
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Git command timed out after 60s", "returncode": -1}
    except Exception as e:
        return {"error": f"Git failed: {e}", "returncode": -1}


# ── Backup System ──────────────────────────────────────────────────────────

def _create_backup(label: str = "") -> dict:
    """Create a timestamped backup of the data/ directory and main.py."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_safe = re.sub(r'[^a-zA-Z0-9_-]', '', label)[:30]
    backup_name = f"backup_{ts}_{label_safe}" if label_safe else f"backup_{ts}"
    backup_dir = Path(ARMY_HOME) / "backups" / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up = []
    # Backup data directory
    data_dir = Path(ARMY_HOME) / "data"
    if data_dir.exists():
        shutil.copytree(data_dir, backup_dir / "data", dirs_exist_ok=True)
        backed_up.append("data/")
    # Backup main.py
    shutil.copy2(_MAIN_PY_PATH, backup_dir / "main.py")
    backed_up.append("main.py")
    # Backup .env (redacted)
    env_file = Path(ARMY_HOME) / ".env"
    if env_file.exists():
        shutil.copy2(env_file, backup_dir / ".env")
        backed_up.append(".env")

    return {
        "created": True,
        "backup_path": str(backup_dir),
        "backed_up": backed_up,
        "label": label or backup_name,
    }


# ── Launchd Service Management ────────────────────────────────────────────

def _setup_launchd(action: str = "install") -> dict:
    """
    Install/uninstall a macOS launchd plist to auto-start the orchestrator.
    action: 'install', 'uninstall', or 'status'
    """
    plist_name = "com.openclaw.army.orchestrator"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{plist_name}.plist"
    python_path = sys.executable
    main_py = str(_MAIN_PY_PATH)
    env_file = str(Path(ARMY_HOME) / ".env")

    if action == "status":
        if plist_path.exists():
            # Check if loaded
            r = subprocess.run(["launchctl", "list", plist_name],
                               capture_output=True, text=True)
            loaded = r.returncode == 0
            return {"installed": True, "loaded": loaded, "plist_path": str(plist_path)}
        return {"installed": False, "loaded": False}

    if action == "uninstall":
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            return {"uninstalled": True}
        return {"uninstalled": False, "detail": "Plist not found"}

    if action == "install":
        # Build a shell wrapper that sources .env then runs python
        wrapper = Path(ARMY_HOME) / "bin" / "start-orchestrator.sh"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_text(f"""#!/bin/bash
set -a
[ -f "{env_file}" ] && source "{env_file}"
set +a
cd "{str(_MAIN_PY_PATH.parent)}"
exec "{python_path}" "{main_py}"
""")
        wrapper.chmod(0o755)

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{str(wrapper)}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/openclaw-orchestrator.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/openclaw-orchestrator.err</string>
    <key>WorkingDirectory</key>
    <string>{str(_MAIN_PY_PATH.parent)}</string>
</dict>
</plist>
"""
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content)
        # Load the plist
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
        return {"installed": True, "plist_path": str(plist_path), "wrapper": str(wrapper)}

    return {"error": f"Unknown action: {action}. Use 'install', 'uninstall', or 'status'."}


# ── File Operations ────────────────────────────────────────────────────────

def _read_file(path: str, start_line: int = None, end_line: int = None) -> dict:
    """Read a file's contents. Optionally specify a line range."""
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"File not found: {path}"}
    if not p.is_file():
        return {"error": f"Not a file: {path}"}
    try:
        content = p.read_text(errors="replace")
        lines = content.split("\n")
        total = len(lines)
        if start_line or end_line:
            s = max(0, (start_line or 1) - 1)
            e = min(total, end_line or total)
            return {"path": str(p), "start_line": s + 1, "end_line": e,
                    "total_lines": total, "content": "\n".join(lines[s:e])}
        # Cap at 50KB for safety
        return {"path": str(p), "total_lines": total, "content": content[:50000],
                "truncated": len(content) > 50000}
    except Exception as e:
        return {"error": f"Read failed: {e}"}


def _write_file(path: str, content: str, append: bool = False) -> dict:
    """Write content to a file. Creates parent directories if needed."""
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode) as f:
            f.write(content)
        return {"written": True, "path": str(p), "bytes": len(content.encode()),
                "mode": "append" if append else "overwrite"}
    except Exception as e:
        return {"written": False, "error": f"Write failed: {e}"}


def _list_files(path: str, pattern: str = "*", recursive: bool = False) -> dict:
    """List files in a directory, optionally with glob pattern."""
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"Path not found: {path}"}
    if not p.is_dir():
        return {"error": f"Not a directory: {path}"}
    try:
        if recursive:
            entries = list(p.rglob(pattern))[:500]
        else:
            entries = list(p.glob(pattern))[:500]
        files = []
        for e in sorted(entries):
            stat = e.stat()
            files.append({
                "name": str(e.relative_to(p)),
                "type": "dir" if e.is_dir() else "file",
                "size": stat.st_size if e.is_file() else 0,
            })
        return {"path": str(p), "count": len(files), "entries": files}
    except Exception as e:
        return {"error": f"List failed: {e}"}


# ── Scheduled Tasks (in-process) ──────────────────────────────────────────

_scheduled_tasks: dict[str, dict] = {}  # name -> {interval, handler_code, last_run, task}
_SCHEDULED_TASKS_PERSIST_PATH = Path(ARMY_HOME) / "data" / "scheduled_tasks.json"


def _save_scheduled_tasks_to_disk():
    """Persist scheduled task definitions so they survive restarts."""
    _SCHEDULED_TASKS_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tasks = {}
    for name, info in _scheduled_tasks.items():
        tasks[name] = {
            "interval": info["interval"],
            "handler_code": info["handler_code"],
            "created_at": info.get("created_at", ""),
        }
    _SCHEDULED_TASKS_PERSIST_PATH.write_text(json.dumps(tasks, indent=2))


async def _load_persisted_scheduled_tasks():
    """Reload scheduled tasks from disk after restart."""
    if not _SCHEDULED_TASKS_PERSIST_PATH.exists():
        return
    try:
        tasks = json.loads(_SCHEDULED_TASKS_PERSIST_PATH.read_text())
        for name, info in tasks.items():
            _schedule_task(name, info["interval"], info["handler_code"])
        log.info(f"Reloaded {len(tasks)} persisted scheduled tasks")
    except Exception as e:
        log.warning(f"Failed to reload scheduled tasks: {e}")


async def _run_scheduled_loop(name: str, interval: int, handler_code: str):
    """Background loop that executes handler_code every interval seconds."""
    wrapped = f"async def _scheduled_handler():\n" + textwrap.indent(handler_code, "    ")
    while name in _scheduled_tasks:
        try:
            safe_globals = {"__builtins__": __builtins__, "os": os, "sys": sys,
                            "subprocess": subprocess, "json": json, "re": re,
                            "Path": Path, "datetime": datetime, "timezone": timezone,
                            "asyncio": asyncio, "logging": logging, "time": time,
                            "shutil": shutil, "hashlib": hashlib}
            exec(wrapped, safe_globals)
            await safe_globals["_scheduled_handler"]()
        except Exception as e:
            log.error(f"Scheduled task '{name}' failed: {e}")
        _scheduled_tasks[name]["last_run"] = datetime.now(timezone.utc).isoformat()
        await asyncio.sleep(interval)


def _schedule_task(name: str, interval: int, handler_code: str) -> dict:
    """Schedule a recurring task. interval in seconds. handler_code is an async function body."""
    if interval < 10:
        return {"scheduled": False, "detail": "Minimum interval is 10 seconds"}
    # Validate syntax
    wrapped = f"async def _test():\n" + textwrap.indent(handler_code, "    ")
    ok, err = _validate_syntax(wrapped)
    if not ok:
        return {"scheduled": False, "detail": f"Handler syntax error: {err}"}
    # Cancel existing if re-scheduling
    if name in _scheduled_tasks and "task" in _scheduled_tasks[name]:
        _scheduled_tasks[name]["task"].cancel()
    task = asyncio.ensure_future(_run_scheduled_loop(name, interval, handler_code))
    _scheduled_tasks[name] = {
        "interval": interval, "handler_code": handler_code,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None, "task": task,
    }
    _save_scheduled_tasks_to_disk()
    return {"scheduled": True, "name": name, "interval": interval}


def _cancel_scheduled_task(name: str) -> dict:
    """Cancel a scheduled task."""
    if name not in _scheduled_tasks:
        return {"cancelled": False, "detail": f"No scheduled task named '{name}'"}
    if "task" in _scheduled_tasks[name]:
        _scheduled_tasks[name]["task"].cancel()
    del _scheduled_tasks[name]
    _save_scheduled_tasks_to_disk()
    return {"cancelled": True, "name": name}


def _list_scheduled_tasks() -> dict:
    """List all active scheduled tasks."""
    tasks = {}
    for name, info in _scheduled_tasks.items():
        tasks[name] = {
            "interval": info["interval"],
            "created_at": info.get("created_at"),
            "last_run": info.get("last_run"),
        }
    return {"tasks": tasks, "count": len(tasks)}


# ── Process Spawning ──────────────────────────────────────────────────────

def _spawn_process(command: str, name: str = "", cwd: str = None,
                   env_vars: dict = None) -> dict:
    """Spawn a long-running background process. Returns PID."""
    import shlex
    work_dir = cwd or ARMY_HOME
    env = os.environ.copy()
    # Source .env
    env_file = Path(ARMY_HOME) / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip("'\"")
    if env_vars:
        env.update(env_vars)
    try:
        parts = shlex.split(command)
        proc = subprocess.Popen(
            parts, cwd=work_dir, env=env,
            stdout=open(f"/tmp/openclaw-spawn-{name or 'unnamed'}.log", "w"),
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        return {"spawned": True, "pid": proc.pid, "name": name or command[:50],
                "command": command}
    except Exception as e:
        return {"spawned": False, "error": f"Spawn failed: {e}"}


# ── Environment Variable Management ──────────────────────────────────────

def _manage_env(action: str, key: str = "", value: str = "") -> dict:
    """Read, set, or list environment variables. Can also update .env file."""
    env_file = Path(ARMY_HOME) / ".env"

    if action == "get":
        val = os.environ.get(key, "")
        return {"key": key, "value": val, "exists": key in os.environ}

    if action == "list":
        # Return non-sensitive env vars
        safe_keys = {k: v[:20] + "..." if len(v) > 20 and ("KEY" in k or "SECRET" in k or "PASSWORD" in k or "TOKEN" in k) else v
                     for k, v in os.environ.items() if k.startswith(("ARMY", "ORCHESTRATOR", "NVAPI", "NVIDIA"))}
        return {"vars": safe_keys, "count": len(safe_keys)}

    if action == "set":
        if not key:
            return {"error": "Key is required"}
        # Set in current process
        os.environ[key] = value
        # Also update .env file for persistence
        if env_file.exists():
            lines = env_file.read_text().splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}")
            env_file.write_text("\n".join(lines) + "\n")
        else:
            env_file.write_text(f"{key}={value}\n")
        return {"set": True, "key": key, "persisted": True}

    return {"error": f"Unknown action: {action}. Use 'get', 'set', or 'list'."}


# ── Database Query ──────────────────────────────────────────────────────────

def _query_database(query: str, database: str = "postgres") -> dict:
    """Execute a SQL query against PostgreSQL via psql."""
    query_upper = query.strip().upper()
    for blocked in ["DROP DATABASE", "DROP SCHEMA"]:
        if blocked in query_upper:
            return {"error": f"Blocked destructive operation: {blocked}"}
    db_host = os.environ.get("POSTGRES_HOST", "localhost")
    db_port = os.environ.get("POSTGRES_PORT", "5432")
    db_user = os.environ.get("POSTGRES_USER", "postgres")
    db_password = os.environ.get("POSTGRES_PASSWORD", "")
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    try:
        cmd = ["psql", "-h", db_host, "-p", db_port, "-U", db_user, "-d", database,
               "-t", "-A", "-F", "\t", "-c", query]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        if result.returncode != 0:
            return {"error": result.stderr[:2000], "returncode": result.returncode}
        output = result.stdout.strip()
        if not output:
            return {"rows": [], "count": 0, "query": query[:200]}
        rows = [line.split("\t") for line in output.split("\n") if line.strip()]
        return {"rows": rows[:500], "count": len(rows), "query": query[:200]}
    except subprocess.TimeoutExpired:
        return {"error": "Query timed out after 30s"}
    except FileNotFoundError:
        return {"error": "psql not found — install PostgreSQL client tools"}
    except Exception as e:
        return {"error": f"Query failed: {e}"}


# ── Memory Service Integration ─────────────────────────────────────────────

async def _memory_store(content: str, category: str = "general",
                        importance: float = 0.7, tags: list = None) -> dict:
    """Store a memory in the Memory Service for long-term recall."""
    try:
        import aiohttp
        payload = {
            "agent_name": "orchestrator",
            "content": content,
            "category": category,
            "importance": importance,
            "metadata": {"source": "orchestrator-tool", "tags": tags or []},
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(f"{MEMORY_SERVICE_URL}/memory/commit", json=payload) as resp:
                if resp.status in (200, 201):
                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()
                    return {"stored": True, "detail": str(data)[:500]}
                return {"stored": False, "error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
    except Exception as e:
        return {"stored": False, "error": str(e)}


async def _memory_search(query: str, limit: int = 10, category: str = None) -> dict:
    """Search the Memory Service for relevant memories (vector + keyword)."""
    try:
        import aiohttp
        params = {"q": query, "limit": limit, "agent": "orchestrator"}
        if category:
            params["category"] = category
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{MEMORY_SERVICE_URL}/memory/search", params=params) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                    except Exception:
                        data = {"raw": (await resp.text())[:2000]}
                    results = data.get("results", data) if isinstance(data, dict) else data
                    return {"results": results, "count": len(results) if isinstance(results, list) else 1}
                return {"error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
    except Exception as e:
        return {"error": str(e)}


# ── Notification Service ───────────────────────────────────────────────────

async def _send_notification(to: str, subject: str, body: str,
                             notification_type: str = "email") -> dict:
    """Send an email or notification via the Notification Service."""
    try:
        import aiohttp
        payload = {
            "to": to,
            "subject": subject,
            "body": body,
            "type": notification_type,
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(f"{NOTIFICATION_SERVICE_URL}/send", json=payload) as resp:
                if resp.status in (200, 201, 202):
                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()
                    return {"sent": True, "detail": str(data)[:500]}
                return {"sent": False, "error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
    except Exception as e:
        return {"sent": False, "error": str(e)}


# ── Knowledge Bridge Integration ──────────────────────────────────────────

async def _knowledge_query(action: str, query: str = "", path: str = "",
                           content: str = "", tags: list = None) -> dict:
    """Interface with the Knowledge Bridge (Obsidian vault)."""
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            if action == "search":
                async with session.get(f"{KNOWLEDGE_BRIDGE_URL}/search",
                                       params={"q": query, "limit": 20}) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except Exception:
                            return {"result": (await resp.text())[:5000]}
                    return {"error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
            elif action == "read":
                async with session.get(f"{KNOWLEDGE_BRIDGE_URL}/notes/{path}") as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except Exception:
                            return {"content": (await resp.text())[:10000]}
                    return {"error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
            elif action == "write":
                payload = {"path": path, "content": content}
                if tags:
                    payload["tags"] = tags
                async with session.post(f"{KNOWLEDGE_BRIDGE_URL}/notes", json=payload) as resp:
                    if resp.status in (200, 201):
                        try:
                            return await resp.json()
                        except Exception:
                            return {"written": True}
                    return {"error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
            elif action == "list_tags":
                async with session.get(f"{KNOWLEDGE_BRIDGE_URL}/tags") as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except Exception:
                            return {"result": (await resp.text())[:5000]}
                    return {"error": f"HTTP {resp.status}: {(await resp.text())[:500]}"}
            return {"error": f"Unknown action: {action}. Use search, read, write, or list_tags."}
    except Exception as e:
        return {"error": str(e)}


# ── File Content Search ───────────────────────────────────────────────────

def _search_files(directory: str, pattern: str, file_pattern: str = "*",
                  max_results: int = 50, regex: bool = False) -> dict:
    """Search file contents in a directory. Like grep but as a tool."""
    d = Path(directory).expanduser()
    if not d.exists() or not d.is_dir():
        return {"error": f"Not a valid directory: {directory}"}

    if regex:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}
        match_fn = lambda line: compiled.search(line)
    else:
        pattern_lower = pattern.lower()
        match_fn = lambda line: pattern_lower in line.lower()

    results = []
    files_searched = 0
    skip_dirs = {".venv", "venv", "node_modules", ".git", "__pycache__", ".tox", "backups"}
    for f in d.rglob(file_pattern):
        if any(sd in f.parts for sd in skip_dirs):
            continue
        if not f.is_file() or f.stat().st_size > 1_000_000:  # Skip >1MB
            continue
        files_searched += 1
        try:
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if match_fn(line):
                    results.append({
                        "file": str(f.relative_to(d)),
                        "line": i,
                        "text": line.strip()[:200],
                    })
                    if len(results) >= max_results:
                        return {"results": results, "count": len(results),
                                "files_searched": files_searched, "truncated": True}
        except Exception:
            continue

    return {"results": results, "count": len(results),
            "files_searched": files_searched, "truncated": False}


# ── Process Management ────────────────────────────────────────────────────

def _manage_process(action: str, pid: int = 0, name: str = "") -> dict:
    """Manage spawned processes. Actions: status, kill, log, list."""
    import signal as sig

    if action == "status":
        if not pid:
            return {"error": "PID required for status check"}
        try:
            os.kill(pid, 0)  # Signal 0 = existence check
            return {"pid": pid, "alive": True}
        except ProcessLookupError:
            return {"pid": pid, "alive": False}
        except PermissionError:
            return {"pid": pid, "alive": True, "note": "Process exists but owned by another user"}

    elif action == "kill":
        if not pid:
            return {"error": "PID required for kill"}
        try:
            os.kill(pid, sig.SIGTERM)
            return {"killed": True, "pid": pid, "signal": "SIGTERM"}
        except ProcessLookupError:
            return {"killed": False, "error": "Process not found"}
        except Exception as e:
            return {"killed": False, "error": str(e)}

    elif action == "log":
        log_name = name or "unnamed"
        log_path = Path(f"/tmp/openclaw-spawn-{log_name}.log")
        if not log_path.exists():
            return {"error": f"Log not found: {log_path}"}
        try:
            content = log_path.read_text(errors="replace")
            return {"log": content[-5000:], "path": str(log_path),
                    "total_bytes": log_path.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    elif action == "list":
        logs = list(Path("/tmp").glob("openclaw-spawn-*.log"))
        processes = []
        for lp in logs:
            pname = lp.stem.replace("openclaw-spawn-", "")
            processes.append({"name": pname, "log_path": str(lp),
                              "size": lp.stat().st_size})
        return {"processes": processes, "count": len(processes)}

    return {"error": f"Unknown action: {action}. Use status, kill, log, or list."}


# ── Session Management ────────────────────────────────────────────────────

def _manage_sessions(action: str, session_id: str = "") -> dict:
    """Manage chat sessions. Actions: list, get, clear, clear_all, export."""
    if action == "list":
        sessions = []
        for sid, msgs in _chat_sessions.items():
            sessions.append({
                "session_id": sid,
                "message_count": len(msgs),
                "last_role": msgs[-1]["role"] if msgs else None,
            })
        return {"sessions": sessions, "count": len(sessions)}

    elif action == "get":
        if not session_id or session_id not in _chat_sessions:
            return {"error": f"Session '{session_id}' not found"}
        msgs = _chat_sessions[session_id]
        return {"session_id": session_id, "messages": msgs[-20:],
                "total_messages": len(msgs)}

    elif action == "clear":
        if session_id and session_id in _chat_sessions:
            del _chat_sessions[session_id]
            return {"cleared": True, "session_id": session_id}
        return {"cleared": False, "error": f"Session '{session_id}' not found"}

    elif action == "clear_all":
        count = len(_chat_sessions)
        _chat_sessions.clear()
        return {"cleared": True, "sessions_removed": count}

    elif action == "export":
        if not session_id or session_id not in _chat_sessions:
            return {"error": f"Session '{session_id}' not found"}
        msgs = _chat_sessions[session_id]
        export_path = Path(ARMY_HOME) / "data" / "exports" / f"session_{session_id}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps({"session_id": session_id, "messages": msgs}, indent=2))
        return {"exported": True, "path": str(export_path), "messages": len(msgs)}

    return {"error": f"Unknown action: {action}. Use list, get, clear, clear_all, or export."}


# ── WebSocket Broadcast ──────────────────────────────────────────────────

async def _broadcast_event(event_type: str, data: dict = None) -> dict:
    """Broadcast a custom event to all WebSocket subscribers."""
    if not ws_subscribers:
        return {"broadcast": False, "detail": "No WebSocket clients connected", "subscribers": 0}

    event = {"event": event_type, "data": data or {},
             "ts": datetime.now(timezone.utc).isoformat()}
    msg = json.dumps(event, default=str)
    sent = 0
    dead = []
    for ws in ws_subscribers:
        try:
            await ws.send_text(msg)
            sent += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_subscribers.remove(ws)
    return {"broadcast": True, "sent_to": sent, "failed": len(dead),
            "subscribers": len(ws_subscribers)}


# ── System Info ──────────────────────────────────────────────────────────

def _system_info() -> dict:
    """Get system runtime information: memory, CPU, disk, uptime, active tasks."""
    import platform
    info = {
        "pid": os.getpid(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": platform.node(),
        "army_home": ARMY_HOME,
        "main_py_lines": len(_MAIN_PY_PATH.read_text().splitlines()),
        "active_sessions": len(_chat_sessions),
        "active_workflows": len([w for w in workflows.values()
                                  if w.status in ("planning", "running", "waiting")]),
        "total_workflows": len(workflows),
        "scheduled_tasks": len(_scheduled_tasks),
        "dynamic_tools": len(_dynamic_tools),
        "dynamic_agents": len(_dynamic_agents),
        "prompt_sections": len(_prompt_sections),
        "quality_samples": len(_QUALITY_WINDOW),
        "ws_subscribers": len(ws_subscribers),
    }
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        info["memory_mb"] = round(rusage.ru_maxrss / 1024 / 1024, 1)
    except Exception:
        pass
    try:
        usage = shutil.disk_usage(ARMY_HOME)
        info["disk"] = {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
        }
    except Exception:
        pass
    try:
        result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        info["uptime"] = result.stdout.strip()
    except Exception:
        pass
    return info


# ── Eval Python (ad-hoc code execution) ───────────────────────────────────

async def _eval_python(code: str, timeout: int = 30) -> dict:
    """Execute arbitrary Python code and return stdout + return value."""
    # Wrap code so the last expression becomes the return value
    wrapped = (
        "import sys, os, json, re, math, datetime, pathlib, collections, itertools, functools, hashlib, base64, csv, io, random, time, subprocess, shutil, glob, fnmatch, textwrap, uuid\n"
        "from pathlib import Path\n"
        "from datetime import datetime, timezone, timedelta\n"
        "_result = None\n"
        f"{code}\n"
    )
    ok, err = _validate_syntax(wrapped)
    if not ok:
        return {"error": f"Syntax error: {err}", "stdout": "", "return_value": None}
    try:
        result = subprocess.run(
            [sys.executable, "-c", wrapped],
            capture_output=True, text=True, timeout=min(timeout, 120),
            cwd=ARMY_HOME,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
        )
        return {
            "stdout": result.stdout[:20000],
            "stderr": result.stderr[:5000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out after {timeout}s", "stdout": "", "returncode": -1}
    except Exception as e:
        return {"error": f"Execution failed: {e}", "stdout": "", "returncode": -1}


# ── Redis Command ─────────────────────────────────────────────────────────

def _redis_command(command: str, database: int = 0) -> dict:
    """Execute a Redis command via redis-cli."""
    cmd_upper = command.strip().upper()
    for blocked in ["FLUSHALL", "FLUSHDB", "SHUTDOWN", "DEBUG", "CONFIG SET"]:
        if cmd_upper.startswith(blocked):
            return {"error": f"Blocked destructive Redis command: {blocked}"}
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")
    try:
        result = subprocess.run(
            ["redis-cli", "-h", redis_host, "-p", redis_port, "-n", str(database)]
            + command.split(),
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {"error": result.stderr[:2000], "returncode": result.returncode}
        return {"output": result.stdout.strip()[:20000], "returncode": result.returncode}
    except FileNotFoundError:
        return {"error": "redis-cli not found — install Redis CLI tools"}
    except subprocess.TimeoutExpired:
        return {"error": "Redis command timed out after 15s"}
    except Exception as e:
        return {"error": f"Redis command failed: {e}"}


# ── Workflow Manifest CRUD ────────────────────────────────────────────────

def _manage_workflow_manifest(action: str, name: str = "", content: dict = None,
                              step_id: str = "", step_data: dict = None) -> dict:
    """Create, read, update, delete YAML workflow manifests."""
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

    if action == "list":
        _load_manifests()
        return {
            "manifests": [
                {"name": m.name, "description": m.description, "version": m.version,
                 "steps": len(m.steps)}
                for m in _manifest_cache.values()
            ],
            "count": len(_manifest_cache),
        }

    elif action == "get":
        _load_manifests()
        m = _manifest_cache.get(name)
        if not m:
            return {"error": f"Manifest '{name}' not found"}
        return m.model_dump()

    elif action == "create":
        if not name or not content:
            return {"error": "Name and content (dict with description, steps) required"}
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        path = WORKFLOWS_DIR / f"{safe_name}.yaml"
        manifest_data = {"name": name, **content}
        try:
            WorkflowManifest(**manifest_data)  # validate
        except Exception as e:
            return {"error": f"Invalid manifest: {e}"}
        path.write_text(yaml.dump(manifest_data, default_flow_style=False))
        _load_manifests()
        return {"created": True, "path": str(path), "name": name}

    elif action == "update":
        _load_manifests()
        if name not in _manifest_cache:
            return {"error": f"Manifest '{name}' not found"}
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        path = WORKFLOWS_DIR / f"{safe_name}.yaml"
        existing = yaml.safe_load(path.read_text()) if path.exists() else {}
        if content:
            existing.update(content)
        existing["name"] = name
        try:
            WorkflowManifest(**existing)  # validate
        except Exception as e:
            return {"error": f"Invalid manifest after update: {e}"}
        path.write_text(yaml.dump(existing, default_flow_style=False))
        _load_manifests()
        return {"updated": True, "name": name}

    elif action == "delete":
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        path = WORKFLOWS_DIR / f"{safe_name}.yaml"
        if not path.exists():
            return {"error": f"Manifest file not found for '{name}'"}
        path.unlink()
        _manifest_cache.pop(name, None)
        return {"deleted": True, "name": name}

    return {"error": f"Unknown action: {action}. Use list, get, create, update, delete."}


# ── Cron-Style Scheduling ────────────────────────────────────────────────

_cron_tasks: dict[str, dict] = {}  # name -> {schedule, handler_code, task}
_CRON_PERSIST_PATH = Path(ARMY_HOME) / "data" / "cron_tasks.json"


def _parse_cron_schedule(schedule: str) -> dict:
    """Parse a human-readable schedule into components.
    Formats: 'daily HH:MM', 'hourly :MM', 'weekly DAY HH:MM', 'every Nh Mm'
    """
    s = schedule.strip().lower()
    if s.startswith("daily"):
        parts = s.split()
        time_str = parts[1] if len(parts) > 1 else "00:00"
        h, m = map(int, time_str.split(":"))
        return {"type": "daily", "hour": h, "minute": m}
    elif s.startswith("hourly"):
        parts = s.split()
        minute = int(parts[1].lstrip(":")) if len(parts) > 1 else 0
        return {"type": "hourly", "minute": minute}
    elif s.startswith("weekly"):
        parts = s.split()
        day_names = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
                     "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                     "friday": 4, "saturday": 5, "sunday": 6}
        day = day_names.get(parts[1], 0) if len(parts) > 1 else 0
        time_str = parts[2] if len(parts) > 2 else "00:00"
        h, m = map(int, time_str.split(":"))
        return {"type": "weekly", "day": day, "hour": h, "minute": m}
    return {"type": "unknown", "raw": schedule}


async def _cron_loop(name: str, parsed: dict, handler_code: str):
    """Background loop that checks every 30s if it's time to run."""
    wrapped = f"async def _cron_handler():\n" + textwrap.indent(handler_code, "    ")
    safe_globals = {"__builtins__": __builtins__, "os": os, "sys": sys,
                    "subprocess": subprocess, "json": json, "re": re,
                    "Path": Path, "datetime": datetime, "timezone": timezone,
                    "asyncio": asyncio, "logging": logging, "time": time,
                    "shutil": shutil, "hashlib": hashlib}
    last_run_key = None
    while name in _cron_tasks:
        now = datetime.now()
        run_key = None
        should_run = False
        if parsed["type"] == "daily":
            run_key = f"{now.date()}"
            should_run = now.hour == parsed["hour"] and now.minute == parsed["minute"]
        elif parsed["type"] == "hourly":
            run_key = f"{now.date()}-{now.hour}"
            should_run = now.minute == parsed["minute"]
        elif parsed["type"] == "weekly":
            run_key = f"{now.isocalendar()[1]}-{now.weekday()}"
            should_run = now.weekday() == parsed["day"] and now.hour == parsed["hour"] and now.minute == parsed["minute"]
        if should_run and run_key != last_run_key:
            last_run_key = run_key
            try:
                exec(wrapped, safe_globals)
                await safe_globals["_cron_handler"]()
                _cron_tasks[name]["last_run"] = now.isoformat()
            except Exception as e:
                log.error(f"Cron task '{name}' failed: {e}")
        await asyncio.sleep(30)


def _cron_schedule(name: str, schedule: str, handler_code: str) -> dict:
    """Schedule a cron-style task. schedule: 'daily HH:MM', 'hourly :MM', 'weekly DAY HH:MM'."""
    parsed = _parse_cron_schedule(schedule)
    if parsed["type"] == "unknown":
        return {"scheduled": False, "detail": f"Unrecognized schedule format: {schedule}. Use 'daily HH:MM', 'hourly :MM', or 'weekly DAY HH:MM'."}
    wrapped = f"async def _test():\n" + textwrap.indent(handler_code, "    ")
    ok, err = _validate_syntax(wrapped)
    if not ok:
        return {"scheduled": False, "detail": f"Handler syntax error: {err}"}
    if name in _cron_tasks and "task" in _cron_tasks[name]:
        _cron_tasks[name]["task"].cancel()
    task = asyncio.ensure_future(_cron_loop(name, parsed, handler_code))
    _cron_tasks[name] = {
        "schedule": schedule, "parsed": parsed, "handler_code": handler_code,
        "created_at": datetime.now(timezone.utc).isoformat(), "last_run": None, "task": task,
    }
    _save_cron_tasks()
    return {"scheduled": True, "name": name, "schedule": schedule, "parsed": parsed}


def _cancel_cron_task(name: str) -> dict:
    if name not in _cron_tasks:
        return {"cancelled": False, "detail": f"No cron task named '{name}'"}
    if "task" in _cron_tasks[name]:
        _cron_tasks[name]["task"].cancel()
    del _cron_tasks[name]
    _save_cron_tasks()
    return {"cancelled": True, "name": name}


def _list_cron_tasks() -> dict:
    tasks = {}
    for name, info in _cron_tasks.items():
        tasks[name] = {"schedule": info["schedule"], "parsed": info.get("parsed"),
                       "created_at": info.get("created_at"), "last_run": info.get("last_run")}
    return {"tasks": tasks, "count": len(tasks)}


def _save_cron_tasks():
    _CRON_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tasks = {}
    for name, info in _cron_tasks.items():
        tasks[name] = {"schedule": info["schedule"], "handler_code": info["handler_code"],
                       "created_at": info.get("created_at", "")}
    _CRON_PERSIST_PATH.write_text(json.dumps(tasks, indent=2))


async def _load_persisted_cron_tasks():
    if not _CRON_PERSIST_PATH.exists():
        return
    try:
        tasks = json.loads(_CRON_PERSIST_PATH.read_text())
        for name, info in tasks.items():
            _cron_schedule(name, info["schedule"], info["handler_code"])
        log.info(f"Reloaded {len(tasks)} persisted cron tasks")
    except Exception as e:
        log.warning(f"Failed to reload cron tasks: {e}")


# ── Archive / Compression ────────────────────────────────────────────────

def _compress_archive(action: str, archive_path: str, source_path: str = "",
                      format: str = "zip") -> dict:
    """Create or extract archives. Formats: zip, tar.gz, tar.bz2."""
    archive_p = Path(archive_path).expanduser()
    source_p = Path(source_path).expanduser() if source_path else None

    if action == "create":
        if not source_p or not source_p.exists():
            return {"error": f"Source path not found: {source_path}"}
        archive_p.parent.mkdir(parents=True, exist_ok=True)
        try:
            if format == "zip":
                import zipfile
                with zipfile.ZipFile(str(archive_p), 'w', zipfile.ZIP_DEFLATED) as zf:
                    if source_p.is_file():
                        zf.write(source_p, source_p.name)
                    else:
                        for f in source_p.rglob("*"):
                            if f.is_file():
                                zf.write(f, f.relative_to(source_p.parent))
            elif format in ("tar.gz", "tar.bz2"):
                import tarfile
                mode = "w:gz" if format == "tar.gz" else "w:bz2"
                with tarfile.open(str(archive_p), mode) as tf:
                    tf.add(str(source_p), arcname=source_p.name)
            else:
                return {"error": f"Unsupported format: {format}. Use zip, tar.gz, or tar.bz2."}
            return {"created": True, "path": str(archive_p),
                    "size": archive_p.stat().st_size, "format": format}
        except Exception as e:
            return {"error": f"Archive creation failed: {e}"}

    elif action == "extract":
        if not archive_p.exists():
            return {"error": f"Archive not found: {archive_path}"}
        dest = source_p or archive_p.parent / archive_p.stem
        dest.mkdir(parents=True, exist_ok=True)
        try:
            if str(archive_p).endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(str(archive_p), 'r') as zf:
                    zf.extractall(str(dest))
                    return {"extracted": True, "destination": str(dest),
                            "files": len(zf.namelist())}
            elif str(archive_p).endswith((".tar.gz", ".tgz", ".tar.bz2")):
                import tarfile
                with tarfile.open(str(archive_p), 'r:*') as tf:
                    tf.extractall(str(dest), filter='data')
                    return {"extracted": True, "destination": str(dest),
                            "files": len(tf.getnames())}
            else:
                return {"error": "Cannot determine archive format from extension."}
        except Exception as e:
            return {"error": f"Extraction failed: {e}"}

    elif action == "list":
        if not archive_p.exists():
            return {"error": f"Archive not found: {archive_path}"}
        try:
            if str(archive_p).endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(str(archive_p), 'r') as zf:
                    return {"files": [{"name": i.filename, "size": i.file_size}
                                      for i in zf.infolist()[:200]]}
            elif str(archive_p).endswith((".tar.gz", ".tgz", ".tar.bz2")):
                import tarfile
                with tarfile.open(str(archive_p), 'r:*') as tf:
                    return {"files": [{"name": m.name, "size": m.size}
                                      for m in tf.getmembers()[:200]]}
            return {"error": "Cannot determine archive format."}
        except Exception as e:
            return {"error": f"List failed: {e}"}

    return {"error": f"Unknown action: {action}. Use create, extract, or list."}


# ── File Diff ─────────────────────────────────────────────────────────────

def _diff_files(path_a: str = "", path_b: str = "", text_a: str = "",
                text_b: str = "", context_lines: int = 3) -> dict:
    """Generate unified diff between two files or two text strings."""
    import difflib
    try:
        if path_a and path_b:
            a_path = Path(path_a).expanduser()
            b_path = Path(path_b).expanduser()
            if not a_path.exists():
                return {"error": f"File not found: {path_a}"}
            if not b_path.exists():
                return {"error": f"File not found: {path_b}"}
            lines_a = a_path.read_text(errors="replace").splitlines(keepends=True)
            lines_b = b_path.read_text(errors="replace").splitlines(keepends=True)
            label_a, label_b = str(a_path), str(b_path)
        elif text_a is not None and text_b is not None:
            lines_a = text_a.splitlines(keepends=True)
            lines_b = text_b.splitlines(keepends=True)
            label_a, label_b = "text_a", "text_b"
        else:
            return {"error": "Provide either (path_a, path_b) or (text_a, text_b)"}

        diff = list(difflib.unified_diff(lines_a, lines_b,
                                         fromfile=label_a, tofile=label_b,
                                         n=context_lines))
        if not diff:
            return {"identical": True, "diff": "", "changes": 0}
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        return {
            "identical": False,
            "diff": "".join(diff)[:30000],
            "added_lines": added,
            "removed_lines": removed,
            "changes": added + removed,
        }
    except Exception as e:
        return {"error": f"Diff failed: {e}"}


# ── Webhook Registration ─────────────────────────────────────────────────

_webhooks: dict[str, dict] = {}  # path -> {handler_code, created_at, call_count}


def _register_webhook(path: str, handler_code: str, description: str = "") -> dict:
    """Register a dynamic webhook endpoint at /webhook/{path}."""
    if not path:
        return {"error": "Path is required"}
    safe_path = re.sub(r'[^a-zA-Z0-9_/-]', '', path).strip("/")
    wrapped = f"async def _test(request_data):\n" + textwrap.indent(handler_code, "    ")
    ok, err = _validate_syntax(wrapped)
    if not ok:
        return {"error": f"Handler syntax error: {err}"}
    _webhooks[safe_path] = {
        "handler_code": handler_code,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "call_count": 0,
    }
    return {"registered": True, "endpoint": f"/webhook/{safe_path}",
            "description": description}


def _unregister_webhook(path: str) -> dict:
    safe_path = re.sub(r'[^a-zA-Z0-9_/-]', '', path).strip("/")
    if safe_path in _webhooks:
        del _webhooks[safe_path]
        return {"removed": True, "path": safe_path}
    return {"removed": False, "detail": f"No webhook at path '{safe_path}'"}


def _list_webhooks() -> dict:
    hooks = []
    for path, info in _webhooks.items():
        hooks.append({"path": f"/webhook/{path}", "description": info.get("description", ""),
                      "created_at": info.get("created_at"), "call_count": info.get("call_count", 0)})
    return {"webhooks": hooks, "count": len(hooks)}


@app.post("/webhook/{path:path}")
@app.get("/webhook/{path:path}")
async def handle_webhook(path: str):
    """Handle incoming webhook calls on dynamic endpoints."""
    from starlette.requests import Request
    import inspect
    if path not in _webhooks:
        raise HTTPException(404, f"No webhook registered at /webhook/{path}")
    hook = _webhooks[path]
    hook["call_count"] = hook.get("call_count", 0) + 1
    handler_code = hook["handler_code"]
    wrapped = f"async def _handler(request_data):\n" + textwrap.indent(handler_code, "    ")
    safe_globals = {
        "__builtins__": __builtins__, "os": os, "sys": sys, "subprocess": subprocess,
        "json": json, "re": re, "Path": Path, "datetime": datetime, "timezone": timezone,
        "asyncio": asyncio, "logging": logging, "time": time,
    }
    try:
        exec(wrapped, safe_globals)
        result = await safe_globals["_handler"]({"path": path, "call_count": hook["call_count"]})
        return {"result": str(result) if result else "ok"}
    except Exception as e:
        return {"error": str(e)}


# ── macOS Clipboard ──────────────────────────────────────────────────────

def _clipboard(action: str, content: str = "") -> dict:
    """Read or write the macOS clipboard (pasteboard)."""
    if action == "read":
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return {"content": result.stdout[:50000], "length": len(result.stdout)}
        except FileNotFoundError:
            return {"error": "pbpaste not found — not on macOS?"}
        except Exception as e:
            return {"error": f"Clipboard read failed: {e}"}
    elif action == "write":
        if not content:
            return {"error": "Content required for write"}
        try:
            result = subprocess.run(["pbcopy"], input=content, capture_output=True, text=True, timeout=5)
            return {"written": True, "length": len(content)}
        except FileNotFoundError:
            return {"error": "pbcopy not found — not on macOS?"}
        except Exception as e:
            return {"error": f"Clipboard write failed: {e}"}
    return {"error": f"Unknown action: {action}. Use 'read' or 'write'."}


# ── Direct Agent Messaging ───────────────────────────────────────────────

async def _agent_message(agent_name: str, message: str, timeout: int = 60) -> dict:
    """Send a direct message to any agent and get its response."""
    port = AGENT_PORTS.get(agent_name)
    if not port:
        da = _dynamic_agents.get(agent_name)
        if da:
            port = da["port"]
        else:
            return {"error": f"Unknown agent: {agent_name}. Available: {list(AGENT_PORTS.keys())}"}
    token = AGENT_TOKENS.get(agent_name, "")
    try:
        import aiohttp
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "model": "openclaw",
            "messages": [{"role": "user", "content": message}],
            "user": "orchestrator-direct",
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.post(f"http://127.0.0.1:{port}/v1/chat/completions",
                                    json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status in (200, 201):
                    try:
                        data = json.loads(body)
                        agent_response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return {"agent": agent_name, "response": agent_response[:5000],
                                "status": resp.status}
                    except (json.JSONDecodeError, IndexError):
                        return {"agent": agent_name, "response": body[:5000], "status": resp.status}
                return {"agent": agent_name, "error": f"HTTP {resp.status}: {body[:1000]}",
                        "status": resp.status}
    except Exception as e:
        return {"agent": agent_name, "error": f"{type(e).__name__}: {str(e)[:500]}"}


# ── Structured Config Editing ────────────────────────────────────────────

def _manage_config(action: str, path: str, key_path: str = "", value = None) -> dict:
    """Read/write structured JSON/YAML config files with dot-notation key paths.
    Actions: 'get' (read key), 'set' (write key), 'delete' (remove key), 'view' (show full file).
    key_path uses dots: 'gateway.auth.token', 'server.port', etc.
    """
    p = Path(path).expanduser()

    def _load_config(p):
        text = p.read_text()
        if p.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text) or {}
        return json.loads(text)

    def _save_config(p, data):
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix in (".yaml", ".yml"):
            p.write_text(yaml.dump(data, default_flow_style=False))
        else:
            p.write_text(json.dumps(data, indent=2))

    def _get_nested(data, keys):
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            elif isinstance(data, list) and k.isdigit():
                data = data[int(k)] if int(k) < len(data) else None
            else:
                return None
        return data

    def _set_nested(data, keys, val):
        for k in keys[:-1]:
            if isinstance(data, dict):
                data = data.setdefault(k, {})
            else:
                return False
        if isinstance(data, dict):
            data[keys[-1]] = val
            return True
        return False

    def _del_nested(data, keys):
        for k in keys[:-1]:
            if isinstance(data, dict):
                data = data.get(k, {})
            else:
                return False
        if isinstance(data, dict) and keys[-1] in data:
            del data[keys[-1]]
            return True
        return False

    if action == "view":
        if not p.exists():
            return {"error": f"File not found: {path}"}
        try:
            data = _load_config(p)
            return {"path": str(p), "data": data}
        except Exception as e:
            return {"error": f"Failed to parse: {e}"}

    elif action == "get":
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not key_path:
            return {"error": "key_path required for get"}
        try:
            data = _load_config(p)
            val = _get_nested(data, key_path.split("."))
            return {"key": key_path, "value": val, "exists": val is not None}
        except Exception as e:
            return {"error": f"Read failed: {e}"}

    elif action == "set":
        if not key_path:
            return {"error": "key_path required for set"}
        try:
            data = _load_config(p) if p.exists() else {}
            ok = _set_nested(data, key_path.split("."), value)
            if not ok:
                return {"error": f"Cannot set nested key: {key_path}"}
            _save_config(p, data)
            return {"set": True, "key": key_path, "path": str(p)}
        except Exception as e:
            return {"error": f"Write failed: {e}"}

    elif action == "delete":
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not key_path:
            return {"error": "key_path required for delete"}
        try:
            data = _load_config(p)
            ok = _del_nested(data, key_path.split("."))
            if not ok:
                return {"error": f"Key not found: {key_path}"}
            _save_config(p, data)
            return {"deleted": True, "key": key_path, "path": str(p)}
        except Exception as e:
            return {"error": f"Delete failed: {e}"}

    return {"error": f"Unknown action: {action}. Use view, get, set, delete."}


# ── Log Query & Analysis ─────────────────────────────────────────────────

def _log_query(action: str, source: str = "", pattern: str = "",
               hours: float = 0, limit: int = 100, regex: bool = False) -> dict:
    """Query, analyze, tail, and rotate log files across all services.
    Actions: 'tail' (last N lines), 'search' (pattern match with time filter),
    'stats' (summary stats), 'rotate' (compress old logs), 'list' (available log files).
    Sources: 'activity', 'quality', 'failures', 'orchestrator', or a file path.
    """
    LOG_SOURCES = {
        "activity": Path(ARMY_HOME) / "data" / "logs" / "activity.jsonl",
        "quality": Path(ARMY_HOME) / "data" / "logs" / "quality.jsonl",
        "failures": Path(ARMY_HOME) / "data" / "logs" / "failures.jsonl",
        "orchestrator": Path(ARMY_HOME) / "data" / "logs" / "orchestrator.log",
    }

    if action == "list":
        log_dir = Path(ARMY_HOME) / "data" / "logs"
        files = []
        if log_dir.exists():
            for f in sorted(log_dir.iterdir()):
                if f.is_file():
                    files.append({"name": f.name, "size": f.stat().st_size,
                                  "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()})
        return {"files": files, "count": len(files), "log_dir": str(log_dir)}

    # Resolve source path
    log_path = LOG_SOURCES.get(source, Path(source).expanduser() if source else None)
    if not log_path or not log_path.exists():
        return {"error": f"Log source not found: {source}. Available: {list(LOG_SOURCES.keys())}"}

    if action == "tail":
        try:
            lines = log_path.read_text(errors="replace").strip().split("\n")
            tail_lines = lines[-min(limit, len(lines)):]
            entries = []
            for line in tail_lines:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({"raw": line})
            return {"entries": entries, "count": len(entries), "source": source}
        except Exception as e:
            return {"error": f"Tail failed: {e}"}

    elif action == "search":
        try:
            if regex:
                compiled = re.compile(pattern, re.IGNORECASE)
                match_fn = lambda line: compiled.search(line)
            else:
                pattern_lower = pattern.lower()
                match_fn = lambda line: pattern_lower in line.lower()
            cutoff_ts = None
            if hours > 0:
                cutoff_ts = (datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)).isoformat()
            matches = []
            for line in log_path.read_text(errors="replace").strip().split("\n"):
                if not line.strip():
                    continue
                if cutoff_ts:
                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts", entry.get("timestamp", ""))
                        if ts and ts < cutoff_ts:
                            continue
                    except json.JSONDecodeError:
                        pass
                if match_fn(line):
                    try:
                        matches.append(json.loads(line))
                    except json.JSONDecodeError:
                        matches.append({"raw": line})
                    if len(matches) >= limit:
                        break
            return {"matches": matches, "count": len(matches), "source": source,
                    "pattern": pattern, "hours_filter": hours}
        except Exception as e:
            return {"error": f"Search failed: {e}"}

    elif action == "stats":
        try:
            lines = log_path.read_text(errors="replace").strip().split("\n")
            total = len(lines)
            size = log_path.stat().st_size
            types = Counter()
            for line in lines[-500:]:
                try:
                    entry = json.loads(line)
                    types[entry.get("type", entry.get("category", "unknown"))] += 1
                except json.JSONDecodeError:
                    types["unparseable"] += 1
            return {"total_lines": total, "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "recent_type_distribution": dict(types.most_common(20)),
                    "source": source}
        except Exception as e:
            return {"error": f"Stats failed: {e}"}

    elif action == "rotate":
        try:
            size = log_path.stat().st_size
            if size < 1_000_000:
                return {"rotated": False, "detail": f"Log is only {size} bytes, no rotation needed (threshold: 1MB)"}
            import gzip
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = log_path.parent / f"{log_path.stem}_{ts}{log_path.suffix}.gz"
            with open(log_path, "rb") as f_in:
                with gzip.open(str(archive_path), "wb") as f_out:
                    f_out.write(f_in.read())
            log_path.write_text("")
            return {"rotated": True, "archive": str(archive_path),
                    "original_size": size, "source": source}
        except Exception as e:
            return {"error": f"Rotate failed: {e}"}

    return {"error": f"Unknown action: {action}. Use tail, search, stats, rotate, or list."}


# ── Network Probe ─────────────────────────────────────────────────────────

def _network_probe(action: str, target: str = "", port: int = 0,
                   timeout: int = 5) -> dict:
    """Network diagnostics: DNS lookup, ping, port check, local info.
    Actions: 'dns' (resolve hostname), 'ping' (ICMP ping), 'port_check' (TCP connect),
    'local_info' (local IPs, hostname), 'traceroute' (trace route to host).
    """
    if action == "dns":
        if not target:
            return {"error": "Target hostname required"}
        try:
            import socket
            results = socket.getaddrinfo(target, None)
            ips = list(set(r[4][0] for r in results))
            return {"hostname": target, "ips": ips, "count": len(ips)}
        except Exception as e:
            return {"error": f"DNS lookup failed: {e}"}

    elif action == "ping":
        if not target:
            return {"error": "Target required"}
        try:
            result = subprocess.run(
                ["ping", "-c", "3", "-W", str(timeout * 1000), target],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            return {"target": target, "stdout": result.stdout[:5000],
                    "success": result.returncode == 0, "returncode": result.returncode}
        except subprocess.TimeoutExpired:
            return {"target": target, "success": False, "error": "Ping timed out"}
        except Exception as e:
            return {"error": f"Ping failed: {e}"}

    elif action == "port_check":
        if not target or not port:
            return {"error": "Target and port required"}
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((target, port))
            sock.close()
            return {"target": target, "port": port, "open": result == 0,
                    "result_code": result}
        except Exception as e:
            return {"error": f"Port check failed: {e}"}

    elif action == "local_info":
        try:
            import socket
            hostname = socket.gethostname()
            try:
                local_ip = socket.gethostbyname(hostname)
            except Exception:
                local_ip = "unknown"
            # Get all interface IPs
            ips = []
            try:
                result = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("inet ") and "127.0.0.1" not in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            ips.append(parts[1])
            except Exception:
                pass
            return {"hostname": hostname, "local_ip": local_ip,
                    "interface_ips": ips}
        except Exception as e:
            return {"error": f"Local info failed: {e}"}

    elif action == "traceroute":
        if not target:
            return {"error": "Target required"}
        try:
            result = subprocess.run(
                ["traceroute", "-m", "15", "-w", str(timeout), target],
                capture_output=True, text=True, timeout=timeout * 16,
            )
            return {"target": target, "stdout": result.stdout[:10000],
                    "returncode": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": "Traceroute timed out"}
        except FileNotFoundError:
            return {"error": "traceroute not found — install with: brew install traceroute"}
        except Exception as e:
            return {"error": f"Traceroute failed: {e}"}

    return {"error": f"Unknown action: {action}. Use dns, ping, port_check, local_info, traceroute."}


# ── Data Transform ────────────────────────────────────────────────────────

def _data_transform(action: str, data: str = "", from_format: str = "",
                    to_format: str = "", query: str = "", path: str = "") -> dict:
    """Convert between CSV, JSON, YAML, TOML. Apply JQ-like queries on JSON.
    Actions: 'convert' (format conversion), 'query' (JQ-style JSON query),
    'detect' (detect data format), 'validate' (validate format).
    """
    if action == "detect":
        text = data or (Path(path).expanduser().read_text() if path else "")
        if not text.strip():
            return {"error": "No data provided"}
        text_stripped = text.strip()
        if text_stripped.startswith(("{", "[")):
            try:
                json.loads(text_stripped)
                return {"format": "json", "valid": True}
            except json.JSONDecodeError:
                return {"format": "json", "valid": False, "detail": "Looks like JSON but invalid"}
        if ":" in text_stripped.split("\n")[0] and not text_stripped.startswith(","):
            try:
                yaml.safe_load(text_stripped)
                return {"format": "yaml", "valid": True}
            except Exception:
                pass
        if "," in text_stripped.split("\n")[0]:
            return {"format": "csv", "valid": True}
        return {"format": "unknown", "valid": False}

    elif action == "convert":
        text = data or (Path(path).expanduser().read_text() if path else "")
        if not text.strip():
            return {"error": "No data provided"}
        # Parse source
        parsed = None
        try:
            if from_format == "json":
                parsed = json.loads(text)
            elif from_format == "yaml":
                parsed = yaml.safe_load(text)
            elif from_format == "csv":
                import csv as csv_mod
                import io
                reader = csv_mod.DictReader(io.StringIO(text))
                parsed = list(reader)
            elif from_format == "toml":
                try:
                    import tomllib
                    parsed = tomllib.loads(text)
                except ImportError:
                    return {"error": "TOML parsing requires Python 3.11+ (tomllib)"}
            else:
                return {"error": f"Unsupported from_format: {from_format}. Use json, yaml, csv, toml."}
        except Exception as e:
            return {"error": f"Failed to parse {from_format}: {e}"}
        # Serialize to target
        try:
            if to_format == "json":
                result = json.dumps(parsed, indent=2, default=str)
            elif to_format == "yaml":
                result = yaml.dump(parsed, default_flow_style=False)
            elif to_format == "csv":
                import csv as csv_mod
                import io
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    output = io.StringIO()
                    writer = csv_mod.DictWriter(output, fieldnames=parsed[0].keys())
                    writer.writeheader()
                    writer.writerows(parsed)
                    result = output.getvalue()
                else:
                    return {"error": "CSV output requires a list of dicts"}
            else:
                return {"error": f"Unsupported to_format: {to_format}. Use json, yaml, csv."}
            return {"output": result[:50000], "from": from_format, "to": to_format,
                    "truncated": len(result) > 50000}
        except Exception as e:
            return {"error": f"Failed to serialize to {to_format}: {e}"}

    elif action == "query":
        text = data or (Path(path).expanduser().read_text() if path else "")
        if not text.strip() or not query:
            return {"error": "Both data and query are required"}
        try:
            obj = json.loads(text) if isinstance(text, str) else text
            # Simple JQ-style query: .key, .key.subkey, .[0], .key[0].sub, .[] (iterate)
            parts = [p for p in re.split(r'\.(?![^\[]*\])', query.lstrip(".")) if p]
            current = obj
            for part in parts:
                if part == "[]":
                    if isinstance(current, list):
                        current = current  # keep as list
                    else:
                        return {"error": f"Cannot iterate non-list with .[]"}
                elif "[" in part:
                    key_part, idx_part = part.split("[", 1)
                    idx = int(idx_part.rstrip("]"))
                    if key_part:
                        current = current[key_part]
                    current = current[idx]
                elif isinstance(current, dict):
                    current = current[part]
                elif isinstance(current, list):
                    current = [item.get(part) if isinstance(item, dict) else None for item in current]
                else:
                    return {"error": f"Cannot navigate '{part}' in {type(current).__name__}"}
            return {"result": current, "query": query}
        except (KeyError, IndexError, TypeError) as e:
            return {"error": f"Query failed: {e}"}
        except Exception as e:
            return {"error": f"Query error: {e}"}

    elif action == "validate":
        text = data or (Path(path).expanduser().read_text() if path else "")
        fmt = from_format or "json"
        try:
            if fmt == "json":
                json.loads(text)
            elif fmt == "yaml":
                yaml.safe_load(text)
            elif fmt == "csv":
                import csv as csv_mod
                import io
                list(csv_mod.reader(io.StringIO(text)))
            else:
                return {"error": f"Unsupported format: {fmt}"}
            return {"valid": True, "format": fmt}
        except Exception as e:
            return {"valid": False, "format": fmt, "error": str(e)}

    return {"error": f"Unknown action: {action}. Use convert, query, detect, validate."}


# ── Hash / Encode Utility ────────────────────────────────────────────────

def _hash_encode(action: str, data: str = "", algorithm: str = "sha256",
                 path: str = "", length: int = 32) -> dict:
    """Compute hashes, encode/decode data, generate secure tokens.
    Actions: 'hash' (SHA256/MD5/etc), 'base64_encode', 'base64_decode',
    'url_encode', 'url_decode', 'hex_encode', 'hex_decode', 'generate_token'.
    """
    import base64
    from urllib.parse import quote, unquote

    if action == "hash":
        text = data
        if path:
            try:
                text = Path(path).expanduser().read_bytes()
            except Exception as e:
                return {"error": f"Cannot read file: {e}"}
        if isinstance(text, str):
            text = text.encode()
        try:
            h = hashlib.new(algorithm)
            h.update(text)
            return {"hash": h.hexdigest(), "algorithm": algorithm,
                    "input_length": len(text)}
        except ValueError:
            return {"error": f"Unsupported algorithm: {algorithm}. Use md5, sha1, sha256, sha512."}

    elif action == "base64_encode":
        return {"encoded": base64.b64encode(data.encode()).decode(),
                "input_length": len(data)}

    elif action == "base64_decode":
        try:
            return {"decoded": base64.b64decode(data).decode(errors="replace"),
                    "input_length": len(data)}
        except Exception as e:
            return {"error": f"Base64 decode failed: {e}"}

    elif action == "url_encode":
        return {"encoded": quote(data, safe=""), "input_length": len(data)}

    elif action == "url_decode":
        return {"decoded": unquote(data), "input_length": len(data)}

    elif action == "hex_encode":
        return {"encoded": data.encode().hex(), "input_length": len(data)}

    elif action == "hex_decode":
        try:
            return {"decoded": bytes.fromhex(data).decode(errors="replace"),
                    "input_length": len(data)}
        except Exception as e:
            return {"error": f"Hex decode failed: {e}"}

    elif action == "generate_token":
        import secrets
        token = secrets.token_urlsafe(length)
        return {"token": token, "length": len(token), "requested_bytes": length}

    return {"error": f"Unknown action: {action}. Use hash, base64_encode, base64_decode, url_encode, url_decode, hex_encode, hex_decode, generate_token."}


# ── Screenshot (macOS) ───────────────────────────────────────────────────

def _screenshot(action: str = "full", output_path: str = "",
                window_name: str = "", region: str = "") -> dict:
    """Capture macOS screenshots using screencapture.
    Actions: 'full' (entire screen), 'window' (interactive window select),
    'region' (x,y,w,h), 'list_windows' (list open windows).
    """
    if action == "list_windows":
        try:
            script = 'tell application "System Events" to get name of every process whose background only is false'
            result = subprocess.run(["osascript", "-e", script],
                                    capture_output=True, text=True, timeout=10)
            windows = [w.strip() for w in result.stdout.split(",") if w.strip()]
            return {"windows": windows, "count": len(windows)}
        except Exception as e:
            return {"error": f"Failed to list windows: {e}"}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        output_path = f"/tmp/screenshot_{ts}.png"
    p = Path(output_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        if action == "full":
            subprocess.run(["screencapture", "-x", str(p)],
                           capture_output=True, timeout=10)
        elif action == "window":
            if window_name:
                # Bring window to front then capture
                script = f'tell application "{window_name}" to activate'
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
                import time as _time
                _time.sleep(0.5)
                subprocess.run(["screencapture", "-x", "-l",
                                str(subprocess.run(["osascript", "-e",
                                    f'tell application "System Events" to get id of window 1 of process "{window_name}"'],
                                    capture_output=True, text=True, timeout=5).stdout.strip()),
                                str(p)], capture_output=True, timeout=10)
            else:
                subprocess.run(["screencapture", "-x", "-w", str(p)],
                               capture_output=True, timeout=30)
        elif action == "region":
            if region:
                # region = "x,y,w,h"
                parts = [int(x.strip()) for x in region.split(",")]
                if len(parts) == 4:
                    x, y, w, h = parts
                    subprocess.run(["screencapture", "-x", "-R",
                                    f"{x},{y},{w},{h}", str(p)],
                                   capture_output=True, timeout=10)
                else:
                    return {"error": "Region must be 'x,y,w,h'"}
            else:
                subprocess.run(["screencapture", "-x", "-s", str(p)],
                               capture_output=True, timeout=60)
        else:
            return {"error": f"Unknown action: {action}. Use full, window, region, list_windows."}

        if p.exists():
            return {"captured": True, "path": str(p), "size": p.stat().st_size}
        return {"captured": False, "detail": "Screenshot file not created"}
    except subprocess.TimeoutExpired:
        return {"error": "Screenshot timed out"}
    except Exception as e:
        return {"error": f"Screenshot failed: {e}"}


# ── Template Rendering ────────────────────────────────────────────────────

def _render_template(template: str = "", template_path: str = "",
                     variables: dict = None, output_path: str = "") -> dict:
    """Render Jinja2-style templates with variables.
    Provide template as string or path. Variables dict is applied.
    Optionally write rendered output to output_path.
    """
    if not template and template_path:
        tp = Path(template_path).expanduser()
        if not tp.exists():
            return {"error": f"Template file not found: {template_path}"}
        template = tp.read_text()
    if not template:
        return {"error": "Template string or template_path required"}
    variables = variables or {}
    try:
        from jinja2 import Environment, BaseLoader, StrictUndefined
        env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
        tmpl = env.from_string(template)
        rendered = tmpl.render(**variables)
    except ImportError:
        # Fallback to Python's string.Template
        from string import Template
        try:
            tmpl = Template(template)
            rendered = tmpl.safe_substitute(**variables)
        except Exception as e:
            return {"error": f"Template render failed (no Jinja2, using string.Template): {e}"}
    except Exception as e:
        return {"error": f"Template render failed: {e}"}

    if output_path:
        op = Path(output_path).expanduser()
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(rendered)

    return {"rendered": rendered[:50000], "length": len(rendered),
            "variables_used": list(variables.keys()),
            "output_path": output_path if output_path else None,
            "truncated": len(rendered) > 50000}


# ── Text Processing Toolkit ──────────────────────────────────────────────

def _text_process(action: str, text: str = "", pattern: str = "",
                  replacement: str = "", flags: str = "") -> dict:
    """Swiss-army text processing tool.
    Actions: 'regex_test' (test pattern against text), 'regex_replace' (find & replace),
    'regex_extract' (extract all matches), 'stats' (word/line/char counts),
    'case' (upper/lower/title/capitalize), 'slug' (URL-safe slug),
    'lines' (split/join/dedup/sort/reverse), 'truncate' (smart truncation).
    """
    if action == "regex_test":
        try:
            re_flags = 0
            if "i" in flags:
                re_flags |= re.IGNORECASE
            if "m" in flags:
                re_flags |= re.MULTILINE
            if "s" in flags:
                re_flags |= re.DOTALL
            match = re.search(pattern, text, re_flags)
            if match:
                return {"matches": True, "match": match.group(),
                        "groups": list(match.groups()), "span": list(match.span())}
            return {"matches": False}
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

    elif action == "regex_replace":
        try:
            re_flags = re.IGNORECASE if "i" in flags else 0
            result = re.sub(pattern, replacement, text, flags=re_flags)
            changes = len(re.findall(pattern, text, re_flags))
            return {"result": result[:50000], "replacements": changes}
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

    elif action == "regex_extract":
        try:
            re_flags = re.IGNORECASE if "i" in flags else 0
            matches = re.findall(pattern, text, re_flags)
            return {"matches": matches[:500], "count": len(matches)}
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

    elif action == "stats":
        lines = text.split("\n")
        words = text.split()
        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", ""))
        sentences = len(re.split(r'[.!?]+', text))
        paragraphs = len([p for p in text.split("\n\n") if p.strip()])
        return {"characters": chars, "characters_no_spaces": chars_no_space,
                "words": len(words), "lines": len(lines), "sentences": sentences,
                "paragraphs": paragraphs,
                "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 1)}

    elif action == "case":
        mode = pattern or "lower"
        if mode == "upper":
            return {"result": text.upper()}
        elif mode == "lower":
            return {"result": text.lower()}
        elif mode == "title":
            return {"result": text.title()}
        elif mode == "capitalize":
            return {"result": text.capitalize()}
        elif mode == "swap":
            return {"result": text.swapcase()}
        return {"error": f"Unknown case mode: {mode}. Use upper, lower, title, capitalize, swap."}

    elif action == "slug":
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return {"slug": slug}

    elif action == "lines":
        mode = pattern or "split"
        lines = text.split("\n")
        if mode == "split":
            return {"lines": lines, "count": len(lines)}
        elif mode == "dedup":
            seen = set()
            unique = []
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    unique.append(line)
            return {"result": "\n".join(unique), "original": len(lines),
                    "unique": len(unique), "removed": len(lines) - len(unique)}
        elif mode == "sort":
            return {"result": "\n".join(sorted(lines))}
        elif mode == "reverse":
            return {"result": "\n".join(reversed(lines))}
        elif mode == "join":
            return {"result": replacement.join(lines) if replacement else " ".join(lines)}
        return {"error": f"Unknown lines mode: {mode}. Use split, dedup, sort, reverse, join."}

    elif action == "truncate":
        max_len = int(pattern) if pattern and pattern.isdigit() else 100
        if len(text) <= max_len:
            return {"result": text, "truncated": False}
        return {"result": text[:max_len - 3] + "...", "truncated": True,
                "original_length": len(text)}

    return {"error": f"Unknown action: {action}. Use regex_test, regex_replace, regex_extract, stats, case, slug, lines, truncate."}


# ── Service Mesh (Redis Pub/Sub) ─────────────────────────────────────────

async def _service_mesh(action: str, channel: str = "", message: str = "",
                        timeout: int = 5) -> dict:
    """Redis pub/sub for inter-agent event-driven messaging.
    Actions: 'publish' (send message to channel), 'channels' (list active channels),
    'subscribe_once' (wait for one message on channel with timeout).
    """
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")

    if action == "publish":
        if not channel or not message:
            return {"error": "Channel and message required"}
        try:
            result = subprocess.run(
                ["redis-cli", "-h", redis_host, "-p", redis_port,
                 "PUBLISH", channel, message],
                capture_output=True, text=True, timeout=10,
            )
            subscribers = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
            return {"published": True, "channel": channel, "subscribers": subscribers}
        except Exception as e:
            return {"error": f"Publish failed: {e}"}

    elif action == "channels":
        try:
            result = subprocess.run(
                ["redis-cli", "-h", redis_host, "-p", redis_port,
                 "PUBSUB", "CHANNELS", "*"],
                capture_output=True, text=True, timeout=10,
            )
            channels = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            return {"channels": channels, "count": len(channels)}
        except Exception as e:
            return {"error": f"List channels failed: {e}"}

    elif action == "subscribe_once":
        if not channel:
            return {"error": "Channel required"}
        try:
            result = subprocess.run(
                ["redis-cli", "-h", redis_host, "-p", redis_port,
                 "SUBSCRIBE", channel],
                capture_output=True, text=True, timeout=timeout,
            )
            lines = result.stdout.strip().split("\n")
            messages = []
            for i in range(0, len(lines) - 2, 3):
                if lines[i].strip() == "message" and i + 2 < len(lines):
                    messages.append({"channel": lines[i + 1].strip(),
                                     "data": lines[i + 2].strip()})
            return {"messages": messages, "count": len(messages), "channel": channel}
        except subprocess.TimeoutExpired:
            return {"messages": [], "count": 0, "channel": channel,
                    "detail": f"No messages received within {timeout}s timeout"}
        except Exception as e:
            return {"error": f"Subscribe failed: {e}"}

    return {"error": f"Unknown action: {action}. Use publish, channels, subscribe_once."}


# ── Port Manager ──────────────────────────────────────────────────────────

def _port_manager(action: str, port: int = 0, start: int = 0,
                  end: int = 0) -> dict:
    """Manage network ports: check listeners, find free ports, kill port processes.
    Actions: 'check' (who's on a port), 'find_free' (find available port in range),
    'kill' (kill process on port), 'list_army' (list all OpenClaw Army ports).
    """
    if action == "check":
        if not port:
            return {"error": "Port number required"}
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-P", "-n"],
                capture_output=True, text=True, timeout=5,
            )
            if not result.stdout.strip():
                return {"port": port, "in_use": False}
            lines = result.stdout.strip().split("\n")
            processes = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 9:
                    processes.append({
                        "command": parts[0], "pid": int(parts[1]),
                        "user": parts[2], "name": parts[8],
                    })
            return {"port": port, "in_use": True, "processes": processes}
        except Exception as e:
            return {"error": f"Check failed: {e}"}

    elif action == "find_free":
        range_start = start or 19000
        range_end = end or 19100
        try:
            import socket
            for p in range(range_start, range_end):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(("127.0.0.1", p))
                sock.close()
                if result != 0:
                    return {"free_port": p, "range": f"{range_start}-{range_end}"}
            return {"error": f"No free ports in range {range_start}-{range_end}"}
        except Exception as e:
            return {"error": f"Port scan failed: {e}"}

    elif action == "kill":
        if not port:
            return {"error": "Port number required"}
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            if not pids:
                return {"killed": False, "detail": f"No process found on port {port}"}
            killed = []
            for pid in pids:
                try:
                    subprocess.run(["kill", pid], timeout=3)
                    killed.append(int(pid))
                except Exception:
                    pass
            return {"killed": True, "port": port, "pids": killed}
        except Exception as e:
            return {"error": f"Kill failed: {e}"}

    elif action == "list_army":
        army_ports = {}
        for name, p in sorted(AGENT_PORTS.items(), key=lambda x: x[1]):
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{p}"],
                    capture_output=True, text=True, timeout=2,
                )
                alive = bool(result.stdout.strip())
            except Exception:
                alive = False
            army_ports[name] = {"port": p, "alive": alive}
        # Add services
        for svc, sp in [("memory", 18820), ("orchestrator", 18830), ("ralph", 18840),
                        ("knowledge-bridge", 18850), ("agent-registry", 18860), ("notification", 18870)]:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{sp}"],
                    capture_output=True, text=True, timeout=2,
                )
                alive = bool(result.stdout.strip())
            except Exception:
                alive = False
            army_ports[svc] = {"port": sp, "alive": alive}
        return {"ports": army_ports, "count": len(army_ports)}

    return {"error": f"Unknown action: {action}. Use check, find_free, kill, list_army."}


# ── Batch Delegation ──────────────────────────────────────────────────────

async def _batch_delegate(tasks: list) -> dict:
    """Delegate different tasks to multiple managers in a single call.
    tasks: list of {manager: 'alpha'|'beta'|'gamma', task: str, priority: int}
    Returns results from all delegations.
    """
    if not tasks:
        return {"error": "No tasks provided"}

    manager_map = {
        "alpha": "alpha-manager", "alpha-manager": "alpha-manager",
        "beta": "beta-manager", "beta-manager": "beta-manager",
        "gamma": "gamma-manager", "gamma-manager": "gamma-manager",
    }

    async def _do_one(item):
        mgr_key = item.get("manager", "alpha")
        manager = manager_map.get(mgr_key)
        if not manager:
            return {"manager": mgr_key, "task": item.get("task", ""), "dispatched": False,
                    "error": f"Unknown manager: {mgr_key}"}
        task_desc = item.get("task", "")
        priority = item.get("priority", 2)
        plan = WorkflowPlan(
            original_task=task_desc,
            analysis=f"Batch-delegated to {manager}",
            status=TaskStatus.PENDING,
            requester="orchestrator",
        )
        plan.subtasks.append(SubTask(description=task_desc, assigned_to=manager, priority=priority))
        workflows[plan.id] = plan
        subtask = plan.subtasks[0]
        result = await dispatch_to_manager(manager, subtask, plan.id)
        return {
            "manager": manager, "task": task_desc, "priority": priority,
            "workflow_id": plan.id, "dispatched": result["dispatched"],
            "response": result.get("response_text", "")[:1000],
            "error": result.get("error", ""),
        }

    results = await asyncio.gather(*[_do_one(t) for t in tasks], return_exceptions=True)
    delegation_results = []
    for r in results:
        if isinstance(r, Exception):
            delegation_results.append({"error": str(r), "dispatched": False})
        else:
            delegation_results.append(r)

    dispatched_count = sum(1 for r in delegation_results if r.get("dispatched"))
    return {
        "results": delegation_results,
        "total": len(delegation_results),
        "dispatched": dispatched_count,
        "failed": len(delegation_results) - dispatched_count,
    }


# ── Dynamic Tool & Agent Registry ──────────────────────────────────────────

_DYNAMIC_TOOLS_PATH = Path(ARMY_HOME) / "data" / "dynamic_tools.json"
_DYNAMIC_AGENTS_PATH = Path(ARMY_HOME) / "data" / "dynamic_agents.json"


def _load_dynamic_tools() -> list[dict]:
    """Load dynamically registered tools from disk."""
    if not _DYNAMIC_TOOLS_PATH.exists():
        return []
    try:
        return json.loads(_DYNAMIC_TOOLS_PATH.read_text())
    except Exception:
        return []


def _save_dynamic_tools(tools: list[dict]):
    """Persist dynamic tools to disk."""
    _DYNAMIC_TOOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DYNAMIC_TOOLS_PATH.write_text(json.dumps(tools, indent=2))


def _load_dynamic_agents() -> dict:
    """Load dynamically registered agents from disk."""
    if not _DYNAMIC_AGENTS_PATH.exists():
        return {}
    try:
        return json.loads(_DYNAMIC_AGENTS_PATH.read_text())
    except Exception:
        return {}


def _save_dynamic_agents(agents: dict):
    """Persist dynamic agents to disk."""
    _DYNAMIC_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DYNAMIC_AGENTS_PATH.write_text(json.dumps(agents, indent=2))


# Runtime registries (loaded at startup, mutated at runtime)
_dynamic_tools: list[dict] = _load_dynamic_tools()
_dynamic_agents: dict = _load_dynamic_agents()


def register_tool(name: str, description: str, parameters: dict, handler_code: str) -> dict:
    """
    Register a new LLM-callable tool at runtime.
    handler_code: Python function body that receives (args: dict) and returns str.
    The function will be exec'd in a sandbox with limited globals.
    """
    # Validate the handler compiles
    wrapped = f"async def _tool_{name}(args):\n" + textwrap.indent(handler_code, "    ")
    ok, err = _validate_syntax(wrapped)
    if not ok:
        return {"registered": False, "detail": f"Handler syntax error: {err}"}

    tool_def = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "handler_code": handler_code,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Replace if exists, else append
    _dynamic_tools[:] = [t for t in _dynamic_tools if t["name"] != name]
    _dynamic_tools.append(tool_def)
    _save_dynamic_tools(_dynamic_tools)

    # Update INTERNAL_TOOLS set
    INTERNAL_TOOLS.add(name)

    return {"registered": True, "detail": f"Tool '{name}' registered and available for LLM use"}


def unregister_tool(name: str) -> dict:
    """Remove a dynamically registered tool."""
    before = len(_dynamic_tools)
    _dynamic_tools[:] = [t for t in _dynamic_tools if t["name"] != name]
    if len(_dynamic_tools) < before:
        _save_dynamic_tools(_dynamic_tools)
        INTERNAL_TOOLS.discard(name)
        return {"removed": True, "detail": f"Tool '{name}' removed"}
    return {"removed": False, "detail": f"Tool '{name}' not found"}


async def _execute_dynamic_tool(name: str, args: dict) -> str:
    """Execute a dynamically registered tool's handler safely."""
    tool = next((t for t in _dynamic_tools if t["name"] == name), None)
    if not tool:
        return json.dumps({"error": f"Dynamic tool '{name}' not found"})

    handler_code = tool["handler_code"]
    wrapped = f"async def _handler(args):\n" + textwrap.indent(handler_code, "    ")

    # Full execution environment — unrestricted for self-evolution
    safe_globals = {
        "__builtins__": __builtins__,
        "os": os, "sys": sys, "subprocess": subprocess,
        "shutil": shutil, "pathlib": __import__('pathlib'), "Path": Path,
        "asyncio": asyncio, "json": json, "re": re,
        "hashlib": hashlib, "textwrap": textwrap, "uuid": uuid,
        "datetime": datetime, "timezone": timezone, "time": time,
        "logging": logging, "app": app,
    }
    # Inject optional heavy imports if available
    for _mod_name in ("aiohttp", "requests", "yaml", "sqlite3", "csv", "io",
                      "base64", "urllib", "html", "xml", "socket", "struct",
                      "collections", "itertools", "functools", "math", "random",
                      "tempfile", "glob", "fnmatch", "threading"):
        try:
            safe_globals[_mod_name] = __import__(_mod_name)
        except ImportError:
            pass

    try:
        exec(wrapped, safe_globals)
        result = await safe_globals["_handler"](args)
        return str(result) if result is not None else "Done"
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {type(e).__name__}: {e}"})


def register_agent(name: str, port: int, description: str,
                   capabilities: list[str], profile: str = "") -> dict:
    """Register a new agent at runtime (doesn't spawn it, just makes it known)."""
    if port in AGENT_PORTS.values():
        existing = [k for k, v in AGENT_PORTS.items() if v == port]
        if existing and existing[0] != name:
            return {"registered": False, "detail": f"Port {port} already used by {existing[0]}"}

    _dynamic_agents[name] = {
        "port": port,
        "description": description,
        "capabilities": capabilities,
        "profile": profile,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_dynamic_agents(_dynamic_agents)

    # Add to live runtime registries
    AGENT_PORTS[name] = port

    return {"registered": True, "detail": f"Agent '{name}' registered on port {port}"}


def unregister_agent(name: str) -> dict:
    """Remove a dynamically registered agent."""
    if name in _dynamic_agents:
        port = _dynamic_agents[name]["port"]
        del _dynamic_agents[name]
        _save_dynamic_agents(_dynamic_agents)
        AGENT_PORTS.pop(name, None)
        return {"removed": True, "detail": f"Agent '{name}' (port {port}) removed"}
    return {"removed": False, "detail": f"Agent '{name}' not found in dynamic registry"}


@app.post("/tools/register")
async def register_tool_endpoint(name: str, description: str,
                                  parameters: dict, handler_code: str):
    """Register a new dynamic tool via API."""
    result = register_tool(name, description, parameters, handler_code)
    if result["registered"]:
        await activity.record("tool_register", "", f"Registered tool: {name}")
    return result


@app.delete("/tools/{name}")
async def unregister_tool_endpoint(name: str):
    """Remove a dynamic tool via API."""
    return unregister_tool(name)


@app.get("/tools")
async def list_tools():
    """List all tools (static + dynamic)."""
    static = [t["function"]["name"] for t in MANAGER_TOOLS]
    dynamic = [t["name"] for t in _dynamic_tools]
    return {"static_tools": static, "dynamic_tools": dynamic, "total": len(static) + len(dynamic)}


@app.post("/agents/register")
async def register_agent_endpoint(name: str, port: int, description: str,
                                   capabilities: list[str], profile: str = ""):
    """Register a new agent at runtime."""
    result = register_agent(name, port, description, capabilities, profile)
    if result["registered"]:
        await activity.record("agent_register", "", f"Registered agent: {name} on port {port}")
    return result


@app.delete("/agents/dynamic/{name}")
async def unregister_agent_endpoint(name: str):
    """Remove a dynamic agent."""
    return unregister_agent(name)


# ── Dynamic SYSTEM_PROMPT Mutation ─────────────────────────────────────────

_PROMPT_OVERRIDES_PATH = Path(ARMY_HOME) / "data" / "prompt_overrides.json"
_PROMPT_SECTIONS_PATH = Path(ARMY_HOME) / "data" / "prompt_sections.json"


def _load_prompt_overrides() -> dict:
    """Load persistent prompt section overrides."""
    if not _PROMPT_OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(_PROMPT_OVERRIDES_PATH.read_text())
    except Exception:
        return {}


def _load_prompt_sections() -> dict:
    """Load custom prompt sections (appended to base prompt)."""
    if not _PROMPT_SECTIONS_PATH.exists():
        return {}
    try:
        return json.loads(_PROMPT_SECTIONS_PATH.read_text())
    except Exception:
        return {}


_prompt_overrides: dict = _load_prompt_overrides()
_prompt_sections: dict = _load_prompt_sections()


def get_effective_system_prompt(date_str: str) -> str:
    """
    Build the effective SYSTEM_PROMPT by applying overrides and appending
    custom sections to the base prompt.
    """
    base = SYSTEM_PROMPT.format(date=date_str)

    # Apply any section overrides (replace tagged blocks)
    for tag, content in _prompt_overrides.items():
        marker_start = f"<!-- SECTION:{tag}:START -->"
        marker_end = f"<!-- SECTION:{tag}:END -->"
        if marker_start in base and marker_end in base:
            start_idx = base.index(marker_start)
            end_idx = base.index(marker_end) + len(marker_end)
            base = base[:start_idx] + marker_start + "\n" + content + "\n" + marker_end + base[end_idx:]

    # Append custom sections
    if _prompt_sections:
        base += "\n\nDYNAMIC KNOWLEDGE & DIRECTIVES (added at runtime):\n"
        for section_name, section_content in _prompt_sections.items():
            base += f"\n## {section_name}\n{section_content}\n"

    # Append info about dynamic tools if any exist
    if _dynamic_tools:
        base += "\n\nDYNAMIC TOOLS (registered at runtime):\n"
        for t in _dynamic_tools:
            base += f"- **{t['name']}**: {t['description']}\n"

    # Append info about dynamic agents if any exist
    if _dynamic_agents:
        base += "\n\nDYNAMIC AGENTS (registered at runtime):\n"
        for name, info in _dynamic_agents.items():
            base += f"- **{name}** (port {info['port']}): {info['description']}\n"

    return base


def update_prompt_section(section_name: str, content: str) -> dict:
    """Add or update a dynamic prompt section."""
    _prompt_sections[section_name] = content
    _PROMPT_SECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROMPT_SECTIONS_PATH.write_text(json.dumps(_prompt_sections, indent=2))
    return {"updated": True, "section": section_name, "total_sections": len(_prompt_sections)}


def remove_prompt_section(section_name: str) -> dict:
    """Remove a dynamic prompt section."""
    if section_name in _prompt_sections:
        del _prompt_sections[section_name]
        _PROMPT_SECTIONS_PATH.write_text(json.dumps(_prompt_sections, indent=2))
        return {"removed": True, "section": section_name}
    return {"removed": False, "detail": f"Section '{section_name}' not found"}


@app.post("/prompt/section")
async def update_prompt_section_endpoint(section_name: str, content: str):
    """Add or update a SYSTEM_PROMPT section."""
    result = update_prompt_section(section_name, content)
    if result["updated"]:
        await activity.record("prompt_update", "", f"Updated prompt section: {section_name}")
    return result


@app.delete("/prompt/section/{section_name}")
async def remove_prompt_section_endpoint(section_name: str):
    """Remove a SYSTEM_PROMPT section."""
    return remove_prompt_section(section_name)


@app.get("/prompt/sections")
async def list_prompt_sections():
    """List all dynamic prompt sections."""
    return {"sections": _prompt_sections, "overrides": _prompt_overrides}


@app.get("/prompt/effective")
async def get_effective_prompt():
    """View the full effective SYSTEM_PROMPT with all dynamic additions."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    prompt = get_effective_system_prompt(today)
    return {"prompt": prompt, "length": len(prompt),
            "dynamic_sections": len(_prompt_sections),
            "dynamic_tools": len(_dynamic_tools),
            "dynamic_agents": len(_dynamic_agents)}


# ── LLM Output Quality Monitor ────────────────────────────────────────────

_QUALITY_LOG_PATH = Path(ARMY_HOME) / "data" / "logs" / "quality.jsonl"
_QUALITY_WINDOW: deque = deque(maxlen=200)  # last 200 response scores


def _score_response_quality(user_message: str, response_text: str,
                            delegations: list[dict], latency_s: float) -> dict:
    """
    Score an LLM response on multiple quality dimensions.
    Returns a dict with individual scores and a composite score (0-100).
    """
    scores = {}

    # 1. Emptiness check (critical failure)
    if not response_text or not response_text.strip():
        return {"composite": 0, "scores": {"empty_response": 0},
                "flags": ["EMPTY_RESPONSE"], "grade": "F"}

    # 2. Length appropriateness (penalize both too short and excessively long)
    resp_len = len(response_text)
    msg_len = len(user_message)
    if resp_len < 20:
        scores["length"] = 20
    elif resp_len < 50 and msg_len > 50:
        scores["length"] = 40
    elif resp_len > 10000:
        scores["length"] = 60  # possibly run-on
    else:
        scores["length"] = 90

    # 3. Relevance heuristic — check overlap of user keywords in response
    user_words = set(re.findall(r'\b\w{4,}\b', user_message.lower()))
    resp_words = set(re.findall(r'\b\w{4,}\b', response_text.lower()))
    if user_words:
        overlap = len(user_words & resp_words) / len(user_words)
        scores["relevance"] = min(100, int(overlap * 100) + 30)  # baseline 30
    else:
        scores["relevance"] = 70  # can't measure

    # 4. Structure (markdown, lists, code blocks indicate structured thinking)
    structure_signals = [
        response_text.count("**") >= 2,  # bold text
        response_text.count("\n- ") >= 2 or response_text.count("\n* ") >= 2,  # lists
        "```" in response_text,  # code blocks
        response_text.count("\n") >= 3,  # multi-paragraph
    ]
    scores["structure"] = 50 + sum(structure_signals) * 12

    # 5. Delegation success rate
    if delegations:
        dispatched = sum(1 for d in delegations if d.get("dispatched"))
        scores["delegation"] = int((dispatched / len(delegations)) * 100) if delegations else 100
    else:
        scores["delegation"] = 100  # no delegations needed = fine

    # 6. Latency penalty
    if latency_s < 10:
        scores["latency"] = 95
    elif latency_s < 30:
        scores["latency"] = 80
    elif latency_s < 60:
        scores["latency"] = 60
    elif latency_s < 120:
        scores["latency"] = 40
    else:
        scores["latency"] = 20

    # 7. Honesty markers (good signs)
    honesty_phrases = ["i cannot", "i'm not able", "i don't have", "i've dispatched",
                       "i've delegated", "limitation", "note that"]
    has_honesty = any(p in response_text.lower() for p in honesty_phrases)
    scores["honesty"] = 90 if has_honesty else 70  # neutral if absent

    # 8. Repetition detection (bad sign)
    sentences = [s.strip() for s in re.split(r'[.!?]\s', response_text) if len(s.strip()) > 20]
    if sentences:
        unique_ratio = len(set(sentences)) / len(sentences)
        scores["repetition"] = int(unique_ratio * 100)
    else:
        scores["repetition"] = 80

    # 9. Error indicators
    error_phrases = ["error:", "failed to", "exception", "traceback", "i'm having trouble"]
    has_errors = any(p in response_text.lower() for p in error_phrases)
    scores["error_free"] = 30 if has_errors else 95

    # Composite score (weighted average)
    weights = {
        "length": 0.10, "relevance": 0.20, "structure": 0.10,
        "delegation": 0.15, "latency": 0.10, "honesty": 0.10,
        "repetition": 0.10, "error_free": 0.15,
    }
    composite = sum(scores.get(k, 70) * w for k, w in weights.items())
    composite = max(0, min(100, int(composite)))

    # Flags
    flags = []
    if composite < 40:
        flags.append("CRITICAL_QUALITY")
    elif composite < 60:
        flags.append("LOW_QUALITY")
    if scores.get("relevance", 70) < 40:
        flags.append("OFF_TOPIC")
    if scores.get("repetition", 80) < 50:
        flags.append("REPETITIVE")
    if has_errors:
        flags.append("CONTAINS_ERRORS")
    if latency_s > 120:
        flags.append("EXTREME_LATENCY")

    # Grade
    if composite >= 85:
        grade = "A"
    elif composite >= 70:
        grade = "B"
    elif composite >= 55:
        grade = "C"
    elif composite >= 40:
        grade = "D"
    else:
        grade = "F"

    return {"composite": composite, "scores": scores, "flags": flags, "grade": grade}


def _record_quality(session_id: str, user_message: str, response_text: str,
                    delegations: list[dict], latency_s: float) -> dict:
    """Score and record a response's quality. Returns the quality report."""
    report = _score_response_quality(user_message, response_text, delegations, latency_s)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "composite": report["composite"],
        "grade": report["grade"],
        "flags": report["flags"],
        "scores": report["scores"],
        "latency_s": round(latency_s, 2),
        "response_len": len(response_text),
        "user_msg_preview": user_message[:100],
    }
    _QUALITY_WINDOW.append(entry)

    # Persist
    _QUALITY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_QUALITY_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return report


def _detect_quality_degradation() -> dict:
    """
    Analyze the quality window for degradation trends.
    Compares recent scores to baseline to detect decline.
    """
    entries = list(_QUALITY_WINDOW)
    if len(entries) < 5:
        return {"degradation_detected": False, "detail": f"Insufficient data ({len(entries)} samples, need 5+)",
                "trend": "unknown"}

    scores = [e["composite"] for e in entries]
    overall_avg = sum(scores) / len(scores)

    # Compare last 5 to overall average
    recent_5 = scores[-5:]
    recent_avg = sum(recent_5) / len(recent_5)

    # Compare last 5 to the 5 before that (if available)
    if len(scores) >= 10:
        prev_5 = scores[-10:-5]
        prev_avg = sum(prev_5) / len(prev_5)
    else:
        prev_avg = overall_avg

    # Check for declining trend in last 5
    declining = all(recent_5[i] <= recent_5[i-1] for i in range(1, len(recent_5)))

    # Check for critical flags
    recent_entries = entries[-5:]
    critical_count = sum(1 for e in recent_entries if "CRITICAL_QUALITY" in e.get("flags", []))
    low_count = sum(1 for e in recent_entries if "LOW_QUALITY" in e.get("flags", []))

    # Grade distribution
    grades = Counter(e["grade"] for e in entries)

    degradation = False
    alerts = []

    if recent_avg < prev_avg - 15:
        degradation = True
        alerts.append(f"Recent avg ({recent_avg:.0f}) dropped >15 points below previous ({prev_avg:.0f})")
    if recent_avg < 50:
        degradation = True
        alerts.append(f"Recent average quality ({recent_avg:.0f}) is below acceptable threshold (50)")
    if declining and len(recent_5) >= 4:
        degradation = True
        alerts.append("Scores declining consistently over last 5 responses")
    if critical_count >= 2:
        degradation = True
        alerts.append(f"{critical_count}/5 recent responses flagged CRITICAL_QUALITY")

    if recent_avg > prev_avg + 5:
        trend = "improving"
    elif recent_avg < prev_avg - 5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "degradation_detected": degradation,
        "alerts": alerts,
        "trend": trend,
        "overall_avg": round(overall_avg, 1),
        "recent_avg": round(recent_avg, 1),
        "previous_avg": round(prev_avg, 1),
        "total_scored": len(entries),
        "grade_distribution": dict(grades),
        "last_5_scores": recent_5,
        "recommendation": _quality_recommendation(degradation, alerts, recent_avg),
    }


def _quality_recommendation(degradation: bool, alerts: list, recent_avg: float) -> str:
    """Generate actionable recommendations based on quality analysis."""
    if not degradation:
        if recent_avg >= 80:
            return "Quality is excellent. No action needed."
        return "Quality is acceptable. Monitor for changes."

    recommendations = []
    if recent_avg < 40:
        recommendations.append("URGENT: Quality critically low. Consider rotating API keys, checking model availability, or reverting recent prompt changes.")
    if any("declining" in a.lower() for a in alerts):
        recommendations.append("Consistent decline detected. Review recent prompt_section changes or new tool registrations that may confuse the LLM.")
    if any("CRITICAL" in a for a in alerts):
        recommendations.append("Multiple critical failures. Run self-heal and check infrastructure health.")

    return " | ".join(recommendations) if recommendations else "Quality declining — investigate recent changes."


@app.get("/quality")
async def quality_report():
    """Get the current quality assessment with degradation detection."""
    degradation = _detect_quality_degradation()
    recent = list(_QUALITY_WINDOW)[-10:]
    return {"degradation_analysis": degradation, "recent_scores": recent}


@app.get("/quality/history")
async def quality_history(limit: int = 50):
    """Get recent quality scores."""
    entries = list(_QUALITY_WINDOW)
    return {"entries": entries[-limit:], "total": len(entries)}
async def self_heal(reason: str = "manual trigger"):
    """
    Self-healing endpoint: diagnose problems and ACTUALLY FIX them.
    Clears stale locks, checks managers, restarts crashed ones, rotates API keys.
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

    # 2. Check manager health and RESTART dead ones
    import aiohttp
    manager_status = {}
    for mgr, port in [("alpha-manager", 18800), ("beta-manager", 18801), ("gamma-manager", 18802)]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as sess:
                async with sess.get(f"http://127.0.0.1:{port}/") as resp:
                    if resp.status == 200:
                        manager_status[mgr] = "up"
                    else:
                        manager_status[mgr] = "error"
        except Exception:
            manager_status[mgr] = "down"
            actions.append(f"{mgr} is DOWN — attempting automatic restart...")
            restart = await _restart_manager(mgr)
            if restart["restarted"]:
                actions.append(f"RESTARTED {mgr} successfully")
                manager_status[mgr] = "restarted"
            else:
                actions.append(f"FAILED to restart {mgr}: {restart['detail']}")
                _record_failure("restart_fail", restart["detail"], mgr)

    # 3. Rotate API key if current one might be rate-limited
    _rotate_key()
    new_key = _get_api_key()
    llm_client.api_key = new_key
    actions.append("Rotated API key to next in pool")

    await activity.record("self_heal", "", f"Self-heal executed: {reason}",
                          {"reason": reason, "actions": actions, "manager_status": manager_status})

    return {
        "reason": reason,
        "actions_taken": actions,
        "manager_status": manager_status,
        "api_key_rotated": True,
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
    """Background task: every 60s, clear stale locks, auto-restart dead managers."""
    import aiohttp
    _consecutive_failures = Counter()  # track per-manager consecutive failures

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

            # Check managers and auto-restart dead ones
            for mgr_name, port in [("alpha-manager", 18800), ("beta-manager", 18801), ("gamma-manager", 18802)]:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as sess:
                        async with sess.get(f"http://127.0.0.1:{port}/") as resp:
                            if resp.status == 200:
                                _consecutive_failures[mgr_name] = 0
                            else:
                                _consecutive_failures[mgr_name] += 1
                except Exception:
                    _consecutive_failures[mgr_name] += 1

                # Auto-restart after 2 consecutive failures (gives transient errors a chance)
                if _consecutive_failures[mgr_name] >= 2:
                    log.warning(f"Watchdog: {mgr_name} down for {_consecutive_failures[mgr_name]} checks — restarting")
                    _record_failure("watchdog_restart", f"{mgr_name} unresponsive for {_consecutive_failures[mgr_name]} checks", mgr_name)
                    restart = await _restart_manager(mgr_name)
                    if restart["restarted"]:
                        log.info(f"Watchdog: RESTARTED {mgr_name} successfully")
                        await activity.record("watchdog", "", f"Auto-restarted {mgr_name}",
                                              {"manager": mgr_name, "result": "success"})
                        _consecutive_failures[mgr_name] = 0
                    else:
                        log.error(f"Watchdog: FAILED to restart {mgr_name}: {restart['detail']}")
                        await activity.record("watchdog", "", f"Failed to restart {mgr_name}",
                                              {"manager": mgr_name, "error": restart["detail"]})

        except Exception as e:
            log.error(f"Watchdog error: {e}")


@app.on_event("startup")
async def startup():
    log.info(f"Orchestrator API starting on port {ORCHESTRATOR_PORT}")
    log.info(f"Configured agents: {list(AGENT_PORTS.keys())}")
    log.info(f"Manager pools: {list(MANAGER_POOLS.keys())}")
    _load_manifests()
    log.info(f"Loaded {len(_manifest_cache)} workflow manifests")
    _load_persisted_sessions()
    await _load_persisted_scheduled_tasks()
    await _load_persisted_cron_tasks()
    await activity.record("system", "", "Orchestrator started",
                          {"port": ORCHESTRATOR_PORT,
                           "agents": len(AGENT_PORTS),
                           "manifests": len(_manifest_cache),
                           "sessions": len(_chat_sessions),
                           "cron_tasks": len(_cron_tasks)})
    asyncio.create_task(_health_watchdog())


# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT, log_level="info")
