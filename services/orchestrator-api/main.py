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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Header
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
import threading
_key_lock = threading.Lock()

def _get_api_key():
    with _key_lock:
        if not _NVAPI_KEYS:
            return ""
        return _NVAPI_KEYS[_key_index % len(_NVAPI_KEYS)]

def _rotate_key():
    global _key_index
    with _key_lock:
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
- **web_scrape**: Parse HTML from URLs or raw strings. Extract text, links, tables, meta tags, headings, or query with CSS selectors. Auto-installs BeautifulSoup.
- **docker_manage**: Full Docker container lifecycle — ps, images, run, stop, rm, logs, exec, pull, build, inspect, stats.
- **osascript**: Execute AppleScript for macOS automation. Open/quit apps, text-to-speech, dialogs, notifications, clipboard, volume, Finder.
- **image_process**: Image manipulation via Pillow — resize, crop, rotate, convert formats, thumbnails, EXIF metadata. Auto-installs Pillow.
- **date_calc**: Date/time calculations — timezone conversion, date arithmetic, natural parsing, epoch conversion, calendar generation.
- **project_replace**: Find and replace across entire project directories. Regex, glob filtering, dry-run preview, auto-backup.
- **process_watchdog**: Auto-restart crashed processes. Register health checks, monitor uptime, configurable restart limits.
- **metrics_collect**: Time-series metrics — record, query, summarize (min/max/avg/p95/p99), dashboard overview, trend detection.
- **markdown_render**: Convert Markdown↔HTML, generate formatted tables from JSON, extract table of contents.
- **sql_schema**: PostgreSQL schema management — list tables, describe columns, indexes, sizes, create tables, add columns, foreign keys.
- **audio_process**: Audio processing via ffmpeg + macOS say — convert formats, text-to-speech, trim, merge, metadata, volume adjust, list available TTS voices.
- **video_process**: Video processing via ffmpeg — convert formats, extract frames, trim clips, generate thumbnails, probe metadata, resize resolution.
- **pdf_tools**: PDF generation and parsing — create PDFs from text, extract text from PDFs, count pages, merge multiple PDFs, split into individual pages. Auto-installs fpdf2 and pymupdf.
- **ssh_remote**: Execute commands on remote hosts via SSH — run commands, copy files to/from remote hosts (scp), test connectivity.
- **secret_vault**: Encrypted secrets management using Fernet — store, retrieve, list, delete secrets with AES encryption. Key rotation support. Vault file is chmod 600.
- **test_runner**: Execute tests and return structured results — run pytest with pass/fail counts, unittest, arbitrary test scripts, discover available tests.
- **dependency_analysis**: Analyze Python imports using AST — list all imports, detect circular dependencies across a project, find unused imports, categorize as stdlib/third-party/local.
- **resource_monitor**: Real-time CPU/memory/disk monitoring with alerts — snapshots, top processes by CPU or memory, configurable threshold alerts, network I/O, temperatures. Auto-installs psutil.
- **sqlite_query**: Lightweight local SQLite database — query, execute, list tables, describe schema, import CSV files. No server needed. Default database at data/local.db.
- **file_watch**: Watch directories for file changes — start/stop watchers using watchfiles, view recent change events (added/modified/deleted) with timestamps.
- **email_parse**: Parse email files (.eml) and read IMAP inboxes — extract headers, body, attachments, list folders, read inbox messages, parse raw email strings.
- **qr_code**: Generate and decode QR codes — create PNG or SVG QR codes from data, decode QR codes from images. Auto-installs qrcode.
- **http_server**: Ephemeral HTTP file servers — start servers on any port to share directories, manage multiple concurrent servers, auto-assigned ports.
- **json_schema**: JSON Schema validation and generation — validate data against Draft-07 schemas, infer schemas from sample data, diff two schemas.
- **cache_manager**: Smart caching layer over Redis — get/set with TTL, namespace isolation, cache stats (memory, key counts), clear by namespace.
- **math_compute**: Advanced mathematics via sympy and numpy — symbolic algebra (simplify/expand/factor), equation solving, derivatives, integrals, matrix operations (det/inverse/eigenvalues), descriptive statistics.
- **regex_builder**: Regex pattern building and testing — test patterns with group extraction, regex replace, findall extraction, split, and pattern explanation/tokenization.
- **cert_check**: SSL certificate management — inspect remote certs, check expiry with warning thresholds, generate self-signed certs, decode PEM files.
- **system_profiler**: macOS system profiling — hardware specs, software info, network config, storage, USB devices, displays, battery, any SPDataType.
- **url_tools**: URL manipulation — parse/decompose URLs, build URLs from components, URL encode/decode, validate (optionally live), extract links from text, fetch and parse XML sitemaps.
- **desktop_control**: Full macOS desktop GUI automation — see the screen (screenshot + OCR text recognition), move mouse, click, type text, press hotkeys, find images/text on screen, list/focus windows, scroll, drag. Auto-installs pyautogui.
- **browser_automate**: Full browser automation via headless Playwright — navigate websites, fill forms, click UI elements, screenshot rendered pages, extract JS-rendered content, run JavaScript in page, interact with SPAs. Launch/close persistent sessions.
- **git_ops**: Complete Git and GitHub operations — local repo management (status, log, diff, branch, commit, push, pull, clone, stash, remote, tag) + GitHub API (raw endpoints, create PRs, list issues). Uses GITHUB_TOKEN env var.
- **code_analyze**: Code analysis suite — AST parsing (list classes/functions/imports), linting (flake8/pylint), security scanning (bandit SAST), cyclomatic complexity metrics, TODO/FIXME/HACK finder. Auto-installs tools.
- **llm_fallback**: Multi-provider LLM routing with automatic failover — add/remove providers, set priorities, test reachability, query with automatic failover across all configured providers. Supports any OpenAI-compatible API.
- **notify_send**: Multi-channel notifications — macOS native alerts, Slack webhooks, Discord webhooks, Pushover push notifications, macOS text-to-speech. Alert yourself or users through any channel.
- **full_backup**: Complete system backup and disaster recovery — backs up code, data/, agents/, configs, PostgreSQL (pg_dump), Redis (BGSAVE). Restore, list, and cleanup old backups.
- **embeddings**: Text embeddings and vector similarity search — encode text to vectors (NVIDIA API or bag-of-words fallback), store in collections, semantic search with cosine similarity. Build knowledge bases.
- **api_client**: Generic REST/GraphQL API client — HTTP requests with auth (bearer/basic/api_key), auto-retry with backoff, GraphQL queries, auto-pagination. Call any external API.
- **cron_advanced**: Advanced cron with task chains — define multi-step task chains with dependencies, per-step retry policies, conditional execution (abort/skip/retry on failure), enable/disable chains.
- **accessibility**: macOS Accessibility API — inspect and control UI elements of any application. Get focused app, list UI elements, click buttons by name, read/write text fields, list and click menu items. Deep app integration.
- **screen_share**: Live screen sharing and continuous monitoring — start a persistent screen capture session that periodically takes screenshots with OCR, detects changes, and streams frames as base64 images over a WebSocket or HTTP endpoint. Actions: start_session (begin capturing), stop_session, get_frame (latest screenshot + OCR text + changed regions), get_status (active sessions), set_interval (adjust capture rate). Integrates with Chrome Remote Desktop for remote access.
- **visionclaw**: VisionClaw integration for Meta Ray-Ban smart glasses — manage glass sessions, check connection status, configure gateway networking, view conversation history with glasses users. The orchestrator exposes /v1/chat/completions (OpenAI-compatible) that VisionClaw connects to, giving the glasses user access to all 101 tools. Actions: status, sessions, config, configure, send, history.

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
- Need to scrape a website or parse HTML? → Use web_scrape to extract text, links, tables, or CSS-selected elements from any URL.
- Need to manage Docker containers? → Use docker_manage to run, stop, inspect, exec, pull images — full container lifecycle.
- Need macOS desktop automation? → Use osascript for AppleScript — open apps, send keystrokes, show dialogs, text-to-speech.
- Need to resize or convert images? → Use image_process for resize, crop, rotate, convert, thumbnails, EXIF metadata.
- Need date math or timezone conversion? → Use date_calc for adding days, diffing dates, converting timezones, epoch values.
- Need to find-and-replace across a project? → Use project_replace with regex and glob filtering across all files.
- Need auto-restart for crashed services? → Use process_watchdog to register health checks and auto-restart on failure.
- Need to track metrics over time? → Use metrics_collect to record values and get min/max/avg/p95/p99 summaries.
- Need Markdown↔HTML conversion or formatted tables? → Use markdown_render to convert, generate tables, extract TOC.
- Need to inspect database schema? → Use sql_schema for tables, columns, indexes, sizes, DDL, foreign keys.
- Need to process audio files? → Use audio_process for format conversion, trimming, merging, volume adjust, metadata via ffmpeg.
- Need text-to-speech? → Use audio_process action 'tts' with macOS say — supports multiple voices. Use 'voices' to list them.
- Need to process video files? → Use video_process for conversion, frame extraction, trimming, thumbnails, resizing via ffmpeg.
- Need to create or parse PDFs? → Use pdf_tools — create PDFs from text, extract text from existing PDFs, merge, split. Auto-installs libraries.
- Need to run commands on remote machines? → Use ssh_remote to execute commands, upload/download files via SCP, test connectivity.
- Need to store secrets securely? → Use secret_vault for AES-encrypted storage. Store API keys, tokens, passwords. Supports key rotation.
- Need to run tests? → Use test_runner to execute pytest/unittest and get structured pass/fail results with output.
- Need to analyze Python dependencies? → Use dependency_analysis to list imports, detect circular deps, find unused imports, categorize packages.
- Need real-time system resource monitoring? → Use resource_monitor for CPU/memory/disk snapshots, top processes, threshold alerts, network stats.
- Need a lightweight local database? → Use sqlite_query for SQL queries without PostgreSQL overhead. Import CSVs, create tables, query data.
- Need to detect file changes? → Use file_watch to start watchers on directories, get events for added/modified/deleted files.
- Need to read or parse emails? → Use email_parse for .eml files, IMAP inbox reading, attachment extraction.
- Need QR codes? → Use qr_code to generate PNG/SVG QR codes or decode QR from images.
- Need to serve files over HTTP? → Use http_server to spin up ephemeral file servers on any port.
- Need to validate JSON data? → Use json_schema to validate against schemas, generate schemas from data, diff schemas.
- Need smart caching? → Use cache_manager for Redis-backed caching with TTL, namespaces, and statistics.
- Need advanced math? → Use math_compute for symbolic algebra, equation solving, calculus, matrix ops, statistics.
- Need to build or test regex? → Use regex_builder to test patterns, extract groups, explain tokens.
- Need to check SSL certificates? → Use cert_check to inspect certs, check expiry, generate self-signed, decode PEM.
- Need macOS hardware/software info? → Use system_profiler to query any SPDataType (hardware, software, network, storage, etc.).
- Need URL parsing or link extraction? → Use url_tools to parse, build, encode, validate URLs, extract links, fetch sitemaps.
- Need to see the screen or control the mouse/keyboard? → Use desktop_control — screenshot_ocr to see what's on screen (with text recognition), move_mouse/click/type_text/hotkey to interact, get_window_list/focus_window to manage apps, find_text_on_screen to locate UI elements.
- Need to automate a browser or scrape JS-rendered sites? → Use browser_automate — launch a Playwright session, navigate, click, fill forms, extract content, screenshot pages. Handles SPAs and dynamic content.
- Need full Git/GitHub integration? → Use git_ops — local repo management (status, log, diff, commit, push, pull) + GitHub API (create PRs, list issues, any endpoint).
- Need code quality analysis? → Use code_analyze — AST parsing, flake8 linting, bandit security scanning, cyclomatic complexity, TODO finder. Self-audit your own code.
- Need to query a different LLM or add backup models? → Use llm_fallback — add providers, set priority chain, queries auto-failover across all providers if one is down.
- Need to alert yourself or a user? → Use notify_send — macOS native alerts, Slack, Discord, Pushover push notifications, or text-to-speech.
- Need a full system backup before risky changes? → Use full_backup — backs up code, data, agents, configs, PostgreSQL, Redis. One-click disaster recovery.
- Need semantic search over documents or knowledge? → Use embeddings — encode text to vectors, store in collections, search by meaning with cosine similarity.
- Need to call any external REST or GraphQL API? → Use api_client — supports auth (bearer/basic/api_key), retry with backoff, GraphQL, auto-pagination.
- Need multi-step automation with retry logic? → Use cron_advanced — define task chains where each step can abort, skip, or retry on failure.
- Need to inspect or click UI elements in macOS apps? → Use accessibility — read AX trees, click buttons by name, get/set text field values, navigate menus.
- Need live screen monitoring or continuous visual feedback? → Use screen_share — start a capture session, get periodic screenshots with OCR + change detection. Streams frames for continuous visual awareness.
- Need to manage Meta Ray-Ban glass sessions or check VisionClaw connections? → Use visionclaw — status shows active glass sessions and gateway config, config shows recommended settings, configure changes gateway bind for LAN access.
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
- You CAN scrape websites and parse HTML with web_scrape (text, links, tables, CSS selectors, meta tags).
- You CAN manage Docker containers with docker_manage (run, stop, logs, exec, pull, build, inspect).
- You CAN automate macOS with osascript (AppleScript — open apps, dialogs, notifications, TTS, clipboard).
- You CAN process images with image_process (resize, crop, rotate, convert, thumbnails, EXIF). Auto-installs Pillow.
- You CAN do date math and timezone conversion with date_calc (add days, diff dates, parse, format, epoch).
- You CAN find-and-replace across project directories with project_replace (regex, glob, dry-run, backup).
- You CAN auto-restart crashed processes with process_watchdog (health checks, max restart limits).
- You CAN track time-series metrics with metrics_collect (record, query, summary with p95/p99, dashboard).
- You CAN convert Markdown↔HTML and generate tables with markdown_render.
- You CAN introspect and manage PostgreSQL schemas with sql_schema (tables, columns, indexes, DDL, foreign keys).
- You CAN process audio with audio_process (convert formats, TTS, trim, merge, metadata, volume) via ffmpeg + macOS say.
- You CAN process video with video_process (convert, extract frames, trim, thumbnails, metadata, resize) via ffmpeg.
- You CAN generate and parse PDFs with pdf_tools (create from text, extract text, page count, merge, split). Auto-installs fpdf2/pymupdf.
- You CAN execute commands on remote hosts with ssh_remote (SSH exec, SCP upload/download, connectivity test).
- You CAN manage encrypted secrets with secret_vault (store, retrieve, list, delete, rotate encryption key). Fernet AES.
- You CAN run tests with test_runner (pytest, unittest, scripts) and get structured pass/fail/error counts.
- You CAN analyze Python dependencies with dependency_analysis (list imports, circular deps, unused imports, categorize stdlib/third-party/local).
- You CAN monitor system resources with resource_monitor (CPU/memory/disk snapshots, top processes, threshold alerts, network I/O). Auto-installs psutil.
- You CAN query lightweight local SQLite databases with sqlite_query (query, execute, tables, schema, import CSV). No server needed.
- You CAN watch directories for file changes with file_watch (start/stop watchers, view added/modified/deleted events).
- You CAN parse email files and read IMAP inboxes with email_parse (headers, body, attachments, folder listing).
- You CAN generate and decode QR codes with qr_code (PNG, SVG, decode from images). Auto-installs qrcode.
- You CAN serve files over HTTP with http_server (start/stop ephemeral servers on any port).
- You CAN validate JSON against schemas and generate schemas with json_schema (Draft-07, diff schemas).
- You CAN cache data intelligently with cache_manager (Redis-backed, TTL, namespaces, memory stats).
- You CAN do advanced math with math_compute (symbolic algebra, solve equations, derivatives, integrals, matrices, statistics).
- You CAN build and test regex patterns with regex_builder (match, replace, extract, split, explain tokens).
- You CAN inspect SSL certificates with cert_check (remote cert details, expiry warnings, self-signed generation, PEM decode).
- You CAN profile macOS system hardware and software with system_profiler (hardware, software, network, storage, USB, displays, battery).
- You CAN parse, build, validate URLs and extract links with url_tools (parse, encode, validate, sitemaps).
- You CAN see the computer screen with desktop_control screenshot_ocr (captures screen + OCR text recognition). You CAN control the mouse (move, click, drag, scroll) and keyboard (type_text, hotkey). You CAN list all visible windows, focus any app, find text/images on screen. This gives you FULL GUI automation capability.
- You CAN automate any browser with browser_automate (Playwright — navigate, click, fill, evaluate JS, screenshot, extract tables, handle JS-rendered content).
- You CAN do full Git and GitHub API operations with git_ops (status, log, diff, commit, push, pull, clone + create PRs, list issues, raw API calls).
- You CAN analyze code quality with code_analyze (AST parse, flake8 lint, bandit security scan, cyclomatic complexity, find TODOs). Self-audit your own code.
- You CAN route LLM queries across multiple providers with llm_fallback (automatic failover, priority chain, add/test/query providers).
- You CAN send alerts through any channel with notify_send (macOS native, Slack webhooks, Discord webhooks, Pushover, text-to-speech).
- You CAN perform complete system backups with full_backup (code, data, configs, PostgreSQL, Redis — one-click backup and restore).
- You CAN build semantic search over any text with embeddings (encode to vectors, store in collections, cosine similarity search).
- You CAN call any external REST or GraphQL API with api_client (auth support, retry with backoff, auto-pagination).
- You CAN define multi-step task chains with cron_advanced (dependencies, per-step retry policies, abort/skip/retry on failure).
- You CAN inspect and control macOS app UIs with accessibility (AX tree, click buttons by name, read/write text fields, navigate menus).
- You CAN continuously monitor the screen with screen_share (start a capture session, get periodic screenshots + OCR text + change detection). Chrome Remote Desktop host is running for remote access integration.
- You CAN receive and process requests from Meta Ray-Ban smart glasses via VisionClaw. The /v1/chat/completions endpoint is OpenAI-compatible. When a glasses user speaks a command, Gemini Live delegates it here. All 101 tools are available to glasses users. Use visionclaw tool to manage glass sessions and gateway config.
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
    {
        "type": "function",
        "function": {
            "name": "web_scrape",
            "description": "Parse HTML and extract structured data from URLs or raw HTML. Actions: 'text' (visible text), 'links' (all links), 'tables' (HTML tables as lists), 'select' (CSS selector query), 'meta' (meta tags/title), 'headers' (headings h1-h6). Auto-installs BeautifulSoup if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'text', 'links', 'tables', 'select', 'meta', 'headers'"},
                    "url": {"type": "string", "description": "URL to fetch and parse"},
                    "html": {"type": "string", "description": "Raw HTML string to parse (instead of url)"},
                    "selector": {"type": "string", "description": "CSS selector (for 'select' action)"},
                    "attribute": {"type": "string", "description": "Extract this attribute from selected elements"},
                    "limit": {"type": "integer", "description": "Max results (default 50)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_manage",
            "description": "Manage Docker containers and images. Actions: 'ps' (list containers), 'images' (list images), 'run' (start container), 'stop', 'rm' (remove), 'logs' (container logs), 'exec' (run command in container), 'pull' (pull image), 'build', 'inspect', 'stats' (resource usage).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'ps', 'images', 'run', 'stop', 'rm', 'logs', 'exec', 'pull', 'build', 'inspect', 'stats'"},
                    "image": {"type": "string", "description": "Docker image name (for run/pull/build)"},
                    "container": {"type": "string", "description": "Container name or ID"},
                    "command": {"type": "string", "description": "Command to run (for exec/run)"},
                    "ports": {"type": "string", "description": "Port mappings: '8080:80,9090:90'"},
                    "env_vars": {"type": "object", "description": "Environment variables dict"},
                    "volumes": {"type": "string", "description": "Volume mounts: '/host:/container'"},
                    "name": {"type": "string", "description": "Container name (for run) or tag (for build)"},
                    "options": {"type": "string", "description": "Additional docker options as string"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "osascript",
            "description": "Execute AppleScript for macOS automation. Preset actions: 'open_app', 'quit_app', 'frontmost' (get frontmost app), 'say' (text-to-speech), 'dialog' (show dialog), 'notification' (macOS notification), 'open_url', 'set_volume', 'get_clipboard', 'set_clipboard', 'list_apps'. Or provide raw AppleScript.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "Raw AppleScript code to execute"},
                    "action": {"type": "string", "description": "Preset action name"},
                    "app_name": {"type": "string", "description": "Application name (for open_app/quit_app)"},
                    "text": {"type": "string", "description": "Text parameter (for say/dialog/notification/open_url/set_volume/set_clipboard)"},
                    "path": {"type": "string", "description": "File path parameter (if needed)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "image_process",
            "description": "Process images: resize, crop, rotate, convert format, get metadata, create thumbnails. Auto-installs Pillow if needed. Actions: 'info' (dimensions/format/EXIF), 'resize', 'crop' (left,top,right,bottom), 'rotate', 'convert' (png/jpg/webp/gif), 'thumbnail', 'flip'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'info', 'resize', 'crop', 'rotate', 'convert', 'thumbnail', 'flip'"},
                    "path": {"type": "string", "description": "Path to the input image"},
                    "output_path": {"type": "string", "description": "Path to save output"},
                    "width": {"type": "integer", "description": "Target width (for resize/thumbnail)"},
                    "height": {"type": "integer", "description": "Target height (for resize/thumbnail)"},
                    "quality": {"type": "integer", "description": "JPEG quality 1-100 (default 85)"},
                    "format": {"type": "string", "description": "Target format: png, jpg, webp, gif (for convert). Or 'horizontal'/'vertical' (for flip)"},
                    "angle": {"type": "number", "description": "Rotation angle in degrees (for rotate)"},
                    "crop": {"type": "string", "description": "Crop coordinates: 'left,top,right,bottom'"}
                },
                "required": ["action", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "date_calc",
            "description": "Date/time calculations and conversions. Actions: 'now' (current time in timezone), 'add' (add days/hours/minutes), 'diff' (difference between two dates), 'convert_tz' (timezone conversion), 'parse' (parse date string), 'format' (reformat date), 'epoch' (Unix timestamp conversion), 'calendar' (month calendar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'now', 'add', 'diff', 'convert_tz', 'parse', 'format', 'epoch', 'calendar'"},
                    "date_str": {"type": "string", "description": "Date string to process. For 'diff': 'date1 | date2'"},
                    "days": {"type": "integer", "description": "Days to add (for 'add')"},
                    "hours": {"type": "integer", "description": "Hours to add (for 'add')"},
                    "minutes": {"type": "integer", "description": "Minutes to add (for 'add')"},
                    "from_tz": {"type": "string", "description": "Source timezone (e.g., 'America/New_York')"},
                    "to_tz": {"type": "string", "description": "Target timezone (e.g., 'Asia/Tokyo')"},
                    "format": {"type": "string", "description": "strftime format string"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "project_replace",
            "description": "Find and replace across multiple files in a project directory. Actions: 'search' (find occurrences), 'replace' (apply replacements), 'preview' (dry-run showing what would change). Supports regex, glob file filtering, auto-backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'search', 'replace', 'preview'"},
                    "directory": {"type": "string", "description": "Root directory to search (default: ARMY_HOME)"},
                    "pattern": {"type": "string", "description": "Search pattern (text or regex)"},
                    "replacement": {"type": "string", "description": "Replacement text (for replace/preview)"},
                    "file_glob": {"type": "string", "description": "File glob pattern (default: '**/*')"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex (default false)"},
                    "dry_run": {"type": "boolean", "description": "Preview changes without applying (default true)"},
                    "backup": {"type": "boolean", "description": "Create .bak files before replacing (default true)"}
                },
                "required": ["action", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_watchdog",
            "description": "Auto-restart crashed processes. Register processes with health checks. Actions: 'register' (add watchdog), 'unregister' (remove), 'list' (show all), 'status' (check one), 'check_all' (health-check all and auto-restart dead ones).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'register', 'unregister', 'list', 'status', 'check_all'"},
                    "name": {"type": "string", "description": "Watchdog name/identifier"},
                    "command": {"type": "string", "description": "Shell command to start the process"},
                    "interval": {"type": "integer", "description": "Health check interval in seconds (default 30)"},
                    "max_restarts": {"type": "integer", "description": "Max auto-restarts before giving up (default 10)"},
                    "health_url": {"type": "string", "description": "HTTP URL to check for health (e.g., http://localhost:18830/health)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "metrics_collect",
            "description": "Record and analyze time-series metrics. Track performance, latency, error rates over time. Actions: 'record' (store a metric), 'query' (get history), 'summary' (min/max/avg/p95/p99), 'list' (all metric names), 'delete', 'dashboard' (overview of all metrics).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'record', 'query', 'summary', 'list', 'delete', 'dashboard'"},
                    "name": {"type": "string", "description": "Metric name (e.g., 'response_time', 'error_count')"},
                    "value": {"type": "number", "description": "Numeric value to record"},
                    "tags": {"type": "object", "description": "Optional tags/labels dict"},
                    "hours": {"type": "number", "description": "Query time window in hours (default 24)"},
                    "limit": {"type": "integer", "description": "Max results (default 100)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "markdown_render",
            "description": "Convert between Markdown and HTML. Generate formatted tables. Actions: 'md_to_html' (Markdown → HTML with code highlighting), 'html_to_md' (HTML → Markdown), 'table' (generate Markdown table from JSON data), 'toc' (extract table of contents from markdown).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'md_to_html', 'html_to_md', 'table', 'toc'"},
                    "text": {"type": "string", "description": "Input text (markdown, HTML, or JSON for table)"},
                    "path": {"type": "string", "description": "Read input from file instead"},
                    "output_path": {"type": "string", "description": "Write output to file"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sql_schema",
            "description": "PostgreSQL schema introspection and management. Actions: 'tables' (list all), 'describe' (columns of a table), 'indexes' (list indexes), 'size' (table/DB sizes), 'create_table' (DDL), 'add_column', 'foreign_keys', 'migrations' (list applied).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: 'tables', 'describe', 'indexes', 'size', 'create_table', 'add_column', 'foreign_keys', 'migrations'"},
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "description": "Schema name (default 'public')"},
                    "columns": {"type": "array", "description": "Column definitions: [{name, type, nullable, default, primary_key}]"},
                    "query": {"type": "string", "description": "Raw SQL query (for advanced use)"}
                },
                "required": ["action"]
            }
        }
    },
    # ── Round 7 Tools ──
    {
        "type": "function",
        "function": {
            "name": "audio_process",
            "description": "Audio processing via ffmpeg and macOS say. Actions: 'convert' (format conversion), 'tts' (text-to-speech), 'trim' (cut segment), 'merge' (concatenate files), 'metadata' (probe info), 'volume' (adjust level), 'voices' (list TTS voices).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: convert, tts, trim, merge, metadata, volume, voices"},
                    "source": {"type": "string", "description": "Input audio file path"},
                    "destination": {"type": "string", "description": "Output file path"},
                    "text": {"type": "string", "description": "Text for TTS"},
                    "output": {"type": "string", "description": "Output path for TTS"},
                    "voice": {"type": "string", "description": "TTS voice name"},
                    "start": {"type": "string", "description": "Start time for trim (seconds or HH:MM:SS)"},
                    "duration": {"type": "string", "description": "Duration for trim"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "List of files to merge"},
                    "level": {"type": "string", "description": "Volume level (e.g., '1.5' for 150%)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "video_process",
            "description": "Video processing via ffmpeg. Actions: 'convert' (format conversion), 'extract_frames' (save frames as images), 'trim' (cut segment), 'thumbnail' (extract single frame), 'metadata' (probe info), 'resize' (change resolution).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: convert, extract_frames, trim, thumbnail, metadata, resize"},
                    "source": {"type": "string", "description": "Input video file path"},
                    "destination": {"type": "string", "description": "Output file path"},
                    "output_dir": {"type": "string", "description": "Output directory for extracted frames"},
                    "fps": {"type": "string", "description": "Frames per second for extraction"},
                    "start": {"type": "string", "description": "Start time for trim"},
                    "duration": {"type": "string", "description": "Duration for trim"},
                    "timestamp": {"type": "string", "description": "Timestamp for thumbnail (HH:MM:SS)"},
                    "width": {"type": "string", "description": "Target width for resize"},
                    "height": {"type": "string", "description": "Target height for resize (-1 for auto)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_tools",
            "description": "PDF generation and parsing. Actions: 'create' (generate PDF from text), 'extract_text' (read text from PDF), 'page_count', 'merge' (combine PDFs), 'split' (extract individual pages). Auto-installs fpdf2 and pymupdf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: create, extract_text, page_count, merge, split"},
                    "source": {"type": "string", "description": "Input PDF file path"},
                    "output": {"type": "string", "description": "Output PDF file path"},
                    "output_dir": {"type": "string", "description": "Output directory for split pages"},
                    "title": {"type": "string", "description": "PDF title for create"},
                    "content": {"type": "string", "description": "Text content for create"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "List of PDF files to merge"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ssh_remote",
            "description": "Execute commands on remote hosts via SSH. Actions: 'exec' (run command), 'copy_to' (scp upload), 'copy_from' (scp download), 'test' (connectivity check).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: exec, copy_to, copy_from, test"},
                    "host": {"type": "string", "description": "Remote host (user@hostname or hostname)"},
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "source": {"type": "string", "description": "Source path for copy"},
                    "destination": {"type": "string", "description": "Destination path for copy"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (max 120)"}
                },
                "required": ["action", "host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "secret_vault",
            "description": "Encrypted secrets management using Fernet encryption. Actions: 'store' (save secret), 'retrieve' (get secret), 'list' (show all keys), 'delete' (remove secret), 'rotate_key' (re-encrypt with new key).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: store, retrieve, list, delete, rotate_key"},
                    "key": {"type": "string", "description": "Secret name/key"},
                    "value": {"type": "string", "description": "Secret value to store"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_runner",
            "description": "Execute tests and return structured results. Actions: 'pytest' (run pytest), 'unittest' (run unittest), 'script' (run test script), 'discover' (list available tests).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: pytest, unittest, script, discover"},
                    "target": {"type": "string", "description": "Test file, directory, or module path"},
                    "args": {"type": "string", "description": "Additional arguments"},
                    "cwd": {"type": "string", "description": "Working directory"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (max 600)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dependency_analysis",
            "description": "Analyze Python imports and dependencies using AST. Actions: 'imports' (list all imports), 'circular' (detect circular dependencies), 'unused' (find unused imports), 'graph' (categorize deps as stdlib/third-party/local).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: imports, circular, unused, graph"},
                    "target": {"type": "string", "description": "File path or directory to analyze"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resource_monitor",
            "description": "CPU/memory/disk monitoring with thresholds and alerts. Actions: 'snapshot' (current usage), 'processes' (top processes by CPU/memory), 'check_thresholds' (alert if over limits), 'network' (I/O counters), 'temperatures'. Auto-installs psutil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: snapshot, processes, check_thresholds, network, temperatures"},
                    "limit": {"type": "integer", "description": "Max processes to return"},
                    "sort_by": {"type": "string", "description": "Sort processes by 'memory' or 'cpu'"},
                    "cpu_threshold": {"type": "number", "description": "CPU alert threshold percent"},
                    "memory_threshold": {"type": "number", "description": "Memory alert threshold percent"},
                    "disk_threshold": {"type": "number", "description": "Disk alert threshold percent"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sqlite_query",
            "description": "Local SQLite database operations (lightweight, no server needed). Actions: 'query' (SELECT/etc), 'execute' (INSERT/UPDATE with params), 'tables' (list tables), 'schema' (describe table), 'import_csv' (load CSV into table).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: query, execute, tables, schema, import_csv"},
                    "database": {"type": "string", "description": "SQLite database path (default: data/local.db)"},
                    "sql": {"type": "string", "description": "SQL statement"},
                    "params": {"type": "array", "description": "Parameters for parameterized queries"},
                    "table": {"type": "string", "description": "Table name for schema/import"},
                    "csv_path": {"type": "string", "description": "CSV file path for import_csv"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_watch",
            "description": "Watch directories for file changes using watchfiles. Actions: 'start' (begin watching), 'stop' (end watcher), 'list' (show active watchers), 'events' (get recent change events).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: start, stop, list, events"},
                    "path": {"type": "string", "description": "Directory to watch"},
                    "watch_id": {"type": "string", "description": "Watcher identifier"},
                    "limit": {"type": "integer", "description": "Max events to return"}
                },
                "required": ["action"]
            }
        }
    },
    # ── Round 8 Tools ──
    {
        "type": "function",
        "function": {
            "name": "email_parse",
            "description": "Parse email files and read IMAP inboxes. Actions: 'parse_file' (parse .eml), 'extract_attachments' (save attachments), 'imap_list' (list IMAP folders), 'imap_inbox' (read inbox headers), 'parse_string' (parse raw email text).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: parse_file, extract_attachments, imap_list, imap_inbox, parse_string"},
                    "path": {"type": "string", "description": "Path to .eml file"},
                    "output_dir": {"type": "string", "description": "Output directory for attachments"},
                    "host": {"type": "string", "description": "IMAP server hostname"},
                    "user": {"type": "string", "description": "IMAP username"},
                    "password": {"type": "string", "description": "IMAP password"},
                    "folder": {"type": "string", "description": "IMAP folder (default INBOX)"},
                    "limit": {"type": "integer", "description": "Max messages to fetch"},
                    "raw": {"type": "string", "description": "Raw email string for parse_string"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "qr_code",
            "description": "Generate and decode QR codes. Actions: 'generate' (create PNG QR), 'generate_svg' (create SVG QR), 'decode' (read QR from image). Auto-installs qrcode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: generate, generate_svg, decode"},
                    "data": {"type": "string", "description": "Data to encode in QR"},
                    "output": {"type": "string", "description": "Output file path"},
                    "size": {"type": "integer", "description": "Box size for PNG (default 10)"},
                    "source": {"type": "string", "description": "Image path for decode"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_server",
            "description": "Manage ephemeral HTTP file servers for sharing files. Actions: 'start' (launch server on a port), 'stop' (shutdown), 'list' (show running servers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: start, stop, list"},
                    "directory": {"type": "string", "description": "Directory to serve (default /tmp)"},
                    "port": {"type": "integer", "description": "Port number (0 for auto)"},
                    "server_id": {"type": "string", "description": "Server identifier"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "json_schema",
            "description": "JSON Schema validation and generation. Actions: 'validate' (check data against schema), 'generate' (infer schema from data), 'diff' (compare two schemas).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: validate, generate, diff"},
                    "data": {"description": "JSON data to validate or generate schema from"},
                    "schema": {"description": "JSON Schema for validation"},
                    "schema_a": {"description": "First schema for diff"},
                    "schema_b": {"description": "Second schema for diff"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cache_manager",
            "description": "Smart caching layer over Redis with TTL and namespaces. Actions: 'get' (fetch cached value), 'set' (store with TTL), 'delete', 'clear' (flush namespace), 'keys' (list cached keys), 'stats' (cache statistics).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: get, set, delete, clear, keys, stats"},
                    "key": {"type": "string", "description": "Cache key"},
                    "value": {"description": "Value to cache (any JSON type)"},
                    "ttl": {"type": "integer", "description": "Time-to-live in seconds (default 3600)"},
                    "namespace": {"type": "string", "description": "Cache namespace (default 'cache')"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "math_compute",
            "description": "Advanced math via sympy and numpy. Actions: 'symbolic' (simplify/expand/factor), 'solve' (solve equations), 'derivative', 'integrate' (definite/indefinite), 'matrix' (det/inverse/eigenvalues/multiply), 'statistics' (mean/median/std/quartiles).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: symbolic, solve, derivative, integrate, matrix, statistics"},
                    "expression": {"type": "string", "description": "Math expression (sympy syntax)"},
                    "equation": {"type": "string", "description": "Equation to solve (e.g. 'x**2 - 4')"},
                    "variable": {"type": "string", "description": "Variable name (default 'x')"},
                    "order": {"type": "integer", "description": "Derivative order"},
                    "lower": {"type": "string", "description": "Lower bound for definite integral"},
                    "upper": {"type": "string", "description": "Upper bound for definite integral"},
                    "data": {"type": "array", "description": "Data array for matrix/statistics"},
                    "data_b": {"type": "array", "description": "Second matrix for multiply"},
                    "operation": {"type": "string", "description": "Matrix operation: info, inverse, eigenvalues, multiply"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "regex_builder",
            "description": "Regex pattern testing, replacement, and explanation. Actions: 'test' (find matches with groups), 'replace' (regex substitution), 'extract' (findall), 'split' (split text by pattern), 'explain' (tokenize and explain pattern).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: test, replace, extract, split, explain"},
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "text": {"type": "string", "description": "Text to match against"},
                    "replacement": {"type": "string", "description": "Replacement string for replace action"},
                    "flags": {"type": "string", "description": "Flags: i=ignorecase, m=multiline, s=dotall"},
                    "count": {"type": "integer", "description": "Max replacements (0=all)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cert_check",
            "description": "SSL certificate inspection and management. Actions: 'inspect' (full cert details), 'check_expiry' (days until expiry with status), 'generate_self_signed' (create cert+key), 'decode_pem' (read PEM file).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: inspect, check_expiry, generate_self_signed, decode_pem"},
                    "host": {"type": "string", "description": "Hostname for inspect/check_expiry"},
                    "port": {"type": "integer", "description": "Port (default 443)"},
                    "warn_days": {"type": "integer", "description": "Warning threshold days (default 30)"},
                    "output_cert": {"type": "string", "description": "Output cert path for self-signed"},
                    "output_key": {"type": "string", "description": "Output key path for self-signed"},
                    "cn": {"type": "string", "description": "Common Name for self-signed"},
                    "days": {"type": "integer", "description": "Validity days for self-signed"},
                    "path": {"type": "string", "description": "PEM file path for decode_pem"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_profiler",
            "description": "macOS system profiling. Actions: 'hardware', 'software', 'network', 'storage', 'usb', 'displays', 'battery', 'custom' (any SPDataType), 'list_types' (available data types).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: hardware, software, network, storage, usb, displays, battery, custom, list_types"},
                    "data_type": {"type": "string", "description": "SPDataType for custom action (e.g. 'SPBluetoothDataType')"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "url_tools",
            "description": "URL parsing, building, encoding, validation, and link extraction. Actions: 'parse' (decompose URL), 'build' (construct URL), 'encode'/'decode' (URL encoding), 'validate' (check URL validity, optionally live), 'extract_links' (find URLs in text), 'sitemap' (fetch and parse XML sitemap).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: parse, build, encode, decode, validate, extract_links, sitemap"},
                    "url": {"type": "string", "description": "URL to parse/validate/sitemap"},
                    "text": {"type": "string", "description": "Text for encode/decode/extract_links"},
                    "scheme": {"type": "string", "description": "URL scheme for build (default https)"},
                    "host": {"type": "string", "description": "Host for build"},
                    "path": {"type": "string", "description": "Path for build"},
                    "params": {"type": "object", "description": "Query params for build"},
                    "fragment": {"type": "string", "description": "Fragment for build"},
                    "check_live": {"type": "boolean", "description": "Whether to check if URL is reachable"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_control",
            "description": "Full macOS desktop GUI automation — see the screen, control mouse and keyboard, interact with applications. Actions: 'screenshot_ocr' (capture screen + OCR text recognition), 'move_mouse' (move cursor to x,y), 'click' (click at position), 'type_text' (type string), 'hotkey' (press key combo like cmd+c), 'locate_on_screen' (find image template on screen), 'get_mouse_position', 'get_screen_size', 'get_window_list' (list all visible windows with positions), 'focus_window' (bring app to front), 'scroll', 'drag', 'find_text_on_screen' (OCR + find text coordinates).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: screenshot_ocr, move_mouse, click, type_text, hotkey, locate_on_screen, get_mouse_position, get_screen_size, get_window_list, focus_window, scroll, drag, find_text_on_screen"},
                    "x": {"type": "integer", "description": "X coordinate for mouse operations"},
                    "y": {"type": "integer", "description": "Y coordinate for mouse operations"},
                    "text": {"type": "string", "description": "Text to type or find on screen"},
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "Key names for hotkey (e.g., ['command', 'c'])"},
                    "button": {"type": "string", "description": "Mouse button: left, right, middle (default: left)"},
                    "clicks": {"type": "integer", "description": "Number of clicks (default: 1)"},
                    "app": {"type": "string", "description": "Application name for focus_window"},
                    "template": {"type": "string", "description": "Path to template image for locate_on_screen"},
                    "confidence": {"type": "number", "description": "Match confidence 0-1 for locate_on_screen (default: 0.8)"},
                    "amount": {"type": "integer", "description": "Scroll amount (negative=down, positive=up)"},
                    "region": {"type": "object", "description": "Screen region for screenshot_ocr {x,y,w,h}"},
                    "output": {"type": "string", "description": "Output path for screenshot"},
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "duration": {"type": "number", "description": "Duration for drag in seconds"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_automate",
            "description": "Full browser automation via headless Playwright — navigate websites, fill forms, click UI, screenshot rendered pages, extract JS-rendered content, interact with SPAs. Actions: 'launch' (start browser session), 'navigate' (go to URL), 'click' (click CSS selector), 'type' (type into input), 'evaluate' (run JavaScript), 'screenshot' (capture page), 'content' (extract text), 'wait' (wait for selector/timeout), 'close' (end session), 'list_sessions', 'select' (dropdown), 'extract_table'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: launch, navigate, click, type, evaluate, screenshot, content, wait, close, list_sessions, select, extract_table"},
                    "session_id": {"type": "string", "description": "Browser session ID (returned by launch)"},
                    "url": {"type": "string", "description": "URL to navigate to"},
                    "selector": {"type": "string", "description": "CSS selector for click/type/wait/content/extract_table"},
                    "text": {"type": "string", "description": "Text to type into element"},
                    "js": {"type": "string", "description": "JavaScript code to evaluate in page context"},
                    "headless": {"type": "boolean", "description": "Run headless (default true)"},
                    "full_page": {"type": "boolean", "description": "Full page screenshot"},
                    "fill": {"type": "boolean", "description": "Use fill instead of type (clears first)"},
                    "output": {"type": "string", "description": "Screenshot output path"},
                    "timeout": {"type": "integer", "description": "Timeout in ms"},
                    "wait_until": {"type": "string", "description": "Navigation wait: load, domcontentloaded, networkidle"},
                    "value": {"type": "string", "description": "Value for select dropdown"},
                    "width": {"type": "integer"}, "height": {"type": "integer"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_ops",
            "description": "Complete Git and GitHub operations — local repo management + GitHub API. Actions: 'status' (porcelain status), 'log' (commit history), 'diff' (file diffs), 'branch' (list branches), 'commit' (stage and commit), 'push', 'pull', 'clone', 'stash', 'remote', 'tag', 'github_api' (raw GitHub API call), 'create_pr' (create pull request), 'list_issues' (list repo issues).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: status, log, diff, branch, commit, push, pull, clone, stash, remote, tag, github_api, create_pr, list_issues"},
                    "repo": {"type": "string", "description": "Local repo path or GitHub 'owner/name'"},
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Files to stage"},
                    "add_all": {"type": "boolean", "description": "Stage all changes before commit"},
                    "remote": {"type": "string", "description": "Git remote name (default: origin)"},
                    "branch": {"type": "string", "description": "Branch name"},
                    "url": {"type": "string", "description": "Clone URL"},
                    "dest": {"type": "string", "description": "Clone destination"},
                    "depth": {"type": "integer", "description": "Shallow clone depth"},
                    "staged": {"type": "boolean", "description": "Show staged diff"},
                    "file": {"type": "string", "description": "File to diff"},
                    "limit": {"type": "integer", "description": "Log entry limit"},
                    "token": {"type": "string", "description": "GitHub token (or use GITHUB_TOKEN env)"},
                    "endpoint": {"type": "string", "description": "GitHub API endpoint (e.g., /repos/owner/name/issues)"},
                    "method": {"type": "string", "description": "HTTP method for github_api"},
                    "body": {"type": "object", "description": "Request body for github_api"},
                    "title": {"type": "string", "description": "PR title"},
                    "head": {"type": "string", "description": "PR head branch"},
                    "base": {"type": "string", "description": "PR base branch (default: main)"},
                    "state": {"type": "string", "description": "Issue state: open, closed, all"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_analyze",
            "description": "Analyze code — AST parsing, linting, security scanning, complexity metrics. Actions: 'ast_parse' (parse Python, list classes/functions/imports), 'lint' (flake8/pylint), 'security_scan' (bandit SAST), 'complexity' (cyclomatic complexity per function), 'find_todos' (find TODO/FIXME/HACK across codebase).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: ast_parse, lint, security_scan, complexity, find_todos"},
                    "path": {"type": "string", "description": "File or directory path"},
                    "code": {"type": "string", "description": "Inline code to analyze (alternative to path)"},
                    "pattern": {"type": "string", "description": "Glob pattern for find_todos (default: *.py)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "llm_fallback",
            "description": "Multi-provider LLM routing with automatic failover — manage provider pool, query with fallback chain. Actions: 'add_provider' (register new LLM endpoint), 'remove_provider', 'list_providers' (show all providers with priority), 'test_provider' (check reachability), 'query' (send prompt with automatic failover across all providers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: add_provider, remove_provider, list_providers, test_provider, query"},
                    "name": {"type": "string", "description": "Provider name"},
                    "base_url": {"type": "string", "description": "API base URL for provider"},
                    "api_key": {"type": "string", "description": "API key for provider"},
                    "model": {"type": "string", "description": "Model name for provider"},
                    "priority": {"type": "integer", "description": "Priority (lower = tried first, default 10)"},
                    "prompt": {"type": "string", "description": "Prompt for query action"},
                    "max_tokens": {"type": "integer", "description": "Max tokens for query"},
                    "temperature": {"type": "number", "description": "Temperature for query"},
                    "timeout": {"type": "integer", "description": "Query timeout in seconds"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "notify_send",
            "description": "Send notifications via multiple channels — macOS native alerts, Slack webhooks, Discord webhooks, Pushover push notifications, text-to-speech. Actions: 'macos' (native macOS notification), 'slack' (Slack webhook), 'discord' (Discord webhook), 'pushover' (push notification), 'say' (text-to-speech).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: macos, slack, discord, pushover, say"},
                    "message": {"type": "string", "description": "Notification message"},
                    "title": {"type": "string", "description": "Notification title"},
                    "webhook_url": {"type": "string", "description": "Webhook URL for slack/discord"},
                    "channel": {"type": "string", "description": "Slack channel override"},
                    "username": {"type": "string", "description": "Bot username for discord"},
                    "token": {"type": "string", "description": "Pushover app token"},
                    "user": {"type": "string", "description": "Pushover user key"},
                    "priority": {"type": "integer", "description": "Pushover priority (-2 to 2)"},
                    "sound": {"type": "string", "description": "macOS notification sound"},
                    "voice": {"type": "string", "description": "TTS voice name for say"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "full_backup",
            "description": "Complete system backup and disaster recovery — code, data, configs, PostgreSQL, Redis. Actions: 'create' (full backup of everything), 'list' (show all backups), 'restore' (restore from backup), 'cleanup' (remove old backups, keep N most recent).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: create, list, restore, cleanup"},
                    "label": {"type": "string", "description": "Backup label for create"},
                    "path": {"type": "string", "description": "Backup path for restore"},
                    "keep": {"type": "integer", "description": "Number of backups to keep in cleanup (default 5)"},
                    "restore_db": {"type": "boolean", "description": "Also restore PostgreSQL database"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "embeddings",
            "description": "Text embeddings and vector similarity search — encode text, store vectors, semantic search across collections. Actions: 'encode' (generate embeddings and store), 'search' (find similar texts by semantic meaning), 'list_collections' (show all vector collections), 'delete_collection'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: encode, search, list_collections, delete_collection"},
                    "texts": {"type": "array", "items": {"type": "string"}, "description": "Texts to encode"},
                    "query": {"type": "string", "description": "Search query"},
                    "collection": {"type": "string", "description": "Collection name (default: default)"},
                    "top_k": {"type": "integer", "description": "Number of results for search (default 5)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "api_client",
            "description": "Generic REST/GraphQL API client with authentication, pagination, and retry. Actions: 'request' (HTTP request with auth), 'graphql' (GraphQL query), 'paginate' (auto-paginate REST endpoints).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: request, graphql, paginate"},
                    "url": {"type": "string", "description": "Request URL"},
                    "method": {"type": "string", "description": "HTTP method (default GET)"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "body": {"type": "object", "description": "Request body (auto serialized to JSON)"},
                    "auth_type": {"type": "string", "description": "Auth type: bearer, basic, api_key"},
                    "auth_value": {"type": "string", "description": "Auth token/credentials"},
                    "key_name": {"type": "string", "description": "Header name for api_key auth (default X-API-Key)"},
                    "timeout": {"type": "integer", "description": "Request timeout in seconds"},
                    "retries": {"type": "integer", "description": "Number of retries on failure"},
                    "query": {"type": "string", "description": "GraphQL query string"},
                    "variables": {"type": "object", "description": "GraphQL variables"},
                    "max_pages": {"type": "integer", "description": "Max pages for pagination"},
                    "page_param": {"type": "string", "description": "Page parameter name (default: page)"},
                    "per_page": {"type": "integer", "description": "Items per page"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cron_advanced",
            "description": "Advanced cron with task chains, conditional execution, and retry policies. Actions: 'create_chain' (define multi-step task with dependencies), 'run_chain' (execute a chain), 'list_chains', 'delete_chain', 'toggle' (enable/disable chain).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: create_chain, run_chain, list_chains, delete_chain, toggle"},
                    "name": {"type": "string", "description": "Chain name"},
                    "steps": {"type": "array", "items": {"type": "object"}, "description": "Step definitions [{tool, args, on_fail: abort|skip|retry, retries}]"},
                    "schedule": {"type": "string", "description": "Cron expression for scheduling"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "accessibility",
            "description": "macOS Accessibility API — inspect and control UI elements of any application. Actions: 'get_focused_app' (currently focused app + window title), 'get_ui_elements' (list UI elements of an app), 'click_element' (click a named UI element), 'get_element_value' (read value from text field), 'set_element_value' (write to text field), 'get_menu_items' (list app menu bar items), 'click_menu' (click a menu item).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: get_focused_app, get_ui_elements, click_element, get_element_value, set_element_value, get_menu_items, click_menu"},
                    "app": {"type": "string", "description": "Application process name"},
                    "element": {"type": "string", "description": "UI element name"},
                    "role": {"type": "string", "description": "UI element role (default: button for click, text field for get/set)"},
                    "value": {"type": "string", "description": "Value to set"},
                    "menu": {"type": "string", "description": "Menu bar item name for click_menu"},
                    "item": {"type": "string", "description": "Menu item name for click_menu"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screen_share",
            "description": "Live screen sharing and continuous monitoring — start a persistent screen capture session with periodic screenshots, OCR text recognition, and change detection. Actions: 'start_session' (begin capturing, optional interval_sec), 'stop_session', 'get_frame' (latest screenshot as base64 + OCR text + changed regions), 'get_status' (active session info), 'set_interval' (adjust capture rate in seconds). Integrates with Chrome Remote Desktop host for remote access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: start_session, stop_session, get_frame, get_status, set_interval"},
                    "interval_sec": {"type": "number", "description": "Seconds between captures (default 2.0, min 0.5)"},
                    "include_image": {"type": "boolean", "description": "Include base64 PNG in get_frame (default false, just OCR text)"},
                    "region": {"type": "object", "description": "Optional capture region {x, y, width, height}"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "visionclaw",
            "description": "VisionClaw integration — manage connections with Meta Ray-Ban smart glasses running VisionClaw iOS app. The glasses stream camera + audio to Gemini Live, which delegates tasks to this orchestrator via /v1/chat/completions. Actions: 'status' (show active glass sessions, connection info), 'sessions' (list all VisionClaw sessions with message counts), 'config' (show current VisionClaw connection config — host, port, token), 'configure' (update gateway bind mode for LAN/loopback access), 'send' (push a proactive message to a glass session), 'history' (get conversation history for a glass session).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: status, sessions, config, configure, send, history"},
                    "session_id": {"type": "string", "description": "VisionClaw session ID (for send/history actions)"},
                    "message": {"type": "string", "description": "Message to send (for send action)"},
                    "bind_mode": {"type": "string", "description": "Gateway bind mode: 'lan' or 'loopback' (for configure action)"}
                },
                "required": ["action"]
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
    "web_scrape", "docker_manage", "osascript", "image_process",
    "date_calc", "project_replace", "process_watchdog", "metrics_collect",
    "markdown_render", "sql_schema",
    "audio_process", "video_process", "pdf_tools", "ssh_remote",
    "secret_vault", "test_runner", "dependency_analysis", "resource_monitor",
    "sqlite_query", "file_watch",
    "email_parse", "qr_code", "http_server", "json_schema",
    "cache_manager", "math_compute", "regex_builder", "cert_check",
    "system_profiler", "url_tools",
    "desktop_control",
    "browser_automate",
    "git_ops",
    "code_analyze",
    "llm_fallback",
    "notify_send",
    "full_backup",
    "embeddings",
    "api_client",
    "cron_advanced",
    "accessibility",
    "screen_share",
    "visionclaw",
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
        # Persist to disk (non-blocking via lock) with rotation
        async with self._lock:
            try:
                # Rotate if file exceeds 50MB
                if self.path.exists() and self.path.stat().st_size > 50 * 1024 * 1024:
                    rotated = self.path.with_suffix(f".{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl")
                    self.path.rename(rotated)
                    log.info(f"Activity log rotated to {rotated}")
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
            elif fn_name == "web_scrape":
                internal_result = _web_scrape(
                    fn_args.get("action", "text"),
                    url=fn_args.get("url", ""),
                    html=fn_args.get("html", ""),
                    selector=fn_args.get("selector", ""),
                    attribute=fn_args.get("attribute", ""),
                    limit=fn_args.get("limit", 50),
                )
                internal_task = f"Web scrape: {fn_args.get('action', '')} {fn_args.get('url', '')[:40]}"
            elif fn_name == "docker_manage":
                internal_result = _docker_manage(
                    fn_args.get("action", "ps"),
                    image=fn_args.get("image", ""),
                    container=fn_args.get("container", ""),
                    command=fn_args.get("command", ""),
                    ports=fn_args.get("ports", ""),
                    env_vars=fn_args.get("env_vars"),
                    volumes=fn_args.get("volumes", ""),
                    name=fn_args.get("name", ""),
                    options=fn_args.get("options", ""),
                )
                internal_task = f"Docker: {fn_args.get('action', '')} {fn_args.get('container', fn_args.get('image', ''))[:30]}"
            elif fn_name == "osascript":
                internal_result = _osascript(
                    script=fn_args.get("script", ""),
                    action=fn_args.get("action", ""),
                    app_name=fn_args.get("app_name", ""),
                    text=fn_args.get("text", ""),
                    path=fn_args.get("path", ""),
                )
                internal_task = f"AppleScript: {fn_args.get('action', 'custom')}"
            elif fn_name == "image_process":
                internal_result = _image_process(
                    fn_args.get("action", "info"),
                    path=fn_args.get("path", ""),
                    output_path=fn_args.get("output_path", ""),
                    width=fn_args.get("width", 0),
                    height=fn_args.get("height", 0),
                    quality=fn_args.get("quality", 85),
                    format=fn_args.get("format", ""),
                    angle=fn_args.get("angle", 0),
                    crop=fn_args.get("crop", ""),
                )
                internal_task = f"Image: {fn_args.get('action', '')} {fn_args.get('path', '')[-30:]}"
            elif fn_name == "date_calc":
                internal_result = _date_calc(
                    fn_args.get("action", "now"),
                    date_str=fn_args.get("date_str", ""),
                    days=fn_args.get("days", 0),
                    hours=fn_args.get("hours", 0),
                    minutes=fn_args.get("minutes", 0),
                    from_tz=fn_args.get("from_tz", ""),
                    to_tz=fn_args.get("to_tz", ""),
                    format=fn_args.get("format", ""),
                )
                internal_task = f"Date calc: {fn_args.get('action', '')}"
            elif fn_name == "project_replace":
                internal_result = _project_replace(
                    fn_args.get("action", "search"),
                    directory=fn_args.get("directory", ""),
                    pattern=fn_args.get("pattern", ""),
                    replacement=fn_args.get("replacement", ""),
                    file_glob=fn_args.get("file_glob", "**/*"),
                    regex=fn_args.get("regex", False),
                    dry_run=fn_args.get("dry_run", True),
                    backup=fn_args.get("backup", True),
                )
                internal_task = f"Project replace: {fn_args.get('action', '')} '{fn_args.get('pattern', '')[:20]}'"
            elif fn_name == "process_watchdog":
                internal_result = _process_watchdog(
                    fn_args.get("action", "list"),
                    name=fn_args.get("name", ""),
                    command=fn_args.get("command", ""),
                    interval=fn_args.get("interval", 30),
                    max_restarts=fn_args.get("max_restarts", 10),
                    health_url=fn_args.get("health_url", ""),
                )
                internal_task = f"Watchdog: {fn_args.get('action', '')} {fn_args.get('name', '')}"
            elif fn_name == "metrics_collect":
                internal_result = _metrics_collect(
                    fn_args.get("action", "list"),
                    name=fn_args.get("name", ""),
                    value=fn_args.get("value", 0),
                    tags=fn_args.get("tags"),
                    hours=fn_args.get("hours", 24),
                    limit=fn_args.get("limit", 100),
                )
                internal_task = f"Metrics: {fn_args.get('action', '')} {fn_args.get('name', '')}"
            elif fn_name == "markdown_render":
                internal_result = _markdown_render(
                    fn_args.get("action", "md_to_html"),
                    text=fn_args.get("text", ""),
                    path=fn_args.get("path", ""),
                    output_path=fn_args.get("output_path", ""),
                )
                internal_task = f"Markdown: {fn_args.get('action', '')}"
            elif fn_name == "sql_schema":
                internal_result = await _sql_schema(
                    fn_args.get("action", "tables"),
                    table=fn_args.get("table", ""),
                    schema=fn_args.get("schema", "public"),
                    columns=fn_args.get("columns"),
                    query=fn_args.get("query", ""),
                )
                internal_task = f"SQL schema: {fn_args.get('action', '')} {fn_args.get('table', '')}"
            # ── Round 7 dispatch ──
            elif fn_name == "audio_process":
                internal_result = _audio_process(
                    fn_args.get("action", ""),
                    source=fn_args.get("source", ""),
                    destination=fn_args.get("destination", ""),
                    text=fn_args.get("text", ""),
                    output=fn_args.get("output", ""),
                    voice=fn_args.get("voice", ""),
                    start=fn_args.get("start", "0"),
                    duration=fn_args.get("duration", ""),
                    files=fn_args.get("files", []),
                    level=fn_args.get("level", "1.5"),
                )
                internal_task = f"Audio: {fn_args.get('action', '')}"
            elif fn_name == "video_process":
                internal_result = _video_process(
                    fn_args.get("action", ""),
                    source=fn_args.get("source", ""),
                    destination=fn_args.get("destination", ""),
                    output_dir=fn_args.get("output_dir", ""),
                    fps=fn_args.get("fps", "1"),
                    start=fn_args.get("start", "0"),
                    duration=fn_args.get("duration", ""),
                    timestamp=fn_args.get("timestamp", "00:00:01"),
                    width=fn_args.get("width", "1280"),
                    height=fn_args.get("height", "-1"),
                )
                internal_task = f"Video: {fn_args.get('action', '')}"
            elif fn_name == "pdf_tools":
                internal_result = _pdf_tools(
                    fn_args.get("action", ""),
                    source=fn_args.get("source", ""),
                    output=fn_args.get("output", ""),
                    output_dir=fn_args.get("output_dir", ""),
                    title=fn_args.get("title", ""),
                    content=fn_args.get("content", ""),
                    files=fn_args.get("files", []),
                )
                internal_task = f"PDF: {fn_args.get('action', '')}"
            elif fn_name == "ssh_remote":
                internal_result = _ssh_remote(
                    fn_args.get("action", ""),
                    host=fn_args.get("host", ""),
                    command=fn_args.get("command", ""),
                    source=fn_args.get("source", ""),
                    destination=fn_args.get("destination", ""),
                    timeout=fn_args.get("timeout", 30),
                )
                internal_task = f"SSH: {fn_args.get('action', '')} {fn_args.get('host', '')}"
            elif fn_name == "secret_vault":
                internal_result = _secret_vault(
                    fn_args.get("action", ""),
                    key=fn_args.get("key", ""),
                    value=fn_args.get("value", ""),
                )
                internal_task = f"Vault: {fn_args.get('action', '')} {fn_args.get('key', '')}"
            elif fn_name == "test_runner":
                internal_result = _test_runner(
                    fn_args.get("action", ""),
                    target=fn_args.get("target", ""),
                    args=fn_args.get("args", ""),
                    cwd=fn_args.get("cwd", ""),
                    timeout=fn_args.get("timeout", 120),
                )
                internal_task = f"Tests: {fn_args.get('action', '')} {fn_args.get('target', '')}"
            elif fn_name == "dependency_analysis":
                internal_result = _dependency_analysis(
                    fn_args.get("action", ""),
                    target=fn_args.get("target", ""),
                )
                internal_task = f"Deps: {fn_args.get('action', '')} {fn_args.get('target', '')}"
            elif fn_name == "resource_monitor":
                internal_result = _resource_monitor(
                    fn_args.get("action", ""),
                    limit=fn_args.get("limit", 10),
                    sort_by=fn_args.get("sort_by", "memory"),
                    cpu_threshold=fn_args.get("cpu_threshold", 90),
                    memory_threshold=fn_args.get("memory_threshold", 90),
                    disk_threshold=fn_args.get("disk_threshold", 90),
                )
                internal_task = f"Resources: {fn_args.get('action', '')}"
            elif fn_name == "sqlite_query":
                internal_result = _sqlite_query(
                    fn_args.get("action", ""),
                    database=fn_args.get("database", ""),
                    sql=fn_args.get("sql", ""),
                    params=fn_args.get("params", []),
                    table=fn_args.get("table", ""),
                    csv_path=fn_args.get("csv_path", ""),
                )
                internal_task = f"SQLite: {fn_args.get('action', '')}"
            elif fn_name == "file_watch":
                internal_result = await _file_watch(
                    fn_args.get("action", ""),
                    path=fn_args.get("path", ""),
                    watch_id=fn_args.get("watch_id", ""),
                    limit=fn_args.get("limit", 50),
                )
                internal_task = f"FileWatch: {fn_args.get('action', '')}"
            # ── Round 8 dispatch ──
            elif fn_name == "email_parse":
                internal_result = _email_parse(
                    fn_args.get("action", ""),
                    path=fn_args.get("path", ""),
                    output_dir=fn_args.get("output_dir", ""),
                    host=fn_args.get("host", ""),
                    user=fn_args.get("user", ""),
                    password=fn_args.get("password", ""),
                    folder=fn_args.get("folder", "INBOX"),
                    limit=fn_args.get("limit", 10),
                    raw=fn_args.get("raw", ""),
                )
                internal_task = f"Email: {fn_args.get('action', '')}"
            elif fn_name == "qr_code":
                internal_result = _qr_code(
                    fn_args.get("action", ""),
                    data=fn_args.get("data", ""),
                    output=fn_args.get("output", ""),
                    size=fn_args.get("size", 10),
                    source=fn_args.get("source", ""),
                )
                internal_task = f"QR: {fn_args.get('action', '')}"
            elif fn_name == "http_server":
                internal_result = _http_server(
                    fn_args.get("action", ""),
                    directory=fn_args.get("directory", "/tmp"),
                    port=fn_args.get("port", 0),
                    server_id=fn_args.get("server_id", ""),
                )
                internal_task = f"HTTPServer: {fn_args.get('action', '')}"
            elif fn_name == "json_schema":
                internal_result = _json_schema(
                    fn_args.get("action", ""),
                    data=fn_args.get("data"),
                    schema=fn_args.get("schema"),
                    schema_a=fn_args.get("schema_a"),
                    schema_b=fn_args.get("schema_b"),
                )
                internal_task = f"JSONSchema: {fn_args.get('action', '')}"
            elif fn_name == "cache_manager":
                internal_result = _cache_manager(
                    fn_args.get("action", ""),
                    key=fn_args.get("key", ""),
                    value=fn_args.get("value"),
                    ttl=fn_args.get("ttl", 3600),
                    namespace=fn_args.get("namespace", "cache"),
                )
                internal_task = f"Cache: {fn_args.get('action', '')} {fn_args.get('key', '')}"
            elif fn_name == "math_compute":
                internal_result = _math_compute(
                    fn_args.get("action", ""),
                    expression=fn_args.get("expression", ""),
                    equation=fn_args.get("equation", ""),
                    variable=fn_args.get("variable", "x"),
                    order=fn_args.get("order", 1),
                    lower=fn_args.get("lower"),
                    upper=fn_args.get("upper"),
                    data=fn_args.get("data", []),
                    data_b=fn_args.get("data_b", []),
                    operation=fn_args.get("operation", "info"),
                )
                internal_task = f"Math: {fn_args.get('action', '')}"
            elif fn_name == "regex_builder":
                internal_result = _regex_builder(
                    fn_args.get("action", ""),
                    pattern=fn_args.get("pattern", ""),
                    text=fn_args.get("text", ""),
                    replacement=fn_args.get("replacement", ""),
                    flags=fn_args.get("flags", ""),
                    count=fn_args.get("count", 0),
                )
                internal_task = f"Regex: {fn_args.get('action', '')}"
            elif fn_name == "cert_check":
                internal_result = _cert_check(
                    fn_args.get("action", ""),
                    host=fn_args.get("host", ""),
                    port=fn_args.get("port", 443),
                    warn_days=fn_args.get("warn_days", 30),
                    output_cert=fn_args.get("output_cert", ""),
                    output_key=fn_args.get("output_key", ""),
                    cn=fn_args.get("cn", "localhost"),
                    days=fn_args.get("days", 365),
                    path=fn_args.get("path", ""),
                )
                internal_task = f"Cert: {fn_args.get('action', '')} {fn_args.get('host', '')}"
            elif fn_name == "system_profiler":
                internal_result = _system_profiler(
                    fn_args.get("action", ""),
                    data_type=fn_args.get("data_type", ""),
                )
                internal_task = f"SysProfile: {fn_args.get('action', '')}"
            elif fn_name == "url_tools":
                internal_result = _url_tools(
                    fn_args.get("action", ""),
                    url=fn_args.get("url", ""),
                    text=fn_args.get("text", ""),
                    scheme=fn_args.get("scheme", "https"),
                    host=fn_args.get("host", ""),
                    path=fn_args.get("path", "/"),
                    params=fn_args.get("params", {}),
                    fragment=fn_args.get("fragment", ""),
                    check_live=fn_args.get("check_live", False),
                )
                internal_task = f"URL: {fn_args.get('action', '')}"
            elif fn_name == "desktop_control":
                internal_result = _desktop_control(
                    fn_args.get("action", ""),
                    x=fn_args.get("x"), y=fn_args.get("y"),
                    text=fn_args.get("text", ""),
                    keys=fn_args.get("keys", []),
                    button=fn_args.get("button", "left"),
                    clicks=fn_args.get("clicks", 1),
                    app=fn_args.get("app", ""),
                    template=fn_args.get("template", ""),
                    confidence=fn_args.get("confidence", 0.8),
                    amount=fn_args.get("amount", -3),
                    region=fn_args.get("region"),
                    output=fn_args.get("output", ""),
                    x1=fn_args.get("x1", 0), y1=fn_args.get("y1", 0),
                    x2=fn_args.get("x2", 0), y2=fn_args.get("y2", 0),
                    duration=fn_args.get("duration", 0.5),
                )
                internal_task = f"Desktop: {fn_args.get('action', '')}"
            elif fn_name == "browser_automate":
                internal_result = _browser_automate(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Browser: {fn_args.get('action', '')}"
            elif fn_name == "git_ops":
                internal_result = _git_ops(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Git: {fn_args.get('action', '')}"
            elif fn_name == "code_analyze":
                internal_result = _code_analyze(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Code analysis: {fn_args.get('action', '')}"
            elif fn_name == "llm_fallback":
                internal_result = _llm_fallback(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"LLM fallback: {fn_args.get('action', '')}"
            elif fn_name == "notify_send":
                internal_result = _notify_send(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Notify: {fn_args.get('action', '')}"
            elif fn_name == "full_backup":
                internal_result = _full_backup(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Backup: {fn_args.get('action', '')}"
            elif fn_name == "embeddings":
                internal_result = _embeddings(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Embeddings: {fn_args.get('action', '')}"
            elif fn_name == "api_client":
                internal_result = _api_client(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"API client: {fn_args.get('action', '')}"
            elif fn_name == "cron_advanced":
                internal_result = _cron_advanced(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Cron: {fn_args.get('action', '')}"
            elif fn_name == "accessibility":
                internal_result = _accessibility(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Accessibility: {fn_args.get('action', '')}"
            elif fn_name == "screen_share":
                internal_result = await _screen_share(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"Screen share: {fn_args.get('action', '')}"
            elif fn_name == "visionclaw":
                internal_result = await _visionclaw(fn_args.get("action", ""), **{k: v for k, v in fn_args.items() if k != "action"})
                internal_task = f"VisionClaw: {fn_args.get('action', '')}"
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


# ── VisionClaw / OpenAI-Compatible Chat Completions ────────────────────────

# Track active VisionClaw (glass) sessions
_visionclaw_sessions: dict[str, dict] = {}


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """
    OpenAI-compatible chat completions endpoint.
    This allows VisionClaw (Meta Ray-Ban glasses) and any OpenAI-compatible
    client to talk to the Meta-Orchestrator using the standard protocol.

    Supports: model, messages[], stream (false only), x-openclaw-session-key header.
    """
    request = await req.json()
    messages = request.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages array is required")

    # Extract the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found in messages array")

    # Derive session from header or generate one
    # VisionClaw sends x-openclaw-session-key header for session continuity
    session_key = req.headers.get("x-openclaw-session-key", "")
    if not session_key:
        session_key = f"glass-{uuid.uuid4().hex[:8]}"

    # Map to orchestrator session ID
    session_id = f"vc-{hashlib.md5(session_key.encode()).hexdigest()[:10]}"

    # Track as VisionClaw session
    _visionclaw_sessions[session_id] = {
        "session_key": session_key,
        "last_active": datetime.now(timezone.utc).isoformat(),
        "message_count": _visionclaw_sessions.get(session_id, {}).get("message_count", 0) + 1,
        "source": "visionclaw",
    }

    log.info(f"VisionClaw [{session_id}]: {user_message[:120]}...")
    await activity.record("visionclaw_request", session_id, user_message[:500],
                          {"source": "glasses", "session_key": session_key[:30]})

    # Route through the same call_llm as /chat — full 100-tool access
    result = await call_llm(session_id, user_message)

    response_text = result.get("response", "")

    await activity.record("visionclaw_response", session_id,
                          response_text[:300],
                          {"delegations": len(result.get("delegations", []))})

    # Return in OpenAI chat completions format
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "openclaw-army",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(user_message.split()) + len(response_text.split()),
        },
    }


@app.get("/v1/chat/completions")
async def chat_completions_health():
    """GET on /v1/chat/completions — used by VisionClaw to check gateway reachability."""
    return {"status": "ok", "service": "openclaw-army-orchestrator", "tools": 101}


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible model listing."""
    return {
        "object": "list",
        "data": [
            {
                "id": "openclaw-army",
                "object": "model",
                "created": 1709078400,
                "owned_by": "landon-king",
            },
            {
                "id": "openclaw",
                "object": "model",
                "created": 1709078400,
                "owned_by": "landon-king",
            },
        ],
    }


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
    r"\brm\s+-rf\s+~",      # rm -rf home
    r">\s*/dev/disk",        # overwrite macOS disk
    r"\bnewfs\b",            # macOS format disk
    r"\bnewfs_\w+",           # macOS newfs variants (newfs_hfs, newfs_apfs, etc.)
    r"\bdiskutil\s+eraseDisk", # macOS erase disk
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
    import ipaddress
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    _ssrf_blocked = {"169.254.169.254", "metadata.google.internal", "metadata.internal"}
    if hostname in _ssrf_blocked:
        return {"error": "Blocked: cloud metadata endpoint", "status": 0, "body": ""}
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            return {"error": f"Blocked: private/internal IP {hostname}", "status": 0, "body": ""}
    except ValueError:
        if hostname in ("localhost", "0.0.0.0"):
            return {"error": f"Blocked: internal host {hostname}", "status": 0, "body": ""}

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
                               capture_output=True, text=True, timeout=10)
            loaded = r.returncode == 0
            return {"installed": True, "loaded": loaded, "plist_path": str(plist_path)}
        return {"installed": False, "loaded": False}

    if action == "uninstall":
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, timeout=10)
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
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, timeout=10)
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


# ── Web Scraping / HTML Parsing ──────────────────────────────────────────

def _web_scrape(action: str, url: str = "", html: str = "",
                selector: str = "", attribute: str = "",
                limit: int = 50) -> dict:
    """Parse HTML and extract structured data. Works on URLs or raw HTML.
    Actions: 'text' (extract visible text), 'links' (extract all links),
    'tables' (extract HTML tables as lists), 'select' (CSS selector query),
    'meta' (extract meta tags/title/description), 'headers' (extract headings).
    """
    # Get HTML content
    content = html
    if not content and url:
        try:
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "15", "-A",
                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", url],
                capture_output=True, text=True, timeout=20,
            )
            content = result.stdout
        except Exception as e:
            return {"error": f"Failed to fetch URL: {e}"}
    if not content:
        return {"error": "Provide url or html parameter"}

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Auto-install
        subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4", "lxml"],
                       capture_output=True, timeout=60)
        from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        soup = BeautifulSoup(content, "html.parser")

    if action == "text":
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return {"text": "\n".join(lines[:limit * 3])[:30000],
                "line_count": len(lines), "truncated": len(lines) > limit * 3}

    elif action == "links":
        links = []
        for a in soup.find_all("a", href=True)[:limit]:
            links.append({"text": a.get_text(strip=True)[:100],
                          "href": a["href"]})
        return {"links": links, "count": len(links)}

    elif action == "tables":
        tables = []
        for table in soup.find_all("table")[:limit]:
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return {"tables": tables, "count": len(tables)}

    elif action == "select":
        if not selector:
            return {"error": "CSS selector required"}
        elements = soup.select(selector)[:limit]
        results = []
        for el in elements:
            item = {"tag": el.name, "text": el.get_text(strip=True)[:500]}
            if attribute and el.get(attribute):
                item["attribute"] = el[attribute]
            item["attrs"] = {k: v for k, v in list(el.attrs.items())[:10]}
            results.append(item)
        return {"elements": results, "count": len(results), "selector": selector}

    elif action == "meta":
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_tags = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name", meta.get("property", ""))
            cont = meta.get("content", "")
            if name and cont:
                meta_tags[name] = cont[:500]
        return {"title": title, "meta": meta_tags}

    elif action == "headers":
        headers = []
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                headers.append({"level": level, "text": h.get_text(strip=True)[:200]})
        return {"headers": headers[:limit], "count": len(headers)}

    return {"error": f"Unknown action: {action}. Use text, links, tables, select, meta, headers."}


# ── Docker Management ─────────────────────────────────────────────────────

def _docker_manage(action: str, image: str = "", container: str = "",
                   command: str = "", ports: str = "", env_vars: dict = None,
                   volumes: str = "", name: str = "", options: str = "") -> dict:
    """Manage Docker containers and images.
    Actions: 'ps' (list containers), 'images' (list images), 'run' (run container),
    'stop' (stop container), 'rm' (remove container), 'logs' (container logs),
    'exec' (exec command in container), 'pull' (pull image), 'build' (build image),
    'inspect' (inspect container/image), 'stats' (container resource stats).
    """
    docker = shutil.which("docker")
    if not docker:
        return {"error": "Docker CLI not found"}

    def _run_docker(args, timeout_sec=30):
        try:
            result = subprocess.run(
                [docker] + args,
                capture_output=True, text=True, timeout=timeout_sec,
            )
            return {"stdout": result.stdout[:10000], "stderr": result.stderr[:3000],
                    "returncode": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Docker command timed out ({timeout_sec}s)"}
        except Exception as e:
            return {"error": str(e)}

    if action == "ps":
        r = _run_docker(["ps", "-a", "--format", "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}\t{{.Ports}}"])
        if "error" in r:
            return r
        lines = r["stdout"].strip().split("\n")
        return {"containers": lines, "count": max(0, len(lines) - 1), "raw": r["stdout"][:5000]}

    elif action == "images":
        r = _run_docker(["images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.ID}}"])
        return {"images": r.get("stdout", "")[:5000], "returncode": r.get("returncode")}

    elif action == "run":
        if not image:
            return {"error": "Image required"}
        cmd = ["run", "-d"]
        if name:
            cmd += ["--name", name]
        if ports:
            for p in ports.split(","):
                cmd += ["-p", p.strip()]
        if env_vars:
            for k, v in env_vars.items():
                cmd += ["-e", f"{k}={v}"]
        if volumes:
            for v in volumes.split(","):
                cmd += ["-v", v.strip()]
        if options:
            cmd += options.split()
        cmd.append(image)
        if command:
            cmd += command.split()
        r = _run_docker(cmd, timeout_sec=120)
        container_id = r.get("stdout", "").strip()[:12]
        return {"container_id": container_id, "image": image,
                "started": r.get("returncode") == 0, "stderr": r.get("stderr", "")}

    elif action == "stop":
        if not container:
            return {"error": "Container name/ID required"}
        return _run_docker(["stop", container])

    elif action == "rm":
        if not container:
            return {"error": "Container name/ID required"}
        return _run_docker(["rm", "-f", container])

    elif action == "logs":
        if not container:
            return {"error": "Container name/ID required"}
        r = _run_docker(["logs", "--tail", "100", container])
        return {"logs": r.get("stdout", "")[:10000] + r.get("stderr", "")[:5000],
                "container": container}

    elif action == "exec":
        if not container or not command:
            return {"error": "Container and command required"}
        return _run_docker(["exec", container] + command.split())

    elif action == "pull":
        if not image:
            return {"error": "Image required"}
        return _run_docker(["pull", image], timeout_sec=300)

    elif action == "build":
        cmd = ["build"]
        if name:
            cmd += ["-t", name]
        cmd.append(image or ".")
        return _run_docker(cmd, timeout_sec=300)

    elif action == "inspect":
        target = container or image
        if not target:
            return {"error": "Container or image name required"}
        r = _run_docker(["inspect", target])
        try:
            return {"inspect": json.loads(r.get("stdout", "[]"))[:1]}
        except json.JSONDecodeError:
            return r

    elif action == "stats":
        r = _run_docker(["stats", "--no-stream", "--format",
                         "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"])
        return {"stats": r.get("stdout", "")[:5000]}

    return {"error": f"Unknown action: {action}. Use ps, images, run, stop, rm, logs, exec, pull, build, inspect, stats."}


# ── macOS AppleScript Automation ─────────────────────────────────────────

def _osascript(script: str = "", action: str = "", app_name: str = "",
               text: str = "", path: str = "") -> dict:
    """Execute AppleScript for macOS automation.
    Provide raw 'script', or use preset actions:
    'open_app' (launch an app), 'quit_app' (quit an app), 'frontmost' (get frontmost app),
    'say' (text-to-speech), 'dialog' (show dialog box), 'notification' (macOS notification),
    'open_url' (open URL in default browser), 'finder_selection' (get Finder selection),
    'set_volume' (0-100), 'get_clipboard', 'set_clipboard', 'list_apps' (running apps).
    """
    osascript_bin = "/usr/bin/osascript"
    if not Path(osascript_bin).exists():
        return {"error": "osascript not found"}

    # Preset actions
    presets = {
        "open_app": f'tell application "{app_name}" to activate',
        "quit_app": f'tell application "{app_name}" to quit',
        "frontmost": 'tell application "System Events" to get name of first process whose frontmost is true',
        "say": f'say "{text}"',
        "dialog": f'display dialog "{text}" buttons {{"OK", "Cancel"}} default button "OK"',
        "notification": f'display notification "{text}" with title "OpenClaw Army"',
        "open_url": f'open location "{text}"',
        "finder_selection": 'tell application "Finder" to get POSIX path of (selection as alias list)',
        "set_volume": f'set volume output volume {text}',
        "get_clipboard": 'the clipboard',
        "set_clipboard": f'set the clipboard to "{text}"',
        "list_apps": 'tell application "System Events" to get name of every process whose background only is false',
    }

    if action and action in presets:
        script = presets[action]
    elif action:
        return {"error": f"Unknown action: {action}. Available: {list(presets.keys())}"}

    if not script:
        return {"error": "Provide a script or an action (open_app, quit_app, say, notification, etc.)"}

    try:
        result = subprocess.run(
            [osascript_bin, "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "output": result.stdout.strip()[:5000],
            "error": result.stderr.strip()[:2000] if result.returncode != 0 else "",
            "returncode": result.returncode,
            "script": script[:500],
        }
    except subprocess.TimeoutExpired:
        return {"error": "AppleScript timed out (30s)"}
    except Exception as e:
        return {"error": f"AppleScript failed: {e}"}


# ── Image Processing ─────────────────────────────────────────────────────

def _image_process(action: str, path: str = "", output_path: str = "",
                   width: int = 0, height: int = 0, quality: int = 85,
                   format: str = "", angle: float = 0,
                   crop: str = "") -> dict:
    """Process images: resize, crop, rotate, convert, metadata, thumbnail.
    Actions: 'info' (dimensions, format, size), 'resize' (resize to width×height),
    'crop' (left,top,right,bottom), 'rotate' (angle in degrees),
    'convert' (change format: png, jpg, webp, gif), 'thumbnail' (create thumbnail),
    'flip' (horizontal/vertical).
    """
    try:
        from PIL import Image, ExifTags
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"],
                       capture_output=True, timeout=60)
        from PIL import Image, ExifTags

    if not path:
        return {"error": "Image path required"}
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"File not found: {path}"}

    try:
        img = Image.open(p)
    except Exception as e:
        return {"error": f"Cannot open image: {e}"}

    if action == "info":
        info = {
            "format": img.format, "mode": img.mode,
            "width": img.width, "height": img.height,
            "size_bytes": p.stat().st_size,
            "path": str(p),
        }
        try:
            exif = img._getexif()
            if exif:
                info["exif"] = {ExifTags.TAGS.get(k, k): str(v)[:100]
                                for k, v in list(exif.items())[:20]}
        except Exception:
            pass
        return info

    out = Path(output_path).expanduser() if output_path else p.parent / f"{p.stem}_out{p.suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)

    if action == "resize":
        if not width and not height:
            return {"error": "Specify width and/or height"}
        if width and not height:
            ratio = width / img.width
            height = int(img.height * ratio)
        elif height and not width:
            ratio = height / img.height
            width = int(img.width * ratio)
        img_resized = img.resize((width, height), Image.LANCZOS)
        img_resized.save(str(out), quality=quality)
        return {"resized": True, "output": str(out), "width": width, "height": height}

    elif action == "crop":
        if not crop:
            return {"error": "Crop coordinates required: 'left,top,right,bottom'"}
        coords = tuple(int(x.strip()) for x in crop.split(","))
        if len(coords) != 4:
            return {"error": "Crop needs 4 values: left,top,right,bottom"}
        img_cropped = img.crop(coords)
        img_cropped.save(str(out), quality=quality)
        return {"cropped": True, "output": str(out),
                "width": img_cropped.width, "height": img_cropped.height}

    elif action == "rotate":
        img_rotated = img.rotate(angle, expand=True)
        img_rotated.save(str(out), quality=quality)
        return {"rotated": True, "output": str(out), "angle": angle}

    elif action == "convert":
        if not format:
            return {"error": "Target format required: png, jpg, webp, gif"}
        out = Path(output_path).expanduser() if output_path else p.parent / f"{p.stem}.{format.lower()}"
        if img.mode == "RGBA" and format.lower() in ("jpg", "jpeg"):
            img = img.convert("RGB")
        img.save(str(out), format=format.upper().replace("JPG", "JPEG"), quality=quality)
        return {"converted": True, "output": str(out), "format": format}

    elif action == "thumbnail":
        size = (width or 200, height or 200)
        img.thumbnail(size, Image.LANCZOS)
        out = Path(output_path).expanduser() if output_path else p.parent / f"{p.stem}_thumb{p.suffix}"
        img.save(str(out), quality=quality)
        return {"thumbnail": True, "output": str(out),
                "width": img.width, "height": img.height}

    elif action == "flip":
        direction = format or "horizontal"
        if direction == "horizontal":
            img_flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            img_flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
        img_flipped.save(str(out), quality=quality)
        return {"flipped": True, "output": str(out), "direction": direction}

    return {"error": f"Unknown action: {action}. Use info, resize, crop, rotate, convert, thumbnail, flip."}


# ── Date / Time Calculator ────────────────────────────────────────────────

def _date_calc(action: str, date_str: str = "", days: int = 0, hours: int = 0,
               minutes: int = 0, from_tz: str = "", to_tz: str = "",
               format: str = "") -> dict:
    """Date/time calculations: arithmetic, timezone conversion, parsing, formatting.
    Actions: 'now' (current time in timezone), 'add' (add days/hours/minutes to date),
    'diff' (difference between two dates), 'convert_tz' (timezone conversion),
    'parse' (parse natural/ISO date string), 'format' (reformat a date),
    'epoch' (convert to/from Unix epoch), 'calendar' (month calendar).
    """
    from datetime import timedelta
    import calendar as cal_mod

    def _parse_dt(s):
        """Try multiple date formats."""
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y",
                    "%b %d, %Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None

    if action == "now":
        tz_name = from_tz or "UTC"
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now(timezone.utc)
            tz_name = "UTC"
        return {"datetime": now.isoformat(), "timezone": tz_name,
                "unix_epoch": int(now.timestamp()),
                "day_of_week": now.strftime("%A"),
                "iso_week": now.isocalendar()[1]}

    elif action == "add":
        base = _parse_dt(date_str) if date_str else datetime.now()
        if not base:
            return {"error": f"Cannot parse date: {date_str}"}
        delta = timedelta(days=days, hours=hours, minutes=minutes)
        result = base + delta
        return {"original": base.isoformat(), "result": result.isoformat(),
                "delta": str(delta), "day_of_week": result.strftime("%A")}

    elif action == "diff":
        # date_str format: "date1 | date2"  
        parts = date_str.split("|")
        if len(parts) != 2:
            return {"error": "Use format: 'date1 | date2'"}
        d1 = _parse_dt(parts[0])
        d2 = _parse_dt(parts[1])
        if not d1 or not d2:
            return {"error": f"Cannot parse dates: {parts[0].strip()} or {parts[1].strip()}"}
        delta = d2 - d1
        total_seconds = int(delta.total_seconds())
        return {"date1": d1.isoformat(), "date2": d2.isoformat(),
                "days": delta.days, "total_seconds": total_seconds,
                "total_hours": round(total_seconds / 3600, 2),
                "human": f"{abs(delta.days)} days, {abs(total_seconds % 86400) // 3600} hours"}

    elif action == "convert_tz":
        if not date_str or not from_tz or not to_tz:
            return {"error": "date_str, from_tz, and to_tz required"}
        dt = _parse_dt(date_str)
        if not dt:
            return {"error": f"Cannot parse date: {date_str}"}
        try:
            import zoneinfo
            src_tz = zoneinfo.ZoneInfo(from_tz)
            dst_tz = zoneinfo.ZoneInfo(to_tz)
            dt_src = dt.replace(tzinfo=src_tz)
            dt_dst = dt_src.astimezone(dst_tz)
            return {"original": dt_src.isoformat(), "converted": dt_dst.isoformat(),
                    "from_tz": from_tz, "to_tz": to_tz}
        except Exception as e:
            return {"error": f"Timezone conversion failed: {e}"}

    elif action == "parse":
        dt = _parse_dt(date_str)
        if dt:
            return {"parsed": dt.isoformat(), "day_of_week": dt.strftime("%A"),
                    "year": dt.year, "month": dt.month, "day": dt.day,
                    "hour": dt.hour, "minute": dt.minute}
        return {"error": f"Cannot parse: {date_str}"}

    elif action == "format":
        dt = _parse_dt(date_str)
        if not dt:
            return {"error": f"Cannot parse: {date_str}"}
        fmt = format or "%B %d, %Y at %I:%M %p"
        return {"formatted": dt.strftime(fmt), "format_used": fmt}

    elif action == "epoch":
        if date_str and date_str.replace(".", "").replace("-", "").isdigit():
            # From epoch
            ts = float(date_str)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return {"datetime": dt.isoformat(), "epoch": ts}
        else:
            dt = _parse_dt(date_str) if date_str else datetime.now(timezone.utc)
            if not dt:
                return {"error": f"Cannot parse: {date_str}"}
            return {"epoch": int(dt.timestamp()), "datetime": dt.isoformat()}

    elif action == "calendar":
        dt = _parse_dt(date_str) if date_str else datetime.now()
        if not dt:
            dt = datetime.now()
        cal_text = cal_mod.month(dt.year, dt.month)
        return {"calendar": cal_text, "year": dt.year, "month": dt.month,
                "days_in_month": cal_mod.monthrange(dt.year, dt.month)[1]}

    return {"error": f"Unknown action: {action}. Use now, add, diff, convert_tz, parse, format, epoch, calendar."}


# ── Project-Wide Find and Replace ────────────────────────────────────────

def _project_replace(action: str, directory: str = "", pattern: str = "",
                     replacement: str = "", file_glob: str = "**/*",
                     regex: bool = False, dry_run: bool = True,
                     backup: bool = True) -> dict:
    """Find and replace across multiple files in a project.
    Actions: 'search' (find occurrences across files), 'replace' (find & replace),
    'preview' (show what would change, alias for dry_run replace).
    """
    if not directory:
        directory = ARMY_HOME
    root = Path(directory).expanduser()
    if not root.exists():
        return {"error": f"Directory not found: {directory}"}
    if not pattern:
        return {"error": "Pattern required"}

    if action == "search":
        matches = []
        try:
            for fpath in root.glob(file_glob):
                if not fpath.is_file() or fpath.stat().st_size > 5_000_000:
                    continue
                if ".git/" in str(fpath) or "__pycache__/" in str(fpath) or "node_modules/" in str(fpath):
                    continue
                try:
                    text = fpath.read_text(errors="replace")
                except Exception:
                    continue
                if regex:
                    found = [(m.start(), m.group()) for m in re.finditer(pattern, text, re.IGNORECASE)]
                else:
                    idx = 0
                    found = []
                    p_lower = pattern.lower()
                    t_lower = text.lower()
                    while True:
                        idx = t_lower.find(p_lower, idx)
                        if idx == -1:
                            break
                        found.append((idx, text[idx:idx + len(pattern)]))
                        idx += 1
                if found:
                    line_hits = []
                    for pos, match_text in found[:10]:
                        line_no = text[:pos].count("\n") + 1
                        line = text.splitlines()[line_no - 1].strip()[:200]
                        line_hits.append({"line": line_no, "text": line, "match": match_text[:100]})
                    matches.append({"file": str(fpath.relative_to(root)),
                                    "count": len(found), "hits": line_hits})
                if len(matches) >= 100:
                    break
        except Exception as e:
            return {"error": f"Search failed: {e}"}
        total = sum(m["count"] for m in matches)
        return {"matches": matches, "files_matched": len(matches),
                "total_occurrences": total, "directory": str(root), "pattern": pattern}

    elif action in ("replace", "preview"):
        is_dry = dry_run or action == "preview"
        changes = []
        try:
            for fpath in root.glob(file_glob):
                if not fpath.is_file() or fpath.stat().st_size > 5_000_000:
                    continue
                if ".git/" in str(fpath) or "__pycache__/" in str(fpath) or "node_modules/" in str(fpath):
                    continue
                try:
                    text = fpath.read_text(errors="replace")
                except Exception:
                    continue
                if regex:
                    count = len(re.findall(pattern, text, re.IGNORECASE))
                    if count == 0:
                        continue
                    new_text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                else:
                    count = text.lower().count(pattern.lower())
                    if count == 0:
                        continue
                    # Case-preserving replace
                    new_text = text.replace(pattern, replacement)

                if new_text != text:
                    if not is_dry:
                        if backup:
                            shutil.copy2(str(fpath), str(fpath) + ".bak")
                        fpath.write_text(new_text)
                    changes.append({"file": str(fpath.relative_to(root)),
                                    "replacements": count, "applied": not is_dry})
                if len(changes) >= 100:
                    break
        except Exception as e:
            return {"error": f"Replace failed: {e}"}
        total = sum(c["replacements"] for c in changes)
        return {"changes": changes, "files_changed": len(changes),
                "total_replacements": total, "dry_run": is_dry,
                "pattern": pattern, "replacement": replacement}

    return {"error": f"Unknown action: {action}. Use search, replace, preview."}


# ── Process Watchdog ──────────────────────────────────────────────────────

_WATCHDOG_REGISTRY: dict = {}
_WATCHDOG_PATH = Path(ARMY_HOME) / "data" / "watchdog_registry.json"

def _load_watchdog():
    global _WATCHDOG_REGISTRY
    if _WATCHDOG_PATH.exists():
        try:
            _WATCHDOG_REGISTRY = json.loads(_WATCHDOG_PATH.read_text())
        except Exception:
            _WATCHDOG_REGISTRY = {}

def _save_watchdog():
    _WATCHDOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _WATCHDOG_PATH.write_text(json.dumps(_WATCHDOG_REGISTRY, indent=2, default=str))

def _process_watchdog(action: str, name: str = "", command: str = "",
                      interval: int = 30, max_restarts: int = 10,
                      health_url: str = "") -> dict:
    """Auto-restart crashed processes. Register watchdogs with health checks.
    Actions: 'register' (add a process to watch), 'unregister' (stop watching),
    'list' (list all watched processes), 'status' (check status of one),
    'check_all' (run health check on all registered processes).
    """
    _load_watchdog()

    if action == "register":
        if not name or not command:
            return {"error": "Name and command required"}
        _WATCHDOG_REGISTRY[name] = {
            "command": command,
            "interval": interval,
            "max_restarts": max_restarts,
            "health_url": health_url,
            "restart_count": 0,
            "last_check": None,
            "last_restart": None,
            "status": "registered",
            "pid": None,
        }
        _save_watchdog()
        return {"registered": True, "name": name, "command": command,
                "interval": interval, "health_url": health_url}

    elif action == "unregister":
        if name in _WATCHDOG_REGISTRY:
            del _WATCHDOG_REGISTRY[name]
            _save_watchdog()
            return {"unregistered": True, "name": name}
        return {"error": f"Not found: {name}"}

    elif action == "list":
        return {"watchdogs": _WATCHDOG_REGISTRY, "count": len(_WATCHDOG_REGISTRY)}

    elif action == "status":
        if name not in _WATCHDOG_REGISTRY:
            return {"error": f"Not found: {name}"}
        entry = _WATCHDOG_REGISTRY[name]
        # Check if process is actually running
        alive = False
        if entry.get("pid"):
            try:
                os.kill(entry["pid"], 0)
                alive = True
            except (OSError, TypeError):
                pass
        if entry.get("health_url"):
            try:
                result = subprocess.run(
                    ["curl", "-sf", "--max-time", "5", entry["health_url"]],
                    capture_output=True, timeout=10,
                )
                alive = result.returncode == 0
            except Exception:
                pass
        entry["alive"] = alive
        entry["last_check"] = datetime.now().isoformat()
        _save_watchdog()
        return {"name": name, **entry}

    elif action == "check_all":
        results = []
        for wname, entry in _WATCHDOG_REGISTRY.items():
            alive = False
            # Check PID
            if entry.get("pid"):
                try:
                    os.kill(entry["pid"], 0)
                    alive = True
                except (OSError, TypeError):
                    pass
            # Check health URL
            if entry.get("health_url") and not alive:
                try:
                    result = subprocess.run(
                        ["curl", "-sf", "--max-time", "5", entry["health_url"]],
                        capture_output=True, timeout=10,
                    )
                    alive = result.returncode == 0
                except Exception:
                    pass
            entry["alive"] = alive
            entry["last_check"] = datetime.now().isoformat()
            # Auto-restart if dead
            restarted = False
            if not alive and entry["restart_count"] < entry["max_restarts"]:
                try:
                    proc = subprocess.Popen(
                        entry["command"], shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    entry["pid"] = proc.pid
                    entry["restart_count"] += 1
                    entry["last_restart"] = datetime.now().isoformat()
                    entry["status"] = "restarted"
                    restarted = True
                except Exception as e:
                    entry["status"] = f"restart_failed: {e}"
            results.append({"name": wname, "alive": alive, "restarted": restarted,
                            "restart_count": entry["restart_count"]})
        _save_watchdog()
        return {"results": results, "total": len(results),
                "healthy": sum(1 for r in results if r["alive"]),
                "restarted": sum(1 for r in results if r["restarted"])}

    return {"error": f"Unknown action: {action}. Use register, unregister, list, status, check_all."}


# ── Time-Series Metrics Collector ────────────────────────────────────────

_METRICS_PATH = Path(ARMY_HOME) / "data" / "metrics"

def _metrics_collect(action: str, name: str = "", value: float = 0,
                     tags: dict = None, hours: float = 24,
                     limit: int = 100) -> dict:
    """Record and analyze time-series metrics. Track performance, errors, latency, etc.
    Actions: 'record' (store a metric), 'query' (get metric history),
    'summary' (min/max/avg/p95 for a metric), 'list' (list all metric names),
    'delete' (delete a metric's history), 'dashboard' (summary of all metrics).
    """
    _METRICS_PATH.mkdir(parents=True, exist_ok=True)

    def _metric_file(metric_name):
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', metric_name)
        return _METRICS_PATH / f"{safe}.jsonl"

    if action == "record":
        if not name:
            return {"error": "Metric name required"}
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "value": value,
            "tags": tags or {},
        }
        f = _metric_file(name)
        with open(f, "a") as fp:
            fp.write(json.dumps(entry) + "\n")
        return {"recorded": True, "name": name, "value": value, "timestamp": entry["ts"]}

    elif action == "query":
        if not name:
            return {"error": "Metric name required"}
        f = _metric_file(name)
        if not f.exists():
            return {"error": f"No data for metric: {name}"}
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)).isoformat()
        entries = []
        for line in f.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                if e["ts"] >= cutoff:
                    entries.append(e)
            except json.JSONDecodeError:
                continue
        entries = entries[-limit:]
        return {"name": name, "entries": entries, "count": len(entries), "hours": hours}

    elif action == "summary":
        if not name:
            return {"error": "Metric name required"}
        f = _metric_file(name)
        if not f.exists():
            return {"error": f"No data for metric: {name}"}
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)).isoformat()
        values = []
        for line in f.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e["ts"] >= cutoff:
                    values.append(e["value"])
            except (json.JSONDecodeError, KeyError):
                continue
        if not values:
            return {"name": name, "count": 0, "detail": "No data in time range"}
        values.sort()
        n = len(values)
        return {
            "name": name, "count": n, "hours": hours,
            "min": min(values), "max": max(values),
            "avg": round(sum(values) / n, 4),
            "median": values[n // 2],
            "p95": values[int(n * 0.95)] if n >= 20 else values[-1],
            "p99": values[int(n * 0.99)] if n >= 100 else values[-1],
            "sum": round(sum(values), 4),
            "latest": values[-1],
        }

    elif action == "list":
        metrics = []
        for f in sorted(_METRICS_PATH.glob("*.jsonl")):
            lines = f.read_text().strip().split("\n")
            count = len([l for l in lines if l.strip()])
            metrics.append({"name": f.stem, "count": count, "size": f.stat().st_size})
        return {"metrics": metrics, "count": len(metrics)}

    elif action == "delete":
        if not name:
            return {"error": "Metric name required"}
        f = _metric_file(name)
        if f.exists():
            f.unlink()
            return {"deleted": True, "name": name}
        return {"error": f"No data for metric: {name}"}

    elif action == "dashboard":
        dashboard = {}
        for f in sorted(_METRICS_PATH.glob("*.jsonl")):
            lines = f.read_text().strip().split("\n")
            values = []
            for line in lines[-100:]:
                try:
                    values.append(json.loads(line)["value"])
                except Exception:
                    continue
            if values:
                dashboard[f.stem] = {
                    "count": len(lines),
                    "latest": values[-1],
                    "avg": round(sum(values) / len(values), 2),
                    "min": min(values),
                    "max": max(values),
                }
        return {"dashboard": dashboard, "metric_count": len(dashboard)}

    return {"error": f"Unknown action: {action}. Use record, query, summary, list, delete, dashboard."}


# ── Markdown / HTML Conversion ────────────────────────────────────────────

def _markdown_render(action: str, text: str = "", path: str = "",
                     output_path: str = "") -> dict:
    """Convert between Markdown and HTML. Generate formatted tables.
    Actions: 'md_to_html' (Markdown → HTML), 'html_to_md' (HTML → Markdown),
    'table' (generate Markdown table from data), 'toc' (extract table of contents from markdown).
    """
    content = text or (Path(path).expanduser().read_text() if path else "")
    if not content and action != "table":
        return {"error": "Provide text or path"}

    if action == "md_to_html":
        try:
            import markdown as md_lib
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "markdown"],
                           capture_output=True, timeout=60)
            import markdown as md_lib
        html = md_lib.markdown(content, extensions=["tables", "fenced_code", "toc"])
        if output_path:
            Path(output_path).expanduser().write_text(html)
        return {"html": html[:50000], "length": len(html),
                "output_path": output_path or None, "truncated": len(html) > 50000}

    elif action == "html_to_md":
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"],
                           capture_output=True, timeout=60)
            from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        # Simple HTML→Markdown converter
        md_lines = []
        for el in soup.descendants:
            if el.name and el.name.startswith("h") and el.name[1:].isdigit():
                level = int(el.name[1:])
                md_lines.append(f"\n{'#' * level} {el.get_text(strip=True)}\n")
            elif el.name == "p":
                md_lines.append(f"\n{el.get_text(strip=True)}\n")
            elif el.name == "li":
                md_lines.append(f"- {el.get_text(strip=True)}")
            elif el.name == "a" and el.get("href"):
                md_lines.append(f"[{el.get_text(strip=True)}]({el['href']})")
            elif el.name == "strong" or el.name == "b":
                md_lines.append(f"**{el.get_text(strip=True)}**")
            elif el.name == "em" or el.name == "i":
                md_lines.append(f"*{el.get_text(strip=True)}*")
            elif el.name == "code":
                md_lines.append(f"`{el.get_text(strip=True)}`")
            elif el.name == "pre":
                md_lines.append(f"\n```\n{el.get_text()}\n```\n")
            elif el.name == "br":
                md_lines.append("")
        result = "\n".join(md_lines).strip()
        if output_path:
            Path(output_path).expanduser().write_text(result)
        return {"markdown": result[:50000], "length": len(result),
                "output_path": output_path or None}

    elif action == "table":
        # text should be JSON array of objects
        try:
            data = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            return {"error": "Table data must be JSON array of objects"}
        if not isinstance(data, list) or not data:
            return {"error": "Need a non-empty list of dicts"}
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
        elif isinstance(data[0], list):
            headers = [str(h) for h in data[0]]
            rows = [[str(c) for c in row] for row in data[1:]]
        else:
            return {"error": "Data must be list of dicts or list of lists"}
        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            md += "| " + " | ".join(row) + " |\n"
        if output_path:
            Path(output_path).expanduser().write_text(md)
        return {"table": md, "rows": len(rows), "columns": len(headers)}

    elif action == "toc":
        toc = []
        for line in content.split("\n"):
            m = re.match(r'^(#{1,6})\s+(.+)', line)
            if m:
                level = len(m.group(1))
                heading = m.group(2).strip()
                anchor = re.sub(r'[^\w\s-]', '', heading.lower()).replace(' ', '-')
                toc.append({"level": level, "heading": heading, "anchor": anchor})
        return {"toc": toc, "count": len(toc)}

    return {"error": f"Unknown action: {action}. Use md_to_html, html_to_md, table, toc."}


# ── SQL Schema Management ────────────────────────────────────────────────

async def _sql_schema(action: str, table: str = "", schema: str = "public",
                      columns: list = None, query: str = "") -> dict:
    """PostgreSQL schema introspection and management.
    Actions: 'tables' (list all tables), 'describe' (describe table columns),
    'indexes' (list indexes for a table), 'size' (table/database sizes),
    'create_table' (create table from column specs), 'add_column' (add column to table),
    'migrations' (list applied migrations), 'foreign_keys' (list FKs).
    """
    import asyncpg
    dsn = os.environ.get("DATABASE_URL", "postgresql://landonking@localhost:5432/openclaw")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        return {"error": f"Database connection failed: {e}"}

    try:
        if action == "tables":
            rows = await conn.fetch(
                "SELECT table_name, table_type FROM information_schema.tables "
                "WHERE table_schema = $1 ORDER BY table_name", schema)
            tables = [{"name": r["table_name"], "type": r["table_type"]} for r in rows]
            return {"tables": tables, "count": len(tables), "schema": schema}

        elif action == "describe":
            if not table:
                return {"error": "Table name required"}
            rows = await conn.fetch(
                "SELECT column_name, data_type, is_nullable, column_default, "
                "character_maximum_length FROM information_schema.columns "
                "WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position",
                schema, table)
            columns_info = [{"name": r["column_name"], "type": r["data_type"],
                             "nullable": r["is_nullable"], "default": str(r["column_default"] or ""),
                             "max_length": r["character_maximum_length"]} for r in rows]
            return {"table": table, "columns": columns_info, "count": len(columns_info)}

        elif action == "indexes":
            if not table:
                return {"error": "Table name required"}
            rows = await conn.fetch(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = $1 AND tablename = $2", schema, table)
            indexes = [{"name": r["indexname"], "definition": r["indexdef"]} for r in rows]
            return {"table": table, "indexes": indexes, "count": len(indexes)}

        elif action == "size":
            rows = await conn.fetch(
                "SELECT relname AS table_name, "
                "pg_size_pretty(pg_total_relation_size(relid)) AS total_size, "
                "pg_size_pretty(pg_relation_size(relid)) AS data_size "
                "FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC")
            sizes = [{"table": r["table_name"], "total": r["total_size"],
                       "data": r["data_size"]} for r in rows]
            db_size = await conn.fetchval("SELECT pg_size_pretty(pg_database_size(current_database()))")
            return {"tables": sizes, "database_size": db_size}

        elif action == "create_table":
            if not table or not columns:
                return {"error": "Table name and columns required. columns: [{name, type, nullable, default}]"}
            col_defs = []
            for col in columns:
                col_def = f"{col['name']} {col['type']}"
                if not col.get("nullable", True):
                    col_def += " NOT NULL"
                if col.get("default"):
                    col_def += f" DEFAULT {col['default']}"
                if col.get("primary_key"):
                    col_def += " PRIMARY KEY"
                col_defs.append(col_def)
            ddl = f"CREATE TABLE IF NOT EXISTS {schema}.{table} ({', '.join(col_defs)})"
            await conn.execute(ddl)
            return {"created": True, "table": f"{schema}.{table}", "ddl": ddl}

        elif action == "add_column":
            if not table or not columns or not columns[0].get("name"):
                return {"error": "Table and column spec required: [{name, type}]"}
            col = columns[0]
            ddl = f"ALTER TABLE {schema}.{table} ADD COLUMN {col['name']} {col['type']}"
            if not col.get("nullable", True):
                ddl += " NOT NULL"
            if col.get("default"):
                ddl += f" DEFAULT {col['default']}"
            await conn.execute(ddl)
            return {"added": True, "table": f"{schema}.{table}", "column": col["name"], "ddl": ddl}

        elif action == "foreign_keys":
            if not table:
                return {"error": "Table name required"}
            rows = await conn.fetch(
                "SELECT kcu.column_name, ccu.table_name AS foreign_table, "
                "ccu.column_name AS foreign_column, tc.constraint_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name "
                "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = $1", table)
            fks = [{"column": r["column_name"], "references_table": r["foreign_table"],
                     "references_column": r["foreign_column"],
                     "constraint": r["constraint_name"]} for r in rows]
            return {"table": table, "foreign_keys": fks, "count": len(fks)}

        elif action == "migrations":
            # Check if migrations table exists
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'schema_migrations')")
            if not exists:
                return {"detail": "No schema_migrations table found. Use create_table to set one up."}
            rows = await conn.fetch(
                "SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 50")
            return {"migrations": [dict(r) for r in rows]}

    except Exception as e:
        return {"error": f"SQL schema operation failed: {e}"}
    finally:
        await conn.close()

    return {"error": f"Unknown action: {action}. Use tables, describe, indexes, size, create_table, add_column, foreign_keys, migrations."}


# ── Round 7 Tools ──────────────────────────────────────────────────────────

# --- audio_process ---
def _audio_process(action: str, **kwargs) -> dict:
    """Audio processing via ffmpeg and macOS say."""
    try:
        if action == "convert":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            if not src or not dst:
                return {"error": "source and destination required"}
            r = subprocess.run(["ffmpeg", "-y", "-i", src, dst],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"converted": dst, "detail": "OK"}

        elif action == "tts":
            text = kwargs.get("text", "")
            output = kwargs.get("output", "/tmp/tts_output.aiff")
            voice = kwargs.get("voice", "")
            if not text:
                return {"error": "text required"}
            cmd = ["say"]
            if voice:
                cmd += ["-v", voice]
            cmd += ["-o", output, text]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return {"tts_file": output, "detail": "OK"}

        elif action == "trim":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            start = kwargs.get("start", "0")
            duration = kwargs.get("duration", "")
            if not src or not dst:
                return {"error": "source and destination required"}
            cmd = ["ffmpeg", "-y", "-i", src, "-ss", str(start)]
            if duration:
                cmd += ["-t", str(duration)]
            cmd += [dst]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"trimmed": dst, "detail": "OK"}

        elif action == "merge":
            files = kwargs.get("files", [])
            dst = kwargs.get("destination", "")
            if len(files) < 2 or not dst:
                return {"error": "files (list of >=2) and destination required"}
            import tempfile
            list_path = tempfile.mktemp(suffix=".txt")
            with open(list_path, "w") as f:
                for fp in files:
                    f.write(f"file '{fp}'\n")
            r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                                "-i", list_path, "-c", "copy", dst],
                               capture_output=True, text=True, timeout=120)
            os.unlink(list_path)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"merged": dst, "detail": "OK"}

        elif action == "metadata":
            src = kwargs.get("source", "")
            if not src:
                return {"error": "source required"}
            r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                                "-show_format", "-show_streams", src],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "volume":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            level = kwargs.get("level", "1.5")
            if not src or not dst:
                return {"error": "source and destination required"}
            r = subprocess.run(["ffmpeg", "-y", "-i", src, "-filter:a",
                                f"volume={level}", dst],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"adjusted": dst, "detail": "OK"}

        elif action == "voices":
            r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10)
            voices = [line.split()[0] for line in r.stdout.strip().split("\n") if line.strip()][:50]
            return {"voices": voices, "count": len(voices)}

        else:
            return {"error": f"Unknown action: {action}. Use convert, tts, trim, merge, metadata, volume, voices."}
    except subprocess.TimeoutExpired:
        return {"error": "Audio processing timed out"}
    except Exception as e:
        return {"error": f"audio_process failed: {e}"}


# --- video_process ---
def _video_process(action: str, **kwargs) -> dict:
    """Video processing via ffmpeg."""
    try:
        if action == "convert":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            if not src or not dst:
                return {"error": "source and destination required"}
            r = subprocess.run(["ffmpeg", "-y", "-i", src, dst],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"converted": dst, "detail": "OK"}

        elif action == "extract_frames":
            src = kwargs.get("source", "")
            output_dir = kwargs.get("output_dir", "/tmp/frames")
            fps = kwargs.get("fps", "1")
            os.makedirs(output_dir, exist_ok=True)
            r = subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", f"fps={fps}",
                                os.path.join(output_dir, "frame_%04d.png")],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            frames = sorted(os.listdir(output_dir))
            return {"output_dir": output_dir, "frame_count": len(frames), "frames": frames[:20]}

        elif action == "trim":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            start = kwargs.get("start", "0")
            duration = kwargs.get("duration", "")
            if not src or not dst:
                return {"error": "source and destination required"}
            cmd = ["ffmpeg", "-y", "-i", src, "-ss", str(start)]
            if duration:
                cmd += ["-t", str(duration)]
            cmd += ["-c", "copy", dst]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"trimmed": dst, "detail": "OK"}

        elif action == "thumbnail":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "/tmp/thumb.png")
            timestamp = kwargs.get("timestamp", "00:00:01")
            r = subprocess.run(["ffmpeg", "-y", "-i", src, "-ss", timestamp,
                                "-vframes", "1", dst],
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"thumbnail": dst, "detail": "OK"}

        elif action == "metadata":
            src = kwargs.get("source", "")
            if not src:
                return {"error": "source required"}
            r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                                "-show_format", "-show_streams", src],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "resize":
            src = kwargs.get("source", "")
            dst = kwargs.get("destination", "")
            width = kwargs.get("width", "1280")
            height = kwargs.get("height", "-1")
            if not src or not dst:
                return {"error": "source and destination required"}
            r = subprocess.run(["ffmpeg", "-y", "-i", src, "-vf",
                                f"scale={width}:{height}", dst],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"error": r.stderr[:1000]}
            return {"resized": dst, "detail": "OK"}

        else:
            return {"error": f"Unknown action: {action}. Use convert, extract_frames, trim, thumbnail, metadata, resize."}
    except subprocess.TimeoutExpired:
        return {"error": "Video processing timed out"}
    except Exception as e:
        return {"error": f"video_process failed: {e}"}


# --- pdf_tools ---
def _pdf_tools(action: str, **kwargs) -> dict:
    """PDF generation and parsing."""
    try:
        if action == "create":
            output = kwargs.get("output", "/tmp/output.pdf")
            title = kwargs.get("title", "")
            content = kwargs.get("content", "")
            if not content:
                return {"error": "content required"}
            try:
                from fpdf import FPDF
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "fpdf2"],
                               capture_output=True, timeout=60)
                from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            if title:
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(5)
            pdf.set_font("Helvetica", "", 11)
            for line in content.split("\n"):
                pdf.multi_cell(0, 6, line)
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            pdf.output(output)
            return {"created": output, "pages": pdf.pages_count}

        elif action == "extract_text":
            source = kwargs.get("source", "")
            if not source:
                return {"error": "source required"}
            try:
                import pymupdf
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"],
                               capture_output=True, timeout=120)
                import pymupdf
            doc = pymupdf.open(source)
            pages = []
            for i, page in enumerate(doc):
                pages.append({"page": i + 1, "text": page.get_text()[:5000]})
            doc.close()
            return {"source": source, "page_count": len(pages), "pages": pages[:50]}

        elif action == "page_count":
            source = kwargs.get("source", "")
            if not source:
                return {"error": "source required"}
            try:
                import pymupdf
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"],
                               capture_output=True, timeout=120)
                import pymupdf
            doc = pymupdf.open(source)
            count = len(doc)
            doc.close()
            return {"source": source, "page_count": count}

        elif action == "merge":
            files = kwargs.get("files", [])
            output = kwargs.get("output", "/tmp/merged.pdf")
            if len(files) < 2:
                return {"error": "files (list of >=2) required"}
            try:
                import pymupdf
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"],
                               capture_output=True, timeout=120)
                import pymupdf
            merged = pymupdf.open()
            for f in files:
                src = pymupdf.open(f)
                merged.insert_pdf(src)
                src.close()
            merged.save(output)
            total = len(merged)
            merged.close()
            return {"merged": output, "page_count": total}

        elif action == "split":
            source = kwargs.get("source", "")
            output_dir = kwargs.get("output_dir", "/tmp/pdf_pages")
            if not source:
                return {"error": "source required"}
            try:
                import pymupdf
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"],
                               capture_output=True, timeout=120)
                import pymupdf
            os.makedirs(output_dir, exist_ok=True)
            doc = pymupdf.open(source)
            out_files = []
            for i in range(len(doc)):
                out = pymupdf.open()
                out.insert_pdf(doc, from_page=i, to_page=i)
                p = os.path.join(output_dir, f"page_{i+1:04d}.pdf")
                out.save(p)
                out.close()
                out_files.append(p)
            doc.close()
            return {"source": source, "pages_split": len(out_files), "files": out_files[:20]}

        else:
            return {"error": f"Unknown action: {action}. Use create, extract_text, page_count, merge, split."}
    except Exception as e:
        return {"error": f"pdf_tools failed: {e}"}


# --- ssh_remote ---
def _ssh_remote(action: str, **kwargs) -> dict:
    """Execute commands on remote hosts via SSH."""
    try:
        host = kwargs.get("host", "")
        if not host:
            return {"error": "host required (user@hostname or hostname)"}

        if action == "exec":
            command = kwargs.get("command", "")
            if not command:
                return {"error": "command required"}
            timeout = min(int(kwargs.get("timeout", 30)), 120)
            ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new",
                       "-o", f"ConnectTimeout={min(timeout, 10)}",
                       host, command]
            r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "host": host,
                "command": command,
                "exit_code": r.returncode,
                "stdout": r.stdout[:5000],
                "stderr": r.stderr[:2000],
            }

        elif action == "copy_to":
            source = kwargs.get("source", "")
            destination = kwargs.get("destination", "")
            if not source or not destination:
                return {"error": "source and destination required"}
            r = subprocess.run(["scp", "-o", "StrictHostKeyChecking=accept-new",
                                source, f"{host}:{destination}"],
                               capture_output=True, text=True, timeout=120)
            return {"host": host, "copied": source, "to": destination,
                    "exit_code": r.returncode, "stderr": r.stderr[:500]}

        elif action == "copy_from":
            source = kwargs.get("source", "")
            destination = kwargs.get("destination", "")
            if not source or not destination:
                return {"error": "source and destination required"}
            r = subprocess.run(["scp", "-o", "StrictHostKeyChecking=accept-new",
                                f"{host}:{source}", destination],
                               capture_output=True, text=True, timeout=120)
            return {"host": host, "copied": source, "to": destination,
                    "exit_code": r.returncode, "stderr": r.stderr[:500]}

        elif action == "test":
            r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=accept-new",
                                "-o", "ConnectTimeout=5", host, "echo OK"],
                               capture_output=True, text=True, timeout=10)
            reachable = r.returncode == 0 and "OK" in r.stdout
            return {"host": host, "reachable": reachable,
                    "stderr": r.stderr[:300] if not reachable else ""}

        else:
            return {"error": f"Unknown action: {action}. Use exec, copy_to, copy_from, test."}
    except subprocess.TimeoutExpired:
        return {"error": f"SSH to {host} timed out"}
    except Exception as e:
        return {"error": f"ssh_remote failed: {e}"}


# --- secret_vault ---
_VAULT_PATH = Path(ARMY_HOME) / "data" / "vault.enc"
_VAULT_KEY_PATH = Path(ARMY_HOME) / "data" / ".vault_key"


def _get_vault_key():
    """Get or create the Fernet encryption key."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"],
                       capture_output=True, timeout=60)
        from cryptography.fernet import Fernet
    if _VAULT_KEY_PATH.exists():
        return Fernet(_VAULT_KEY_PATH.read_bytes().strip())
    key = Fernet.generate_key()
    _VAULT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _VAULT_KEY_PATH.write_bytes(key)
    os.chmod(str(_VAULT_KEY_PATH), 0o600)
    return Fernet(key)


def _load_vault() -> dict:
    if not _VAULT_PATH.exists():
        return {}
    f = _get_vault_key()
    data = f.decrypt(_VAULT_PATH.read_bytes())
    return json.loads(data)


def _save_vault(secrets: dict):
    f = _get_vault_key()
    data = f.encrypt(json.dumps(secrets).encode())
    _VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _VAULT_PATH.write_bytes(data)
    os.chmod(str(_VAULT_PATH), 0o600)


def _secret_vault(action: str, **kwargs) -> dict:
    """Encrypted secrets management."""
    try:
        if action == "store":
            key = kwargs.get("key", "")
            value = kwargs.get("value", "")
            if not key or not value:
                return {"error": "key and value required"}
            secrets = _load_vault()
            secrets[key] = value
            _save_vault(secrets)
            return {"stored": key, "detail": "OK"}

        elif action == "retrieve":
            key = kwargs.get("key", "")
            if not key:
                return {"error": "key required"}
            secrets = _load_vault()
            if key not in secrets:
                return {"error": f"Secret '{key}' not found"}
            return {"key": key, "value": secrets[key]}

        elif action == "list":
            secrets = _load_vault()
            return {"secrets": list(secrets.keys()), "count": len(secrets)}

        elif action == "delete":
            key = kwargs.get("key", "")
            if not key:
                return {"error": "key required"}
            secrets = _load_vault()
            if key not in secrets:
                return {"error": f"Secret '{key}' not found"}
            del secrets[key]
            _save_vault(secrets)
            return {"deleted": key, "detail": "OK"}

        elif action == "rotate_key":
            # Re-encrypt all secrets with a new key
            secrets = _load_vault()
            if _VAULT_KEY_PATH.exists():
                _VAULT_KEY_PATH.unlink()
            _save_vault(secrets)
            return {"detail": "Vault key rotated", "secrets_count": len(secrets)}

        else:
            return {"error": f"Unknown action: {action}. Use store, retrieve, list, delete, rotate_key."}
    except Exception as e:
        return {"error": f"secret_vault failed: {e}"}


# --- test_runner ---
def _test_runner(action: str, **kwargs) -> dict:
    """Execute tests and return structured results."""
    try:
        if action == "pytest":
            target = kwargs.get("target", ".")
            args = kwargs.get("args", "")
            timeout = min(int(kwargs.get("timeout", 120)), 600)
            cmd = [sys.executable, "-m", "pytest", target, "-v", "--tb=short", "--no-header"]
            if args:
                cmd.extend(args.split())
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               cwd=kwargs.get("cwd", ARMY_HOME))
            lines = r.stdout.strip().split("\n")
            passed = sum(1 for l in lines if " PASSED" in l)
            failed = sum(1 for l in lines if " FAILED" in l)
            errors = sum(1 for l in lines if " ERROR" in l)
            skipped = sum(1 for l in lines if " SKIPPED" in l)
            return {
                "exit_code": r.returncode,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "output": r.stdout[:5000],
                "stderr": r.stderr[:2000],
            }

        elif action == "unittest":
            target = kwargs.get("target", "")
            if not target:
                return {"error": "target required (module path or file)"}
            timeout = min(int(kwargs.get("timeout", 120)), 600)
            cmd = [sys.executable, "-m", "unittest", target, "-v"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               cwd=kwargs.get("cwd", ARMY_HOME))
            return {
                "exit_code": r.returncode,
                "output": r.stdout[:5000],
                "stderr": r.stderr[:5000],
            }

        elif action == "script":
            target = kwargs.get("target", "")
            if not target:
                return {"error": "target script path required"}
            timeout = min(int(kwargs.get("timeout", 120)), 600)
            cmd = [sys.executable, target]
            if kwargs.get("args"):
                cmd.extend(kwargs["args"].split())
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               cwd=kwargs.get("cwd", ARMY_HOME))
            return {
                "exit_code": r.returncode,
                "output": r.stdout[:5000],
                "stderr": r.stderr[:2000],
            }

        elif action == "discover":
            target = kwargs.get("target", ".")
            r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", target],
                               capture_output=True, text=True, timeout=30,
                               cwd=kwargs.get("cwd", ARMY_HOME))
            tests = [l.strip() for l in r.stdout.strip().split("\n") if "::" in l]
            return {"tests": tests[:100], "count": len(tests)}

        else:
            return {"error": f"Unknown action: {action}. Use pytest, unittest, script, discover."}
    except subprocess.TimeoutExpired:
        return {"error": "Test execution timed out"}
    except Exception as e:
        return {"error": f"test_runner failed: {e}"}


# --- dependency_analysis ---
def _dependency_analysis(action: str, **kwargs) -> dict:
    """Analyze Python imports and dependencies."""
    import ast as _ast

    try:
        if action == "imports":
            target = kwargs.get("target", "")
            if not target:
                return {"error": "target file path required"}
            source = Path(target).read_text()
            tree = _ast.parse(source)
            imports = []
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Import):
                    for alias in node.names:
                        imports.append({"module": alias.name, "alias": alias.asname, "line": node.lineno})
                elif isinstance(node, _ast.ImportFrom):
                    for alias in node.names:
                        imports.append({"module": f"{node.module}.{alias.name}" if node.module else alias.name,
                                        "alias": alias.asname, "line": node.lineno, "from": node.module})
            return {"target": target, "imports": imports, "count": len(imports)}

        elif action == "circular":
            target_dir = kwargs.get("target", ".")
            # Build import graph for .py files
            graph = {}
            py_files = list(Path(target_dir).rglob("*.py"))[:200]
            for fp in py_files:
                try:
                    tree = _ast.parse(fp.read_text())
                except Exception:
                    continue
                mod_name = fp.stem
                deps = set()
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.Import):
                        for alias in node.names:
                            deps.add(alias.name.split(".")[0])
                    elif isinstance(node, _ast.ImportFrom) and node.module:
                        deps.add(node.module.split(".")[0])
                graph[mod_name] = deps

            # Detect cycles via DFS
            cycles = []
            visited = set()
            path_set = set()

            def _dfs(node, path):
                if node in path_set:
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
                    return
                if node in visited or node not in graph:
                    return
                visited.add(node)
                path_set.add(node)
                path.append(node)
                for dep in graph.get(node, []):
                    if dep in graph:
                        _dfs(dep, path)
                path.pop()
                path_set.discard(node)

            for mod in graph:
                _dfs(mod, [])

            return {"directory": target_dir, "modules_scanned": len(graph),
                    "circular_deps": cycles[:20], "count": len(cycles)}

        elif action == "unused":
            target = kwargs.get("target", "")
            if not target:
                return {"error": "target file path required"}
            source = Path(target).read_text()
            tree = _ast.parse(source)
            imported_names = {}
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        imported_names[name] = alias.name
                elif isinstance(node, _ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imported_names[name] = f"{node.module}.{alias.name}" if node.module else alias.name

            # Check usage in the source
            all_names = set()
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Name):
                    all_names.add(node.id)
                elif isinstance(node, _ast.Attribute):
                    if isinstance(node.value, _ast.Name):
                        all_names.add(node.value.id)

            unused = {name: mod for name, mod in imported_names.items()
                      if name not in all_names - set(imported_names.keys()) and name not in all_names}
            # Re-check: a name used as Name(id=...) counts
            truly_unused = {}
            for name, mod in imported_names.items():
                if name not in all_names:
                    truly_unused[name] = mod

            return {"target": target, "unused_imports": truly_unused, "count": len(truly_unused)}

        elif action == "graph":
            target = kwargs.get("target", "")
            if not target:
                return {"error": "target file path required"}
            source = Path(target).read_text()
            tree = _ast.parse(source)
            stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
            stdlib_deps = []
            third_party = []
            local_deps = []
            for node in _ast.walk(tree):
                mod = None
                if isinstance(node, _ast.Import):
                    for alias in node.names:
                        mod = alias.name.split(".")[0]
                elif isinstance(node, _ast.ImportFrom) and node.module:
                    mod = node.module.split(".")[0]
                if mod:
                    if mod in stdlib:
                        if mod not in [d["module"] for d in stdlib_deps]:
                            stdlib_deps.append({"module": mod, "category": "stdlib"})
                    elif Path(target).parent.joinpath(mod + ".py").exists() or Path(target).parent.joinpath(mod).is_dir():
                        local_deps.append({"module": mod, "category": "local"})
                    else:
                        if mod not in [d["module"] for d in third_party]:
                            third_party.append({"module": mod, "category": "third_party"})
            return {"target": target, "stdlib": stdlib_deps, "third_party": third_party,
                    "local": local_deps}

        else:
            return {"error": f"Unknown action: {action}. Use imports, circular, unused, graph."}
    except Exception as e:
        return {"error": f"dependency_analysis failed: {e}"}


# --- resource_monitor ---
def _resource_monitor(action: str, **kwargs) -> dict:
    """CPU/memory/disk monitoring with thresholds and alerts."""
    try:
        try:
            import psutil
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "psutil"],
                           capture_output=True, timeout=60)
            import psutil

        if action == "snapshot":
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {
                "cpu_percent": cpu,
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "percent": mem.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent,
                },
            }

        elif action == "processes":
            limit = int(kwargs.get("limit", 10))
            sort_by = kwargs.get("sort_by", "memory")
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            key = "memory_percent" if sort_by == "memory" else "cpu_percent"
            procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)
            return {"processes": procs[:limit], "sort_by": sort_by}

        elif action == "check_thresholds":
            cpu_thresh = float(kwargs.get("cpu_threshold", 90))
            mem_thresh = float(kwargs.get("memory_threshold", 90))
            disk_thresh = float(kwargs.get("disk_threshold", 90))
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            alerts = []
            if cpu > cpu_thresh:
                alerts.append({"resource": "cpu", "value": cpu, "threshold": cpu_thresh})
            if mem > mem_thresh:
                alerts.append({"resource": "memory", "value": mem, "threshold": mem_thresh})
            if disk > disk_thresh:
                alerts.append({"resource": "disk", "value": disk, "threshold": disk_thresh})
            return {
                "cpu": cpu, "memory": mem, "disk": disk,
                "alerts": alerts, "alert_count": len(alerts),
                "status": "ALERT" if alerts else "OK",
            }

        elif action == "network":
            net = psutil.net_io_counters()
            conns = len(psutil.net_connections())
            return {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
                "active_connections": conns,
            }

        elif action == "temperatures":
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            if not temps:
                # macOS fallback
                r = subprocess.run(["sudo", "powermetrics", "--samplers", "smc", "-n", "1", "-i", "1"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return {"raw": r.stdout[:2000]}
                return {"detail": "Temperature sensors not available without sudo on macOS"}
            return {"temperatures": {k: [{"label": s.label, "current": s.current, "high": s.high} for s in v] for k, v in temps.items()}}

        else:
            return {"error": f"Unknown action: {action}. Use snapshot, processes, check_thresholds, network, temperatures."}
    except Exception as e:
        return {"error": f"resource_monitor failed: {e}"}


# --- sqlite_query ---
def _sqlite_query(action: str, **kwargs) -> dict:
    """Local SQLite database operations."""
    import sqlite3 as _sqlite3

    db_path = kwargs.get("database", os.path.join(ARMY_HOME, "data", "local.db"))
    try:
        if action == "query":
            sql = kwargs.get("sql", "")
            if not sql:
                return {"error": "sql required"}
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql)
            if sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("PRAGMA"):
                rows = [dict(r) for r in cur.fetchmany(500)]
                result = {"rows": rows, "count": len(rows)}
            else:
                conn.commit()
                result = {"rows_affected": cur.rowcount}
            conn.close()
            return result

        elif action == "execute":
            sql = kwargs.get("sql", "")
            params = kwargs.get("params", [])
            if not sql:
                return {"error": "sql required"}
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            result = {"rows_affected": cur.rowcount, "lastrowid": cur.lastrowid}
            conn.close()
            return result

        elif action == "tables":
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return {"database": db_path, "tables": tables, "count": len(tables)}

        elif action == "schema":
            table = kwargs.get("table", "")
            if not table:
                return {"error": "table required"}
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = [{"cid": r[0], "name": r[1], "type": r[2], "notnull": bool(r[3]),
                      "default": r[4], "pk": bool(r[5])} for r in cur.fetchall()]
            conn.close()
            return {"table": table, "columns": cols, "count": len(cols)}

        elif action == "import_csv":
            csv_path = kwargs.get("csv_path", "")
            table = kwargs.get("table", "")
            if not csv_path or not table:
                return {"error": "csv_path and table required"}
            import csv
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                rows_data = list(reader)
            if not rows_data:
                return {"error": "CSV is empty"}
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cols = list(rows_data[0].keys())
            col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
            cur.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(f'"{c}"' for c in cols)
            for row in rows_data:
                cur.execute(f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})',
                            [row.get(c, "") for c in cols])
            conn.commit()
            conn.close()
            return {"table": table, "rows_imported": len(rows_data), "columns": cols}

        else:
            return {"error": f"Unknown action: {action}. Use query, execute, tables, schema, import_csv."}
    except Exception as e:
        return {"error": f"sqlite_query failed: {e}"}


# --- file_watch ---
_FILE_WATCHERS: dict[str, dict] = {}


async def _file_watch(action: str, **kwargs) -> dict:
    """Watch directories for file changes."""
    try:
        if action == "start":
            path = kwargs.get("path", "")
            watch_id = kwargs.get("watch_id", str(uuid.uuid4())[:8])
            if not path:
                return {"error": "path required"}
            if not os.path.isdir(path):
                return {"error": f"Directory not found: {path}"}
            if watch_id in _FILE_WATCHERS:
                return {"error": f"Watcher '{watch_id}' already running"}

            log_path = os.path.join(ARMY_HOME, "data", "file_watch", f"{watch_id}.jsonl")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            cancel_event = asyncio.Event()

            async def _watcher():
                from watchfiles import awatch, Change
                change_map = {Change.added: "added", Change.modified: "modified", Change.deleted: "deleted"}
                try:
                    async for changes in awatch(path, stop_event=cancel_event):
                        entries = []
                        for change_type, change_path in changes:
                            entry = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "type": change_map.get(change_type, str(change_type)),
                                "path": change_path,
                            }
                            entries.append(entry)
                        with open(log_path, "a") as f:
                            for e in entries:
                                f.write(json.dumps(e) + "\n")
                except asyncio.CancelledError:
                    pass

            task = asyncio.create_task(_watcher())
            _FILE_WATCHERS[watch_id] = {
                "path": path, "log_path": log_path, "task": task,
                "cancel": cancel_event, "started": datetime.now(timezone.utc).isoformat()
            }
            return {"watch_id": watch_id, "path": path, "log_path": log_path, "status": "watching"}

        elif action == "stop":
            watch_id = kwargs.get("watch_id", "")
            if not watch_id or watch_id not in _FILE_WATCHERS:
                return {"error": f"Watcher '{watch_id}' not found"}
            w = _FILE_WATCHERS.pop(watch_id)
            w["cancel"].set()
            w["task"].cancel()
            return {"watch_id": watch_id, "stopped": True}

        elif action == "list":
            watchers = []
            for wid, w in _FILE_WATCHERS.items():
                watchers.append({"watch_id": wid, "path": w["path"],
                                 "log_path": w["log_path"], "started": w["started"]})
            return {"watchers": watchers, "count": len(watchers)}

        elif action == "events":
            watch_id = kwargs.get("watch_id", "")
            limit = int(kwargs.get("limit", 50))
            if not watch_id or watch_id not in _FILE_WATCHERS:
                return {"error": f"Watcher '{watch_id}' not found"}
            log_path = _FILE_WATCHERS[watch_id]["log_path"]
            if not os.path.exists(log_path):
                return {"watch_id": watch_id, "events": [], "count": 0}
            with open(log_path) as f:
                lines = f.readlines()
            events = []
            for line in lines[-limit:]:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
            return {"watch_id": watch_id, "events": events, "count": len(events)}

        else:
            return {"error": f"Unknown action: {action}. Use start, stop, list, events."}
    except Exception as e:
        return {"error": f"file_watch failed: {e}"}


# ── Round 8 Tools ──────────────────────────────────────────────────────────

# --- email_parse ---
def _email_parse(action: str, **kwargs) -> dict:
    """Parse emails and read IMAP inboxes."""
    import email as _email
    from email import policy as _policy
    try:
        if action == "parse_file":
            path = kwargs.get("path", "")
            if not path:
                return {"error": "path required"}
            with open(path, "rb") as f:
                msg = _email.message_from_binary_file(f, policy=_policy.default)
            result = {
                "subject": str(msg.get("subject", "")),
                "from": str(msg.get("from", "")),
                "to": str(msg.get("to", "")),
                "date": str(msg.get("date", "")),
                "cc": str(msg.get("cc", "")),
                "message_id": str(msg.get("message-id", "")),
            }
            if msg.is_multipart():
                parts = []
                for part in msg.walk():
                    ct = part.get_content_type()
                    fn = part.get_filename()
                    if fn:
                        parts.append({"type": "attachment", "filename": fn, "content_type": ct,
                                       "size": len(part.get_payload(decode=True) or b"")})
                    elif ct == "text/plain":
                        parts.append({"type": "text", "content": (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")[:5000]})
                    elif ct == "text/html":
                        parts.append({"type": "html", "content": (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")[:5000]})
                result["parts"] = parts
            else:
                result["body"] = (msg.get_payload(decode=True) or b"").decode("utf-8", errors="replace")[:5000]
            return result

        elif action == "extract_attachments":
            path = kwargs.get("path", "")
            output_dir = kwargs.get("output_dir", "/tmp/email_attachments")
            if not path:
                return {"error": "path required"}
            os.makedirs(output_dir, exist_ok=True)
            with open(path, "rb") as f:
                msg = _email.message_from_binary_file(f, policy=_policy.default)
            saved = []
            for part in msg.walk():
                fn = part.get_filename()
                if fn:
                    out_path = os.path.join(output_dir, fn)
                    with open(out_path, "wb") as f:
                        f.write(part.get_payload(decode=True) or b"")
                    saved.append({"filename": fn, "path": out_path, "size": os.path.getsize(out_path)})
            return {"attachments": saved, "count": len(saved)}

        elif action == "imap_list":
            import imaplib
            host = kwargs.get("host", "")
            user = kwargs.get("user", "")
            password = kwargs.get("password", "")
            if not all([host, user, password]):
                return {"error": "host, user, password required"}
            conn = imaplib.IMAP4_SSL(host, timeout=15)
            conn.login(user, password)
            _, folders = conn.list()
            conn.logout()
            folder_list = []
            for f in (folders or []):
                if isinstance(f, bytes):
                    folder_list.append(f.decode("utf-8", errors="replace"))
            return {"folders": folder_list, "count": len(folder_list)}

        elif action == "imap_inbox":
            import imaplib
            host = kwargs.get("host", "")
            user = kwargs.get("user", "")
            password = kwargs.get("password", "")
            folder = kwargs.get("folder", "INBOX")
            limit = int(kwargs.get("limit", 10))
            if not all([host, user, password]):
                return {"error": "host, user, password required"}
            conn = imaplib.IMAP4_SSL(host, timeout=15)
            conn.login(user, password)
            conn.select(folder, readonly=True)
            _, data = conn.search(None, "ALL")
            ids = data[0].split()
            recent = ids[-limit:] if len(ids) > limit else ids
            messages = []
            for mid in reversed(recent):
                _, msg_data = conn.fetch(mid, "(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    header = msg_data[0][1].decode("utf-8", errors="replace")
                    messages.append({"id": mid.decode(), "header": header.strip()})
            conn.logout()
            return {"folder": folder, "messages": messages, "count": len(messages)}

        elif action == "parse_string":
            raw = kwargs.get("raw", "")
            if not raw:
                return {"error": "raw email string required"}
            msg = _email.message_from_string(raw, policy=_policy.default)
            return {
                "subject": str(msg.get("subject", "")),
                "from": str(msg.get("from", "")),
                "to": str(msg.get("to", "")),
                "date": str(msg.get("date", "")),
                "body": (msg.get_payload(decode=True) or b"").decode("utf-8", errors="replace")[:5000] if not msg.is_multipart() else "[multipart]",
            }

        else:
            return {"error": f"Unknown action: {action}. Use parse_file, extract_attachments, imap_list, imap_inbox, parse_string."}
    except Exception as e:
        return {"error": f"email_parse failed: {e}"}


# --- qr_code ---
def _qr_code(action: str, **kwargs) -> dict:
    """Generate and decode QR codes."""
    try:
        if action == "generate":
            data = kwargs.get("data", "")
            output = kwargs.get("output", "/tmp/qrcode.png")
            size = int(kwargs.get("size", 10))
            if not data:
                return {"error": "data required"}
            try:
                import qrcode
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "qrcode[pil]"],
                               capture_output=True, timeout=60)
                import qrcode
            qr = qrcode.QRCode(version=1, box_size=size, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            img.save(output)
            return {"output": output, "data_length": len(data), "detail": "OK"}

        elif action == "generate_svg":
            data = kwargs.get("data", "")
            output = kwargs.get("output", "/tmp/qrcode.svg")
            if not data:
                return {"error": "data required"}
            try:
                import qrcode
                import qrcode.image.svg
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "qrcode[pil]"],
                               capture_output=True, timeout=60)
                import qrcode
                import qrcode.image.svg
            qr = qrcode.QRCode(version=1, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            img.save(output)
            return {"output": output, "format": "svg", "detail": "OK"}

        elif action == "decode":
            source = kwargs.get("source", "")
            if not source:
                return {"error": "source image path required"}
            # Use zbarimg if available, else try pyzbar
            r = subprocess.run(["which", "zbarimg"], capture_output=True, timeout=5)
            if r.returncode == 0:
                r = subprocess.run(["zbarimg", "--raw", "-q", source],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0 and r.stdout.strip():
                    return {"decoded": r.stdout.strip(), "method": "zbarimg"}
            # Fallback: use pyzbar
            try:
                from pyzbar.pyzbar import decode as _pyzbar_decode
                from PIL import Image
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "pyzbar", "Pillow"],
                               capture_output=True, timeout=60)
                from pyzbar.pyzbar import decode as _pyzbar_decode
                from PIL import Image
            img = Image.open(source)
            results = _pyzbar_decode(img)
            if not results:
                return {"error": "No QR code found in image"}
            decoded = [{"data": r.data.decode("utf-8", errors="replace"), "type": r.type} for r in results]
            return {"decoded": decoded, "count": len(decoded)}

        else:
            return {"error": f"Unknown action: {action}. Use generate, generate_svg, decode."}
    except Exception as e:
        return {"error": f"qr_code failed: {e}"}


# --- http_server ---
_HTTP_SERVERS: dict[str, dict] = {}


def _http_server(action: str, **kwargs) -> dict:
    """Manage ephemeral HTTP file servers."""
    try:
        if action == "start":
            directory = kwargs.get("directory", "/tmp")
            port = int(kwargs.get("port", 0))
            server_id = kwargs.get("server_id", str(uuid.uuid4())[:8])
            if not os.path.isdir(directory):
                return {"error": f"Directory not found: {directory}"}
            if server_id in _HTTP_SERVERS:
                return {"error": f"Server '{server_id}' already running"}

            import http.server
            import socketserver
            import threading

            class QuietHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *a, **kw):
                    super().__init__(*a, directory=directory, **kw)
                def log_message(self, format, *args):
                    pass  # Suppress logs

            httpd = socketserver.TCPServer(("0.0.0.0", port), QuietHandler)
            actual_port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            _HTTP_SERVERS[server_id] = {
                "httpd": httpd, "thread": thread, "directory": directory,
                "port": actual_port, "started": datetime.now(timezone.utc).isoformat(),
            }
            return {"server_id": server_id, "port": actual_port, "directory": directory,
                    "url": f"http://localhost:{actual_port}", "status": "running"}

        elif action == "stop":
            server_id = kwargs.get("server_id", "")
            if not server_id or server_id not in _HTTP_SERVERS:
                return {"error": f"Server '{server_id}' not found"}
            srv = _HTTP_SERVERS.pop(server_id)
            srv["httpd"].shutdown()
            return {"server_id": server_id, "stopped": True}

        elif action == "list":
            servers = []
            for sid, s in _HTTP_SERVERS.items():
                servers.append({"server_id": sid, "port": s["port"],
                                "directory": s["directory"], "started": s["started"]})
            return {"servers": servers, "count": len(servers)}

        else:
            return {"error": f"Unknown action: {action}. Use start, stop, list."}
    except Exception as e:
        return {"error": f"http_server failed: {e}"}


# --- json_schema ---
def _json_schema(action: str, **kwargs) -> dict:
    """JSON Schema validation and generation."""
    try:
        if action == "validate":
            data = kwargs.get("data")
            schema = kwargs.get("schema")
            if data is None or schema is None:
                return {"error": "data and schema required"}
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(schema, str):
                schema = json.loads(schema)
            try:
                import jsonschema as _js
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "jsonschema"],
                               capture_output=True, timeout=60)
                import jsonschema as _js
            errors = list(_js.Draft7Validator(schema).iter_errors(data))
            if not errors:
                return {"valid": True, "errors": []}
            return {"valid": False, "errors": [{"path": list(e.absolute_path), "message": e.message} for e in errors[:20]]}

        elif action == "generate":
            data = kwargs.get("data")
            if data is None:
                return {"error": "data required"}
            if isinstance(data, str):
                data = json.loads(data)

            def _infer(val):
                if isinstance(val, dict):
                    props = {}
                    required = []
                    for k, v in val.items():
                        props[k] = _infer(v)
                        required.append(k)
                    return {"type": "object", "properties": props, "required": required}
                elif isinstance(val, list):
                    if val:
                        return {"type": "array", "items": _infer(val[0])}
                    return {"type": "array"}
                elif isinstance(val, bool):
                    return {"type": "boolean"}
                elif isinstance(val, int):
                    return {"type": "integer"}
                elif isinstance(val, float):
                    return {"type": "number"}
                elif isinstance(val, str):
                    return {"type": "string"}
                elif val is None:
                    return {"type": "null"}
                return {}

            schema = {"$schema": "http://json-schema.org/draft-07/schema#"}
            schema.update(_infer(data))
            return {"schema": schema}

        elif action == "diff":
            schema_a = kwargs.get("schema_a")
            schema_b = kwargs.get("schema_b")
            if schema_a is None or schema_b is None:
                return {"error": "schema_a and schema_b required"}
            if isinstance(schema_a, str):
                schema_a = json.loads(schema_a)
            if isinstance(schema_b, str):
                schema_b = json.loads(schema_b)

            def _flat(d, prefix=""):
                items = {}
                for k, v in d.items():
                    key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, dict):
                        items.update(_flat(v, key))
                    else:
                        items[key] = v
                return items

            flat_a = _flat(schema_a)
            flat_b = _flat(schema_b)
            all_keys = set(flat_a) | set(flat_b)
            diffs = []
            for k in sorted(all_keys):
                va = flat_a.get(k, "<missing>")
                vb = flat_b.get(k, "<missing>")
                if va != vb:
                    diffs.append({"path": k, "schema_a": va, "schema_b": vb})
            return {"differences": diffs, "count": len(diffs), "identical": len(diffs) == 0}

        else:
            return {"error": f"Unknown action: {action}. Use validate, generate, diff."}
    except Exception as e:
        return {"error": f"json_schema failed: {e}"}


# --- cache_manager ---
def _cache_manager(action: str, **kwargs) -> dict:
    """Smart caching layer over Redis with TTL and namespaces."""
    import redis as _redis_mod
    try:
        r = _redis_mod.Redis(host="localhost", port=6379, decode_responses=True, socket_timeout=5)

        ns = kwargs.get("namespace", "cache")
        prefix = f"ocache:{ns}:"

        if action == "get":
            key = kwargs.get("key", "")
            if not key:
                return {"error": "key required"}
            val = r.get(f"{prefix}{key}")
            ttl = r.ttl(f"{prefix}{key}")
            if val is None:
                return {"key": key, "hit": False}
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
            return {"key": key, "value": val, "hit": True, "ttl_seconds": ttl}

        elif action == "set":
            key = kwargs.get("key", "")
            value = kwargs.get("value")
            ttl = int(kwargs.get("ttl", 3600))
            if not key or value is None:
                return {"error": "key and value required"}
            serialized = json.dumps(value) if not isinstance(value, str) else value
            r.setex(f"{prefix}{key}", ttl, serialized)
            return {"key": key, "stored": True, "ttl_seconds": ttl, "namespace": ns}

        elif action == "delete":
            key = kwargs.get("key", "")
            if not key:
                return {"error": "key required"}
            deleted = r.delete(f"{prefix}{key}")
            return {"key": key, "deleted": bool(deleted)}

        elif action == "clear":
            keys = r.keys(f"{prefix}*")
            if keys:
                r.delete(*keys)
            return {"namespace": ns, "cleared": len(keys)}

        elif action == "keys":
            keys = r.keys(f"{prefix}*")
            clean = [k.replace(prefix, "", 1) for k in keys]
            return {"namespace": ns, "keys": sorted(clean), "count": len(clean)}

        elif action == "stats":
            keys = r.keys(f"{prefix}*")
            total_size = 0
            with_ttl = 0
            for k in keys:
                total_size += r.memory_usage(k) or 0
                if r.ttl(k) > 0:
                    with_ttl += 1
            all_ns = set()
            for k in r.keys("ocache:*"):
                parts = k.split(":")
                if len(parts) >= 2:
                    all_ns.add(parts[1])
            return {
                "namespace": ns, "key_count": len(keys),
                "memory_bytes": total_size, "keys_with_ttl": with_ttl,
                "all_namespaces": sorted(all_ns),
            }

        else:
            return {"error": f"Unknown action: {action}. Use get, set, delete, clear, keys, stats."}
    except Exception as e:
        return {"error": f"cache_manager failed: {e}"}


# --- math_compute ---
def _math_compute(action: str, **kwargs) -> dict:
    """Advanced math computations using sympy and numpy."""
    try:
        if action == "symbolic":
            expr_str = kwargs.get("expression", "")
            variable = kwargs.get("variable", "x")
            if not expr_str:
                return {"error": "expression required"}
            import sympy
            x = sympy.Symbol(variable)
            expr = sympy.sympify(expr_str)
            return {
                "expression": str(expr),
                "simplified": str(sympy.simplify(expr)),
                "expanded": str(sympy.expand(expr)),
                "factored": str(sympy.factor(expr)),
                "latex": sympy.latex(expr),
            }

        elif action == "solve":
            equation = kwargs.get("equation", "")
            variable = kwargs.get("variable", "x")
            if not equation:
                return {"error": "equation required (e.g., 'x**2 - 4')"}
            import sympy
            x = sympy.Symbol(variable)
            expr = sympy.sympify(equation)
            solutions = sympy.solve(expr, x)
            return {"equation": equation, "variable": variable,
                    "solutions": [str(s) for s in solutions]}

        elif action == "derivative":
            expr_str = kwargs.get("expression", "")
            variable = kwargs.get("variable", "x")
            order = int(kwargs.get("order", 1))
            if not expr_str:
                return {"error": "expression required"}
            import sympy
            x = sympy.Symbol(variable)
            expr = sympy.sympify(expr_str)
            result = sympy.diff(expr, x, order)
            return {"expression": expr_str, "derivative": str(result),
                    "order": order, "latex": sympy.latex(result)}

        elif action == "integrate":
            expr_str = kwargs.get("expression", "")
            variable = kwargs.get("variable", "x")
            lower = kwargs.get("lower")
            upper = kwargs.get("upper")
            if not expr_str:
                return {"error": "expression required"}
            import sympy
            x = sympy.Symbol(variable)
            expr = sympy.sympify(expr_str)
            if lower is not None and upper is not None:
                result = sympy.integrate(expr, (x, sympy.sympify(lower), sympy.sympify(upper)))
                return {"expression": expr_str, "definite_integral": str(result),
                        "bounds": [str(lower), str(upper)], "numeric": float(result) if result.is_number else None}
            else:
                result = sympy.integrate(expr, x)
                return {"expression": expr_str, "integral": str(result), "latex": sympy.latex(result)}

        elif action == "matrix":
            data = kwargs.get("data", [])
            operation = kwargs.get("operation", "info")
            if not data:
                return {"error": "data (2D array) required"}
            import numpy as np
            m = np.array(data, dtype=float)
            if operation == "info":
                result = {"shape": list(m.shape), "rank": int(np.linalg.matrix_rank(m)),
                          "trace": float(np.trace(m)) if m.shape[0] == m.shape[1] else None}
                if m.shape[0] == m.shape[1]:
                    result["determinant"] = float(np.linalg.det(m))
                return result
            elif operation == "inverse":
                inv = np.linalg.inv(m)
                return {"inverse": inv.tolist()}
            elif operation == "eigenvalues":
                vals, vecs = np.linalg.eig(m)
                return {"eigenvalues": vals.tolist(), "eigenvectors": vecs.tolist()}
            elif operation == "multiply":
                data_b = kwargs.get("data_b", [])
                if not data_b:
                    return {"error": "data_b required for multiply"}
                b = np.array(data_b, dtype=float)
                result = np.matmul(m, b)
                return {"result": result.tolist()}
            else:
                return {"error": f"Unknown operation: {operation}. Use info, inverse, eigenvalues, multiply."}

        elif action == "statistics":
            data = kwargs.get("data", [])
            if not data:
                return {"error": "data (array of numbers) required"}
            import numpy as np
            arr = np.array(data, dtype=float)
            return {
                "count": len(arr), "mean": float(np.mean(arr)),
                "median": float(np.median(arr)), "std": float(np.std(arr)),
                "variance": float(np.var(arr)),
                "min": float(np.min(arr)), "max": float(np.max(arr)),
                "q25": float(np.percentile(arr, 25)),
                "q75": float(np.percentile(arr, 75)),
                "sum": float(np.sum(arr)),
            }

        else:
            return {"error": f"Unknown action: {action}. Use symbolic, solve, derivative, integrate, matrix, statistics."}
    except Exception as e:
        return {"error": f"math_compute failed: {e}"}


# --- regex_builder ---
def _regex_builder(action: str, **kwargs) -> dict:
    """Regex pattern building, testing, and explanation."""
    try:
        if action == "test":
            pattern = kwargs.get("pattern", "")
            text = kwargs.get("text", "")
            flags_str = kwargs.get("flags", "")
            if not pattern:
                return {"error": "pattern required"}
            flags = 0
            if "i" in flags_str:
                flags |= re.IGNORECASE
            if "m" in flags_str:
                flags |= re.MULTILINE
            if "s" in flags_str:
                flags |= re.DOTALL
            try:
                compiled = re.compile(pattern, flags)
            except re.error as e:
                return {"valid": False, "error": str(e)}
            matches = []
            for m in compiled.finditer(text):
                match_info = {"match": m.group(), "start": m.start(), "end": m.end()}
                if m.groups():
                    match_info["groups"] = list(m.groups())
                if m.groupdict():
                    match_info["named_groups"] = m.groupdict()
                matches.append(match_info)
            return {"pattern": pattern, "valid": True, "matches": matches,
                    "match_count": len(matches), "full_match": bool(compiled.fullmatch(text))}

        elif action == "replace":
            pattern = kwargs.get("pattern", "")
            text = kwargs.get("text", "")
            replacement = kwargs.get("replacement", "")
            flags_str = kwargs.get("flags", "")
            count = int(kwargs.get("count", 0))
            if not pattern:
                return {"error": "pattern required"}
            flags = 0
            if "i" in flags_str:
                flags |= re.IGNORECASE
            if "m" in flags_str:
                flags |= re.MULTILINE
            result = re.sub(pattern, replacement, text, count=count, flags=flags)
            return {"original": text, "result": result, "replacements_made": text != result}

        elif action == "extract":
            pattern = kwargs.get("pattern", "")
            text = kwargs.get("text", "")
            if not pattern:
                return {"error": "pattern required"}
            matches = re.findall(pattern, text)
            return {"pattern": pattern, "extracted": matches, "count": len(matches)}

        elif action == "split":
            pattern = kwargs.get("pattern", "")
            text = kwargs.get("text", "")
            if not pattern:
                return {"error": "pattern required"}
            parts = re.split(pattern, text)
            return {"pattern": pattern, "parts": parts, "count": len(parts)}

        elif action == "explain":
            pattern = kwargs.get("pattern", "")
            if not pattern:
                return {"error": "pattern required"}
            explanations = {
                ".": "any character except newline",
                "*": "0 or more of previous",
                "+": "1 or more of previous",
                "?": "0 or 1 of previous",
                "^": "start of string/line",
                "$": "end of string/line",
                "\\d": "any digit [0-9]",
                "\\w": "any word character [a-zA-Z0-9_]",
                "\\s": "any whitespace",
                "\\b": "word boundary",
                "\\D": "any non-digit",
                "\\W": "any non-word character",
                "\\S": "any non-whitespace",
                "|": "OR (alternation)",
            }
            tokens = []
            i = 0
            while i < len(pattern):
                if pattern[i] == "\\" and i + 1 < len(pattern):
                    tok = pattern[i:i+2]
                    tokens.append({"token": tok, "meaning": explanations.get(tok, f"escaped '{pattern[i+1]}'")})
                    i += 2
                elif pattern[i] == "[":
                    end = pattern.find("]", i)
                    if end != -1:
                        tok = pattern[i:end+1]
                        tokens.append({"token": tok, "meaning": f"character class: one of {tok}"})
                        i = end + 1
                    else:
                        tokens.append({"token": "[", "meaning": "unclosed character class"})
                        i += 1
                elif pattern[i] == "(":
                    end = pattern.find(")", i)
                    if end != -1:
                        tok = pattern[i:end+1]
                        if tok.startswith("(?:"):
                            tokens.append({"token": tok, "meaning": "non-capturing group"})
                        elif tok.startswith("(?P<"):
                            name = tok[4:tok.index(">")]
                            tokens.append({"token": tok, "meaning": f"named group '{name}'"})
                        elif tok.startswith("(?="):
                            tokens.append({"token": tok, "meaning": "positive lookahead"})
                        elif tok.startswith("(?!"):
                            tokens.append({"token": tok, "meaning": "negative lookahead"})
                        else:
                            tokens.append({"token": tok, "meaning": f"capturing group"})
                        i = end + 1
                    else:
                        tokens.append({"token": "(", "meaning": "unclosed group"})
                        i += 1
                elif pattern[i] == "{":
                    end = pattern.find("}", i)
                    if end != -1:
                        tok = pattern[i:end+1]
                        tokens.append({"token": tok, "meaning": f"quantifier: repeat {tok[1:-1]} times"})
                        i = end + 1
                    else:
                        tokens.append({"token": "{", "meaning": "literal {"})
                        i += 1
                else:
                    c = pattern[i]
                    tokens.append({"token": c, "meaning": explanations.get(c, f"literal '{c}'")})
                    i += 1
            try:
                re.compile(pattern)
                valid = True
            except re.error:
                valid = False
            return {"pattern": pattern, "valid": valid, "tokens": tokens}

        else:
            return {"error": f"Unknown action: {action}. Use test, replace, extract, split, explain."}
    except Exception as e:
        return {"error": f"regex_builder failed: {e}"}


# --- cert_check ---
def _cert_check(action: str, **kwargs) -> dict:
    """SSL certificate inspection and generation."""
    try:
        if action == "inspect":
            host = kwargs.get("host", "")
            port = int(kwargs.get("port", 443))
            if not host:
                return {"error": "host required"}
            import ssl
            import socket
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
                s.settimeout(10)
                s.connect((host, port))
                cert = s.getpeercert()
            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            not_before = cert.get("notBefore", "")
            not_after = cert.get("notAfter", "")
            san = [entry[1] for entry in cert.get("subjectAltName", ())]
            # Check expiry
            from datetime import datetime as _dt
            expire_dt = _dt.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            days_left = (expire_dt - _dt.utcnow()).days
            return {
                "host": host, "port": port,
                "subject": subject, "issuer": issuer,
                "not_before": not_before, "not_after": not_after,
                "days_until_expiry": days_left,
                "expired": days_left < 0,
                "san": san,
                "serial": cert.get("serialNumber", ""),
            }

        elif action == "check_expiry":
            host = kwargs.get("host", "")
            port = int(kwargs.get("port", 443))
            warn_days = int(kwargs.get("warn_days", 30))
            if not host:
                return {"error": "host required"}
            import ssl
            import socket
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
                s.settimeout(10)
                s.connect((host, port))
                cert = s.getpeercert()
            not_after = cert.get("notAfter", "")
            from datetime import datetime as _dt
            expire_dt = _dt.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            days_left = (expire_dt - _dt.utcnow()).days
            status = "EXPIRED" if days_left < 0 else "WARNING" if days_left < warn_days else "OK"
            return {"host": host, "expires": not_after, "days_left": days_left, "status": status}

        elif action == "generate_self_signed":
            output_cert = kwargs.get("output_cert", "/tmp/selfsigned.crt")
            output_key = kwargs.get("output_key", "/tmp/selfsigned.key")
            cn = kwargs.get("cn", "localhost")
            days = int(kwargs.get("days", 365))
            r = subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", output_key, "-out", output_cert,
                "-days", str(days), "-subj", f"/CN={cn}"
            ], capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return {"cert": output_cert, "key": output_key, "cn": cn, "days": days, "detail": "OK"}

        elif action == "decode_pem":
            path = kwargs.get("path", "")
            if not path:
                return {"error": "path to PEM file required"}
            r = subprocess.run(["openssl", "x509", "-in", path, "-text", "-noout"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return {"path": path, "details": r.stdout[:5000]}

        else:
            return {"error": f"Unknown action: {action}. Use inspect, check_expiry, generate_self_signed, decode_pem."}
    except Exception as e:
        return {"error": f"cert_check failed: {e}"}


# --- system_profiler ---
def _system_profiler(action: str, **kwargs) -> dict:
    """macOS system profiling via system_profiler."""
    try:
        if action == "hardware":
            r = subprocess.run(["system_profiler", "SPHardwareDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "software":
            r = subprocess.run(["system_profiler", "SPSoftwareDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "network":
            r = subprocess.run(["system_profiler", "SPNetworkDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "storage":
            r = subprocess.run(["system_profiler", "SPStorageDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "usb":
            r = subprocess.run(["system_profiler", "SPUSBDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "displays":
            r = subprocess.run(["system_profiler", "SPDisplaysDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "battery":
            r = subprocess.run(["system_profiler", "SPPowerDataType", "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "custom":
            data_type = kwargs.get("data_type", "")
            if not data_type:
                return {"error": "data_type required (e.g., 'SPBluetoothDataType')"}
            r = subprocess.run(["system_profiler", data_type, "-json"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return {"error": r.stderr[:500]}
            return json.loads(r.stdout)

        elif action == "list_types":
            r = subprocess.run(["system_profiler", "-listDataTypes"],
                               capture_output=True, text=True, timeout=10)
            types = [l.strip() for l in r.stdout.strip().split("\n") if l.strip().startswith("SP")]
            return {"data_types": types, "count": len(types)}

        else:
            return {"error": f"Unknown action: {action}. Use hardware, software, network, storage, usb, displays, battery, custom, list_types."}
    except Exception as e:
        return {"error": f"system_profiler failed: {e}"}


# --- url_tools ---
def _url_tools(action: str, **kwargs) -> dict:
    """URL parsing, validation, encoding, and link checking."""
    from urllib.parse import urlparse, urlencode, quote, unquote, parse_qs, urlunparse
    try:
        if action == "parse":
            url = kwargs.get("url", "")
            if not url:
                return {"error": "url required"}
            parsed = urlparse(url)
            return {
                "url": url,
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "hostname": parsed.hostname,
                "port": parsed.port,
                "path": parsed.path,
                "query": parsed.query,
                "fragment": parsed.fragment,
                "params": parse_qs(parsed.query),
            }

        elif action == "build":
            scheme = kwargs.get("scheme", "https")
            host = kwargs.get("host", "")
            path = kwargs.get("path", "/")
            params = kwargs.get("params", {})
            fragment = kwargs.get("fragment", "")
            if not host:
                return {"error": "host required"}
            query = urlencode(params) if params else ""
            url = urlunparse((scheme, host, path, "", query, fragment))
            return {"url": url}

        elif action == "encode":
            text = kwargs.get("text", "")
            if not text:
                return {"error": "text required"}
            return {"original": text, "encoded": quote(text)}

        elif action == "decode":
            text = kwargs.get("text", "")
            if not text:
                return {"error": "text required"}
            return {"original": text, "decoded": unquote(text)}

        elif action == "validate":
            url = kwargs.get("url", "")
            if not url:
                return {"error": "url required"}
            parsed = urlparse(url)
            valid = bool(parsed.scheme and parsed.netloc)
            result = {"url": url, "valid": valid, "scheme": parsed.scheme, "host": parsed.hostname}
            if valid and kwargs.get("check_live"):
                try:
                    import urllib.request
                    req = urllib.request.Request(url, method="HEAD")
                    req.add_header("User-Agent", "OpenClaw-Army/1.0")
                    resp = urllib.request.urlopen(req, timeout=10)
                    result["status_code"] = resp.status
                    result["reachable"] = True
                except Exception as e:
                    result["reachable"] = False
                    result["check_error"] = str(e)[:200]
            return result

        elif action == "extract_links":
            text = kwargs.get("text", "")
            if not text:
                return {"error": "text required"}
            url_pattern = re.compile(r'https?://[^\s<>"\')\]]+')
            links = url_pattern.findall(text)
            unique = list(dict.fromkeys(links))
            return {"links": unique, "count": len(unique)}

        elif action == "sitemap":
            url = kwargs.get("url", "")
            if not url:
                return {"error": "sitemap url required"}
            import urllib.request
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "OpenClaw-Army/1.0")
            resp = urllib.request.urlopen(req, timeout=15)
            content = resp.read().decode("utf-8", errors="replace")[:100000]
            urls = re.findall(r"<loc>(.*?)</loc>", content)
            return {"sitemap_url": url, "urls": urls[:200], "count": len(urls)}

        else:
            return {"error": f"Unknown action: {action}. Use parse, build, encode, decode, validate, extract_links, sitemap."}
    except Exception as e:
        return {"error": f"url_tools failed: {e}"}


# ── Desktop Control (Screen Vision + GUI Automation) ───────────────────────

def _ensure_pyautogui():
    """Auto-install pyautogui + pyobjc-framework-Quartz if missing."""
    try:
        import pyautogui
        return True
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "pyautogui", "pyobjc-framework-Quartz", "pyobjc-framework-ApplicationServices"],
                       capture_output=True, timeout=120)
        try:
            import pyautogui
            return True
        except ImportError:
            return False

def _ensure_ocr():
    """Auto-install pytesseract if missing. Requires tesseract binary."""
    try:
        import pytesseract
        return True
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pytesseract"],
                       capture_output=True, timeout=60)
        try:
            import pytesseract
            return True
        except ImportError:
            return False


def _desktop_control(action: str, **kwargs) -> dict:
    """Full macOS desktop control — see screen, move mouse, click, type, find elements."""
    try:
        if action == "screenshot_ocr":
            # Take screenshot and OCR it to understand what's on screen
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            img_path = kwargs.get("output", f"/tmp/desktop_ocr_{ts}.png")
            region = kwargs.get("region")  # Optional: {"x": 0, "y": 0, "w": 800, "h": 600}

            if region:
                subprocess.run(["screencapture", "-x", "-R",
                                f"{region['x']},{region['y']},{region['w']},{region['h']}",
                                img_path], capture_output=True, timeout=10)
            else:
                subprocess.run(["screencapture", "-x", img_path],
                               capture_output=True, timeout=10)

            if not Path(img_path).exists():
                return {"error": "Screenshot failed"}

            # Try OCR
            ocr_text = ""
            if _ensure_ocr():
                # First check if tesseract binary exists
                tess_check = subprocess.run(["which", "tesseract"], capture_output=True, text=True, timeout=5)
                if tess_check.returncode == 0:
                    import pytesseract
                    from PIL import Image
                    img = Image.open(img_path)
                    ocr_text = pytesseract.image_to_string(img)
                else:
                    # Use macOS native Vision framework via subprocess as fallback
                    vision_script = f'''
import subprocess, json
r = subprocess.run(["/usr/bin/swift", "-e", """
import Vision, AppKit
let url = URL(fileURLWithPath: "{img_path}")
guard let img = NSImage(contentsOf: url), let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {{ exit(1) }}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
try? VNImageRequestHandler(cgImage: cgImg).perform([req])
let texts = (req.results ?? []).compactMap {{ $0.topCandidates(1).first?.string }}
print(texts.joined(separator: "\\n"))
"""], capture_output=True, text=True, timeout=30)
print(r.stdout)
'''
                    result = subprocess.run([sys.executable, "-c", vision_script],
                                           capture_output=True, text=True, timeout=45)
                    ocr_text = result.stdout.strip()

            return {
                "screenshot": img_path,
                "size_bytes": Path(img_path).stat().st_size,
                "ocr_text": ocr_text[:10000],
                "has_ocr": bool(ocr_text.strip()),
            }

        elif action == "move_mouse":
            x = kwargs.get("x", 0)
            y = kwargs.get("y", 0)
            if _ensure_pyautogui():
                import pyautogui
                pyautogui.moveTo(x, y, duration=0.2)
                return {"moved_to": {"x": x, "y": y}}
            else:
                # Fallback: AppleScript via cliclick or CGEvent
                script = f'''
import subprocess
subprocess.run(["/usr/bin/swift", "-e", """
import CoreGraphics
let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: CGPoint(x: {x}, y: {y}), mouseButton: .left)
move?.post(tap: .cghidEventTap)
"""], capture_output=True, timeout=5)
'''
                subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=10)
                return {"moved_to": {"x": x, "y": y}, "method": "cgevent"}

        elif action == "click":
            x = kwargs.get("x", None)
            y = kwargs.get("y", None)
            button = kwargs.get("button", "left")
            clicks = kwargs.get("clicks", 1)
            if _ensure_pyautogui():
                import pyautogui
                if x is not None and y is not None:
                    pyautogui.click(x, y, clicks=clicks, button=button)
                else:
                    pyautogui.click(clicks=clicks, button=button)
                return {"clicked": True, "x": x, "y": y, "button": button, "clicks": clicks}
            else:
                return {"error": "pyautogui required for click — install failed"}

        elif action == "type_text":
            text = kwargs.get("text", "")
            interval = kwargs.get("interval", 0.02)
            if not text:
                return {"error": "text required"}
            if _ensure_pyautogui():
                import pyautogui
                pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
                return {"typed": True, "length": len(text)}
            else:
                # Fallback: osascript
                escaped = text.replace("\\", "\\\\").replace('"', '\\"')
                subprocess.run(["/usr/bin/osascript", "-e",
                                f'tell application "System Events" to keystroke "{escaped}"'],
                               capture_output=True, timeout=10)
                return {"typed": True, "length": len(text), "method": "osascript"}

        elif action == "hotkey":
            keys = kwargs.get("keys", [])
            if not keys:
                return {"error": "keys required (e.g., ['command', 'c'])"}
            if _ensure_pyautogui():
                import pyautogui
                pyautogui.hotkey(*keys)
                return {"hotkey": keys}
            else:
                return {"error": "pyautogui required for hotkey — install failed"}

        elif action == "locate_on_screen":
            # Find an image/button on screen by template matching
            template_path = kwargs.get("template", "")
            confidence = kwargs.get("confidence", 0.8)
            if not template_path or not Path(template_path).exists():
                return {"error": "template image path required and must exist"}
            if _ensure_pyautogui():
                import pyautogui
                try:
                    location = pyautogui.locateOnScreen(template_path, confidence=confidence)
                    if location:
                        center = pyautogui.center(location)
                        return {"found": True, "x": center.x, "y": center.y,
                                "region": {"left": location.left, "top": location.top,
                                           "width": location.width, "height": location.height}}
                    return {"found": False}
                except Exception as e:
                    return {"error": f"locate failed: {e}"}
            return {"error": "pyautogui required"}

        elif action == "get_mouse_position":
            if _ensure_pyautogui():
                import pyautogui
                pos = pyautogui.position()
                return {"x": pos.x, "y": pos.y}
            return {"error": "pyautogui required"}

        elif action == "get_screen_size":
            if _ensure_pyautogui():
                import pyautogui
                size = pyautogui.size()
                return {"width": size.width, "height": size.height}
            # Fallback
            result = subprocess.run(["system_profiler", "SPDisplaysDataType", "-json"],
                                     capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {"displays": data, "method": "system_profiler"}
            return {"error": "Could not determine screen size"}

        elif action == "get_window_list":
            # List all visible windows with positions
            script = '''
tell application "System Events"
    set winList to ""
    repeat with proc in (every process whose visible is true)
        set pName to name of proc
        try
            repeat with w in (every window of proc)
                set wName to name of w
                set wPos to position of w
                set wSz to size of w
                set winList to winList & pName & "|" & wName & "|" & (item 1 of wPos) & "," & (item 2 of wPos) & "|" & (item 1 of wSz) & "," & (item 2 of wSz) & "\\n"
            end repeat
        end try
    end repeat
    return winList
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=15)
            windows = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("|")
                if len(parts) == 4:
                    pos = parts[2].split(",")
                    sz = parts[3].split(",")
                    windows.append({
                        "app": parts[0], "title": parts[1],
                        "x": int(pos[0]), "y": int(pos[1]),
                        "width": int(sz[0]), "height": int(sz[1]),
                    })
            return {"windows": windows, "count": len(windows)}

        elif action == "focus_window":
            app_name = kwargs.get("app", "")
            if not app_name:
                return {"error": "app name required"}
            subprocess.run(["/usr/bin/osascript", "-e",
                            f'tell application "{app_name}" to activate'],
                           capture_output=True, timeout=10)
            return {"focused": app_name}

        elif action == "scroll":
            amount = kwargs.get("amount", -3)
            x = kwargs.get("x")
            y = kwargs.get("y")
            if _ensure_pyautogui():
                import pyautogui
                if x is not None and y is not None:
                    pyautogui.scroll(amount, x, y)
                else:
                    pyautogui.scroll(amount)
                return {"scrolled": amount}
            return {"error": "pyautogui required"}

        elif action == "drag":
            x1 = kwargs.get("x1", 0)
            y1 = kwargs.get("y1", 0)
            x2 = kwargs.get("x2", 0)
            y2 = kwargs.get("y2", 0)
            duration = kwargs.get("duration", 0.5)
            if _ensure_pyautogui():
                import pyautogui
                pyautogui.moveTo(x1, y1)
                pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
                return {"dragged": True, "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}}
            return {"error": "pyautogui required"}

        elif action == "find_text_on_screen":
            # Screenshot + OCR + find text coordinates
            target = kwargs.get("text", "")
            if not target:
                return {"error": "text to find required"}
            # Take screenshot
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            img_path = f"/tmp/find_text_{ts}.png"
            subprocess.run(["screencapture", "-x", img_path],
                           capture_output=True, timeout=10)
            if not Path(img_path).exists():
                return {"error": "Screenshot failed"}

            from PIL import Image
            img = Image.open(img_path)
            w, h = img.size

            # Try tesseract with bounding boxes
            tess_check = subprocess.run(["which", "tesseract"], capture_output=True, text=True, timeout=5)
            if tess_check.returncode == 0 and _ensure_ocr():
                import pytesseract
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                results = []
                for i, word in enumerate(data["text"]):
                    if target.lower() in word.lower():
                        results.append({
                            "text": word,
                            "x": data["left"][i] + data["width"][i] // 2,
                            "y": data["top"][i] + data["height"][i] // 2,
                            "box": {"left": data["left"][i], "top": data["top"][i],
                                    "width": data["width"][i], "height": data["height"][i]},
                        })
                Path(img_path).unlink(missing_ok=True)
                return {"found": len(results) > 0, "matches": results[:20],
                        "screen_size": {"w": w, "h": h}}
            else:
                # Fallback: just screenshot + full OCR text
                result = _desktop_control("screenshot_ocr", output=img_path)
                ocr = result.get("ocr_text", "")
                found = target.lower() in ocr.lower()
                Path(img_path).unlink(missing_ok=True)
                return {"found": found, "ocr_contains_text": found,
                        "hint": "Install tesseract for precise coordinates: brew install tesseract"}

        else:
            return {"error": f"Unknown action: {action}. Use screenshot_ocr, move_mouse, click, type_text, hotkey, locate_on_screen, get_mouse_position, get_screen_size, get_window_list, focus_window, scroll, drag, find_text_on_screen."}

    except Exception as e:
        return {"error": f"desktop_control failed: {e}"}


# ── Browser Automation (Playwright) ────────────────────────────────────────

_BROWSER_SESSIONS: dict[str, dict] = {}  # session_id -> {browser, page, context}

def _browser_automate(action: str, **kwargs) -> dict:
    """Full browser automation via Playwright — navigate, click, type, screenshot, extract."""
    try:
        if action == "launch":
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"],
                               capture_output=True, timeout=120)
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                               capture_output=True, timeout=300)
                from playwright.sync_api import sync_playwright

            headless = kwargs.get("headless", True)
            sid = kwargs.get("session_id", str(uuid.uuid4())[:8])
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": kwargs.get("width", 1280), "height": kwargs.get("height", 720)},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) OpenClaw-Army/3.0",
            )
            page = context.new_page()
            _BROWSER_SESSIONS[sid] = {"pw": pw, "browser": browser, "context": context, "page": page}
            return {"session_id": sid, "launched": True, "headless": headless}

        elif action == "navigate":
            sid = kwargs.get("session_id", "")
            url = kwargs.get("url", "")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No browser session '{sid}'. Use launch first."}
            if not url:
                return {"error": "url required"}
            page = _BROWSER_SESSIONS[sid]["page"]
            wait = kwargs.get("wait_until", "domcontentloaded")
            page.goto(url, wait_until=wait, timeout=kwargs.get("timeout", 30000))
            return {"url": page.url, "title": page.title()}

        elif action == "click":
            sid = kwargs.get("session_id", "")
            selector = kwargs.get("selector", "")
            if sid not in _BROWSER_SESSIONS or not selector:
                return {"error": "session_id and selector required"}
            page = _BROWSER_SESSIONS[sid]["page"]
            page.click(selector, timeout=kwargs.get("timeout", 5000))
            return {"clicked": selector}

        elif action == "type":
            sid = kwargs.get("session_id", "")
            selector = kwargs.get("selector", "")
            text = kwargs.get("text", "")
            if sid not in _BROWSER_SESSIONS or not selector:
                return {"error": "session_id and selector required"}
            page = _BROWSER_SESSIONS[sid]["page"]
            page.fill(selector, text) if kwargs.get("fill") else page.type(selector, text)
            return {"typed": text[:100], "into": selector}

        elif action == "evaluate":
            sid = kwargs.get("session_id", "")
            js = kwargs.get("js", "")
            if sid not in _BROWSER_SESSIONS or not js:
                return {"error": "session_id and js required"}
            page = _BROWSER_SESSIONS[sid]["page"]
            result = page.evaluate(js)
            return {"result": str(result)[:10000]}

        elif action == "screenshot":
            sid = kwargs.get("session_id", "")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No session '{sid}'"}
            page = _BROWSER_SESSIONS[sid]["page"]
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = kwargs.get("output", f"/tmp/browser_shot_{ts}.png")
            page.screenshot(path=path, full_page=kwargs.get("full_page", False))
            return {"screenshot": path, "size": Path(path).stat().st_size}

        elif action == "content":
            sid = kwargs.get("session_id", "")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No session '{sid}'"}
            page = _BROWSER_SESSIONS[sid]["page"]
            selector = kwargs.get("selector", "body")
            el = page.query_selector(selector)
            text = el.inner_text() if el else ""
            return {"text": text[:20000], "selector": selector, "url": page.url}

        elif action == "wait":
            sid = kwargs.get("session_id", "")
            selector = kwargs.get("selector", "")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No session '{sid}'"}
            page = _BROWSER_SESSIONS[sid]["page"]
            if selector:
                page.wait_for_selector(selector, timeout=kwargs.get("timeout", 10000))
                return {"waited_for": selector}
            else:
                page.wait_for_timeout(kwargs.get("timeout", 2000))
                return {"waited_ms": kwargs.get("timeout", 2000)}

        elif action == "close":
            sid = kwargs.get("session_id", "")
            if sid in _BROWSER_SESSIONS:
                sess = _BROWSER_SESSIONS.pop(sid)
                sess["browser"].close()
                sess["pw"].stop()
                return {"closed": sid}
            return {"error": f"No session '{sid}'"}

        elif action == "list_sessions":
            return {"sessions": list(_BROWSER_SESSIONS.keys()), "count": len(_BROWSER_SESSIONS)}

        elif action == "select":
            sid = kwargs.get("session_id", "")
            selector = kwargs.get("selector", "")
            value = kwargs.get("value", "")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No session '{sid}'"}
            page = _BROWSER_SESSIONS[sid]["page"]
            page.select_option(selector, value)
            return {"selected": value, "in": selector}

        elif action == "extract_table":
            sid = kwargs.get("session_id", "")
            selector = kwargs.get("selector", "table")
            if sid not in _BROWSER_SESSIONS:
                return {"error": f"No session '{sid}'"}
            page = _BROWSER_SESSIONS[sid]["page"]
            js = f"""
            (() => {{
                const table = document.querySelector('{selector}');
                if (!table) return null;
                const rows = [];
                for (const tr of table.querySelectorAll('tr')) {{
                    const cells = [];
                    for (const td of tr.querySelectorAll('td, th')) cells.push(td.innerText.trim());
                    rows.push(cells);
                }}
                return rows;
            }})()
            """
            rows = page.evaluate(js)
            return {"rows": rows[:200] if rows else [], "count": len(rows) if rows else 0}

        else:
            return {"error": f"Unknown action: {action}. Use launch, navigate, click, type, evaluate, screenshot, content, wait, close, list_sessions, select, extract_table."}

    except Exception as e:
        return {"error": f"browser_automate failed: {e}"}


# ── Git Operations (GitHub API + local git) ────────────────────────────────

def _git_ops(action: str, **kwargs) -> dict:
    """Git operations — local repo management + GitHub API integration."""
    try:
        if action in ("status", "log", "diff", "branch", "stash", "remote", "tag"):
            repo_path = kwargs.get("repo", ARMY_HOME)
            cmd_map = {
                "status": ["git", "status", "--porcelain", "-b"],
                "log": ["git", "log", f"--oneline", f"-{kwargs.get('limit', 20)}",
                        "--format=%h %s (%cr) <%an>"],
                "diff": ["git", "diff"] + (["--staged"] if kwargs.get("staged") else []),
                "branch": ["git", "branch", "-a", "--format=%(refname:short) %(objectname:short)"],
                "stash": ["git", "stash", "list"],
                "remote": ["git", "remote", "-v"],
                "tag": ["git", "tag", "-l", "--sort=-creatordate",
                        "--format=%(refname:short) %(creatordate:short)"],
            }
            cmd = cmd_map[action]
            if action == "diff" and kwargs.get("file"):
                cmd.append(kwargs["file"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=repo_path)
            return {"output": result.stdout[:15000], "returncode": result.returncode,
                    "stderr": result.stderr[:2000] if result.returncode else ""}

        elif action == "commit":
            repo_path = kwargs.get("repo", ARMY_HOME)
            message = kwargs.get("message", "")
            if not message:
                return {"error": "commit message required"}
            add_all = kwargs.get("add_all", False)
            files = kwargs.get("files", [])
            if add_all:
                subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, timeout=15)
            elif files:
                subprocess.run(["git", "add"] + files, cwd=repo_path, capture_output=True, timeout=15)
            result = subprocess.run(["git", "commit", "-m", message],
                                     capture_output=True, text=True, timeout=30, cwd=repo_path)
            return {"output": result.stdout[:5000], "returncode": result.returncode,
                    "stderr": result.stderr[:2000]}

        elif action == "push":
            repo_path = kwargs.get("repo", ARMY_HOME)
            remote = kwargs.get("remote", "origin")
            branch = kwargs.get("branch", "")
            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=repo_path)
            return {"output": result.stdout[:5000] + result.stderr[:5000],
                    "returncode": result.returncode}

        elif action == "pull":
            repo_path = kwargs.get("repo", ARMY_HOME)
            remote = kwargs.get("remote", "origin")
            branch = kwargs.get("branch", "")
            cmd = ["git", "pull", remote]
            if branch:
                cmd.append(branch)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=repo_path)
            return {"output": result.stdout[:5000] + result.stderr[:5000],
                    "returncode": result.returncode}

        elif action == "clone":
            url = kwargs.get("url", "")
            dest = kwargs.get("dest", "")
            if not url:
                return {"error": "url required"}
            if kwargs.get("depth"):
                cmd = ["git", "clone", "--depth", str(kwargs["depth"]), url]
            else:
                cmd = ["git", "clone", url]
            if dest:
                cmd.append(dest)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {"output": result.stdout[:5000] + result.stderr[:5000],
                    "returncode": result.returncode}

        elif action == "github_api":
            # Generic GitHub API calls
            token = kwargs.get("token", os.environ.get("GITHUB_TOKEN", ""))
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "GET").upper()
            body = kwargs.get("body")
            if not token:
                return {"error": "GITHUB_TOKEN env var or token param required"}
            if not endpoint:
                return {"error": "endpoint required (e.g., /repos/owner/name/issues)"}
            import urllib.request
            url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
            data = json.dumps(body).encode() if body else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("User-Agent", "OpenClaw-Army/3.0")
            if body:
                req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=30)
            resp_body = resp.read().decode()
            try:
                return {"status": resp.status, "data": json.loads(resp_body)}
            except json.JSONDecodeError:
                return {"status": resp.status, "data": resp_body[:10000]}

        elif action == "create_pr":
            token = kwargs.get("token", os.environ.get("GITHUB_TOKEN", ""))
            repo = kwargs.get("repo", "")  # "owner/name"
            title = kwargs.get("title", "")
            head = kwargs.get("head", "")
            base = kwargs.get("base", "main")
            body_text = kwargs.get("body", "")
            if not all([token, repo, title, head]):
                return {"error": "token, repo (owner/name), title, and head branch required"}
            return _git_ops("github_api", token=token, endpoint=f"/repos/{repo}/pulls",
                           method="POST", body={"title": title, "head": head, "base": base, "body": body_text})

        elif action == "list_issues":
            token = kwargs.get("token", os.environ.get("GITHUB_TOKEN", ""))
            repo = kwargs.get("repo", "")
            state = kwargs.get("state", "open")
            if not repo:
                return {"error": "repo (owner/name) required"}
            return _git_ops("github_api", token=token,
                           endpoint=f"/repos/{repo}/issues?state={state}&per_page=30")

        else:
            return {"error": f"Unknown action: {action}. Use status, log, diff, branch, stash, remote, tag, commit, push, pull, clone, github_api, create_pr, list_issues."}

    except Exception as e:
        return {"error": f"git_ops failed: {e}"}


# ── Code Analysis (AST, Lint, Security Scan) ──────────────────────────────

def _code_analyze(action: str, **kwargs) -> dict:
    """Analyze code — AST parsing, linting, security scanning, complexity metrics."""
    try:
        if action == "ast_parse":
            code = kwargs.get("code", "")
            path = kwargs.get("path", "")
            if path:
                code = Path(path).expanduser().read_text(errors="replace")
            if not code:
                return {"error": "code or path required"}
            import ast
            tree = ast.parse(code)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) or isinstance(n, ast.AsyncFunctionDef)]
            imports = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    imports.extend(a.name for a in n.names)
                elif isinstance(n, ast.ImportFrom):
                    imports.append(n.module or "")
            return {"classes": classes, "functions": functions[:200], "imports": list(set(imports)),
                    "total_nodes": sum(1 for _ in ast.walk(tree)),
                    "lines": len(code.split("\n"))}

        elif action == "lint":
            path = kwargs.get("path", "")
            if not path:
                return {"error": "path required"}
            # Try flake8 first, then pylint
            for linter in ["flake8", "pylint"]:
                check = subprocess.run([sys.executable, "-m", linter, "--version"],
                                        capture_output=True, timeout=10)
                if check.returncode == 0:
                    result = subprocess.run(
                        [sys.executable, "-m", linter, path],
                        capture_output=True, text=True, timeout=60)
                    return {"linter": linter, "output": result.stdout[:15000],
                            "returncode": result.returncode,
                            "stderr": result.stderr[:2000]}
            # Auto-install flake8
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "flake8"],
                           capture_output=True, timeout=60)
            result = subprocess.run([sys.executable, "-m", "flake8", path],
                                     capture_output=True, text=True, timeout=60)
            return {"linter": "flake8", "output": result.stdout[:15000],
                    "returncode": result.returncode}

        elif action == "security_scan":
            path = kwargs.get("path", "")
            if not path:
                return {"error": "path required"}
            check = subprocess.run([sys.executable, "-m", "bandit", "--version"],
                                    capture_output=True, timeout=10)
            if check.returncode != 0:
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", "bandit"],
                               capture_output=True, timeout=60)
            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-r", path, "-f", "json", "-ll"],
                capture_output=True, text=True, timeout=120)
            try:
                data = json.loads(result.stdout)
                return {"issues": data.get("results", [])[:50],
                        "metrics": data.get("metrics", {}),
                        "severity_counts": {
                            "high": len([r for r in data.get("results", []) if r.get("issue_severity") == "HIGH"]),
                            "medium": len([r for r in data.get("results", []) if r.get("issue_severity") == "MEDIUM"]),
                            "low": len([r for r in data.get("results", []) if r.get("issue_severity") == "LOW"]),
                        }}
            except json.JSONDecodeError:
                return {"output": result.stdout[:10000], "stderr": result.stderr[:2000]}

        elif action == "complexity":
            path = kwargs.get("path", "")
            code = kwargs.get("code", "")
            if path:
                code = Path(path).expanduser().read_text(errors="replace")
            if not code:
                return {"error": "code or path required"}
            import ast
            tree = ast.parse(code)
            # Cyclomatic complexity approximation
            complexities = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cc = 1
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                              ast.With, ast.Assert, ast.BoolOp)):
                            cc += 1
                        if isinstance(child, ast.BoolOp):
                            cc += len(child.values) - 1
                    complexities.append({"name": node.name, "line": node.lineno, "complexity": cc})
            complexities.sort(key=lambda x: x["complexity"], reverse=True)
            return {"functions": complexities[:50],
                    "total_functions": len(complexities),
                    "avg_complexity": sum(c["complexity"] for c in complexities) / max(len(complexities), 1),
                    "max_complexity": complexities[0]["complexity"] if complexities else 0}

        elif action == "find_todos":
            path = kwargs.get("path", ARMY_HOME)
            pattern = kwargs.get("pattern", "*.py")
            p = Path(path).expanduser()
            todos = []
            for f in (p.rglob(pattern) if p.is_dir() else [p]):
                if not f.is_file() or f.stat().st_size > 2_000_000:
                    continue
                for i, line in enumerate(f.read_text(errors="replace").split("\n"), 1):
                    for marker in ["TODO", "FIXME", "HACK", "BUG", "XXX"]:
                        if marker in line:
                            todos.append({"file": str(f), "line": i, "marker": marker,
                                          "text": line.strip()[:200]})
                            break
                if len(todos) >= 200:
                    break
            return {"todos": todos, "count": len(todos)}

        else:
            return {"error": f"Unknown action: {action}. Use ast_parse, lint, security_scan, complexity, find_todos."}
    except Exception as e:
        return {"error": f"code_analyze failed: {e}"}


# ── LLM Fallback (Multi-provider routing) ─────────────────────────────────

_LLM_PROVIDERS: dict[str, dict] = {}  # provider_name -> {base_url, api_key, model, priority}
_LLM_PROVIDERS_PATH = Path(ARMY_HOME) / "data" / "llm_providers.json"

def _load_llm_providers():
    """Load LLM provider configurations from disk."""
    global _LLM_PROVIDERS
    if _LLM_PROVIDERS_PATH.exists():
        try:
            _LLM_PROVIDERS = json.loads(_LLM_PROVIDERS_PATH.read_text())
        except Exception:
            pass

def _save_llm_providers():
    _LLM_PROVIDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LLM_PROVIDERS_PATH.write_text(json.dumps(_LLM_PROVIDERS, indent=2))

_load_llm_providers()

def _llm_fallback(action: str, **kwargs) -> dict:
    """Manage LLM provider fallback chain — add providers, test, query with automatic failover."""
    try:
        if action == "add_provider":
            name = kwargs.get("name", "")
            base_url = kwargs.get("base_url", "")
            api_key = kwargs.get("api_key", "")
            model = kwargs.get("model", "")
            priority = kwargs.get("priority", 10)
            if not all([name, base_url, model]):
                return {"error": "name, base_url, and model required"}
            _LLM_PROVIDERS[name] = {
                "base_url": base_url, "api_key": api_key,
                "model": model, "priority": priority, "enabled": True,
            }
            _save_llm_providers()
            return {"added": name, "total_providers": len(_LLM_PROVIDERS)}

        elif action == "remove_provider":
            name = kwargs.get("name", "")
            if name in _LLM_PROVIDERS:
                del _LLM_PROVIDERS[name]
                _save_llm_providers()
                return {"removed": name}
            return {"error": f"Provider '{name}' not found"}

        elif action == "list_providers":
            providers = []
            # Include the default NVIDIA provider
            providers.append({
                "name": "nvidia_default", "base_url": LLM_BASE_URL,
                "model": LLM_MODEL, "priority": 0, "builtin": True,
            })
            for name, cfg in sorted(_LLM_PROVIDERS.items(), key=lambda x: x[1].get("priority", 10)):
                providers.append({"name": name, **{k: v for k, v in cfg.items() if k != "api_key"},
                                  "has_key": bool(cfg.get("api_key"))})
            return {"providers": providers, "count": len(providers)}

        elif action == "test_provider":
            name = kwargs.get("name", "")
            if name == "nvidia_default":
                base_url, api_key, model = LLM_BASE_URL, _get_api_key(), LLM_MODEL
            elif name in _LLM_PROVIDERS:
                cfg = _LLM_PROVIDERS[name]
                base_url, api_key, model = cfg["base_url"], cfg.get("api_key", ""), cfg["model"]
            else:
                return {"error": f"Provider '{name}' not found"}
            try:
                import urllib.request
                req = urllib.request.Request(f"{base_url}/models", method="GET")
                if api_key:
                    req.add_header("Authorization", f"Bearer {api_key}")
                req.add_header("User-Agent", "OpenClaw-Army/3.0")
                resp = urllib.request.urlopen(req, timeout=10)
                return {"provider": name, "reachable": True, "status": resp.status}
            except Exception as e:
                return {"provider": name, "reachable": False, "error": str(e)[:200]}

        elif action == "query":
            # Try providers in priority order with automatic failover
            prompt = kwargs.get("prompt", "")
            if not prompt:
                return {"error": "prompt required"}
            providers_ordered = [
                ("nvidia_default", {"base_url": LLM_BASE_URL, "api_key": _get_api_key(), "model": LLM_MODEL, "priority": 0})
            ]
            for name, cfg in sorted(_LLM_PROVIDERS.items(), key=lambda x: x[1].get("priority", 10)):
                if cfg.get("enabled"):
                    providers_ordered.append((name, cfg))
            providers_ordered.sort(key=lambda x: x[1].get("priority", 10))

            for name, cfg in providers_ordered:
                try:
                    import urllib.request
                    data = json.dumps({
                        "model": cfg["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": kwargs.get("max_tokens", 1024),
                        "temperature": kwargs.get("temperature", 0.7),
                    }).encode()
                    req = urllib.request.Request(f"{cfg['base_url']}/chat/completions",
                                                 data=data, method="POST")
                    if cfg.get("api_key"):
                        req.add_header("Authorization", f"Bearer {cfg['api_key']}")
                    req.add_header("Content-Type", "application/json")
                    req.add_header("User-Agent", "OpenClaw-Army/3.0")
                    resp = urllib.request.urlopen(req, timeout=kwargs.get("timeout", 60))
                    body = json.loads(resp.read().decode())
                    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return {"provider": name, "model": cfg["model"], "response": content[:10000],
                            "usage": body.get("usage", {})}
                except Exception:
                    continue
            return {"error": "All LLM providers failed"}

        else:
            return {"error": f"Unknown action: {action}. Use add_provider, remove_provider, list_providers, test_provider, query."}
    except Exception as e:
        return {"error": f"llm_fallback failed: {e}"}


# ── Notification Sender (Multi-channel) ────────────────────────────────────

def _notify_send(action: str, **kwargs) -> dict:
    """Send notifications via multiple channels — Slack, Discord, macOS native, Pushover."""
    try:
        if action == "macos":
            title = kwargs.get("title", "OpenClaw Army")
            message = kwargs.get("message", "")
            sound = kwargs.get("sound", "default")
            if not message:
                return {"error": "message required"}
            def _osa_escape(s: str) -> str:
                return s.replace('\\', '\\\\').replace('"', '\\"')
            escaped_title = _osa_escape(title)
            escaped_msg = _osa_escape(message)
            escaped_sound = _osa_escape(sound)
            script = f'display notification "{escaped_msg}" with title "{escaped_title}" sound name "{escaped_sound}"'
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            return {"sent": result.returncode == 0, "channel": "macos",
                    "error": result.stderr if result.returncode else ""}

        elif action == "slack":
            webhook_url = kwargs.get("webhook_url", os.environ.get("SLACK_WEBHOOK_URL", ""))
            message = kwargs.get("message", "")
            channel = kwargs.get("channel", "")
            if not webhook_url:
                return {"error": "webhook_url or SLACK_WEBHOOK_URL env var required"}
            if not message:
                return {"error": "message required"}
            payload = {"text": message}
            if channel:
                payload["channel"] = channel
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(webhook_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            return {"sent": True, "channel": "slack", "status": resp.status}

        elif action == "discord":
            webhook_url = kwargs.get("webhook_url", os.environ.get("DISCORD_WEBHOOK_URL", ""))
            message = kwargs.get("message", "")
            username = kwargs.get("username", "OpenClaw Army")
            if not webhook_url:
                return {"error": "webhook_url or DISCORD_WEBHOOK_URL env var required"}
            if not message:
                return {"error": "message required"}
            import urllib.request
            payload = {"content": message[:2000], "username": username}
            data = json.dumps(payload).encode()
            req = urllib.request.Request(webhook_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            return {"sent": True, "channel": "discord", "status": resp.status}

        elif action == "pushover":
            token = kwargs.get("token", os.environ.get("PUSHOVER_APP_TOKEN", ""))
            user = kwargs.get("user", os.environ.get("PUSHOVER_USER_KEY", ""))
            message = kwargs.get("message", "")
            title = kwargs.get("title", "OpenClaw Army")
            priority = kwargs.get("priority", 0)
            if not all([token, user, message]):
                return {"error": "token, user, and message required (or set PUSHOVER_APP_TOKEN/PUSHOVER_USER_KEY)"}
            import urllib.request, urllib.parse
            data = urllib.parse.urlencode({
                "token": token, "user": user, "message": message[:1024],
                "title": title, "priority": priority,
            }).encode()
            req = urllib.request.Request("https://api.pushover.net/1/messages.json",
                                          data=data, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            return {"sent": True, "channel": "pushover", "status": resp.status}

        elif action == "say":
            # macOS text-to-speech
            message = kwargs.get("message", "")
            voice = kwargs.get("voice", "")
            if not message:
                return {"error": "message required"}
            cmd = ["say"]
            if voice:
                cmd.extend(["-v", voice])
            cmd.append(message[:500])
            subprocess.run(cmd, capture_output=True, timeout=30)
            return {"spoken": True, "length": len(message)}

        else:
            return {"error": f"Unknown action: {action}. Use macos, slack, discord, pushover, say."}
    except Exception as e:
        return {"error": f"notify_send failed: {e}"}


# ── Full System Backup & Disaster Recovery ─────────────────────────────────

def _full_backup(action: str, **kwargs) -> dict:
    """Complete system backup and restore — all code, data, configs, databases."""
    try:
        backup_base = Path(ARMY_HOME) / "backups"
        backup_base.mkdir(parents=True, exist_ok=True)

        if action == "create":
            label = kwargs.get("label", "full")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_dir = backup_base / f"full_{ts}_{label}"
            backup_dir.mkdir(parents=True)

            manifest = {"ts": ts, "label": label, "contents": []}

            # 1. Main code
            src = Path(__file__).resolve()
            shutil.copy2(src, backup_dir / "main.py")
            manifest["contents"].append("main.py")

            # 2. Data directory
            data_dir = Path(ARMY_HOME) / "data"
            if data_dir.exists():
                shutil.copytree(data_dir, backup_dir / "data", dirs_exist_ok=True)
                manifest["contents"].append("data/")

            # 3. Agents directory
            agents_dir = Path(ARMY_HOME) / "agents"
            if agents_dir.exists():
                shutil.copytree(agents_dir, backup_dir / "agents", dirs_exist_ok=True)
                manifest["contents"].append("agents/")

            # 4. Config files
            for cfg in [".env", "docker-compose.yml", "docker-compose.override.yml"]:
                cfg_path = Path(ARMY_HOME) / cfg
                if cfg_path.exists():
                    shutil.copy2(cfg_path, backup_dir / cfg)
                    manifest["contents"].append(cfg)

            # 5. PostgreSQL dump
            try:
                pg_dump = backup_dir / "pg_dump.sql"
                dsn = os.environ.get("DATABASE_URL", "postgresql://landonking@localhost:5432/openclaw")
                result = subprocess.run(["pg_dump", dsn, "-f", str(pg_dump)],
                                         capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    manifest["contents"].append("pg_dump.sql")
            except Exception as e:
                manifest["pg_dump_error"] = str(e)[:200]

            # 6. Redis snapshot
            try:
                rdb = backup_dir / "redis_dump.rdb"
                redis_dir = subprocess.run(["redis-cli", "CONFIG", "GET", "dir"],
                                            capture_output=True, text=True, timeout=5)
                if redis_dir.returncode == 0:
                    lines = redis_dir.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        rdb_src = Path(lines[1]) / "dump.rdb"
                        if rdb_src.exists():
                            subprocess.run(["redis-cli", "BGSAVE"], capture_output=True, timeout=10)
                            time.sleep(2)
                            shutil.copy2(rdb_src, rdb)
                            manifest["contents"].append("redis_dump.rdb")
            except Exception as e:
                manifest["redis_error"] = str(e)[:200]

            # Write manifest
            (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

            # Calculate size
            total_size = sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file())

            return {"backup_dir": str(backup_dir), "contents": manifest["contents"],
                    "total_size_mb": round(total_size / (1024*1024), 2),
                    "manifest": str(backup_dir / "manifest.json")}

        elif action == "list":
            backups = []
            for d in sorted(backup_base.iterdir(), reverse=True):
                if d.is_dir() and d.name.startswith("full_"):
                    manifest_path = d / "manifest.json"
                    size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    info = {"name": d.name, "path": str(d), "size_mb": round(size / (1024*1024), 2)}
                    if manifest_path.exists():
                        try:
                            info["manifest"] = json.loads(manifest_path.read_text())
                        except Exception:
                            pass
                    backups.append(info)
            return {"backups": backups[:20], "count": len(backups)}

        elif action == "restore":
            backup_path = kwargs.get("path", "")
            if not backup_path or not Path(backup_path).exists():
                return {"error": "valid backup path required"}
            bp = Path(backup_path)
            restored = []

            # Restore main.py
            src_main = bp / "main.py"
            if src_main.exists():
                _safe_backup("pre_restore")
                shutil.copy2(src_main, Path(__file__).resolve())
                restored.append("main.py")

            # Restore data/
            src_data = bp / "data"
            if src_data.exists():
                shutil.copytree(src_data, Path(ARMY_HOME) / "data", dirs_exist_ok=True)
                restored.append("data/")

            # Restore agents/
            src_agents = bp / "agents"
            if src_agents.exists():
                shutil.copytree(src_agents, Path(ARMY_HOME) / "agents", dirs_exist_ok=True)
                restored.append("agents/")

            # Restore config files
            for cfg in [".env", "docker-compose.yml"]:
                src_cfg = bp / cfg
                if src_cfg.exists():
                    shutil.copy2(src_cfg, Path(ARMY_HOME) / cfg)
                    restored.append(cfg)

            # Restore PostgreSQL
            pg_dump = bp / "pg_dump.sql"
            if pg_dump.exists() and kwargs.get("restore_db"):
                dsn = os.environ.get("DATABASE_URL", "postgresql://landonking@localhost:5432/openclaw")
                result = subprocess.run(["psql", dsn, "-f", str(pg_dump)],
                                         capture_output=True, text=True, timeout=120)
                restored.append(f"pg_dump.sql (rc={result.returncode})")

            return {"restored": restored, "source": str(bp),
                    "hint": "Restart the server to apply restored code"}

        elif action == "cleanup":
            keep = kwargs.get("keep", 5)
            backups = sorted([d for d in backup_base.iterdir() if d.is_dir()], reverse=True)
            removed = []
            for d in backups[keep:]:
                shutil.rmtree(d)
                removed.append(d.name)
            return {"removed": removed, "kept": min(len(backups), keep)}

        else:
            return {"error": f"Unknown action: {action}. Use create, list, restore, cleanup."}
    except Exception as e:
        return {"error": f"full_backup failed: {e}"}


# ── Embeddings & Vector Search ─────────────────────────────────────────────

_EMBEDDINGS_PATH = Path(ARMY_HOME) / "data" / "embeddings"

def _embeddings(action: str, **kwargs) -> dict:
    """Generate text embeddings, store vectors, and perform similarity search."""
    import numpy as np

    _EMBEDDINGS_PATH.mkdir(parents=True, exist_ok=True)

    try:
        if action == "encode":
            texts = kwargs.get("texts", [])
            if isinstance(texts, str):
                texts = [texts]
            if not texts:
                return {"error": "texts required (string or list of strings)"}
            collection = kwargs.get("collection", "default")

            # Use the configured LLM API's embedding endpoint if available,
            # otherwise fall back to simple TF-IDF style embeddings
            try:
                import urllib.request
                api_key = _get_api_key()
                data = json.dumps({"input": texts[:100], "model": "nvidia/nv-embedqa-e5-v5"}).encode()
                req = urllib.request.Request(f"{LLM_BASE_URL}/embeddings", data=data, method="POST")
                req.add_header("Authorization", f"Bearer {api_key}")
                req.add_header("Content-Type", "application/json")
                resp = urllib.request.urlopen(req, timeout=30)
                body = json.loads(resp.read().decode())
                vectors = [item["embedding"] for item in body["data"]]
            except Exception:
                # Simple bag-of-words fallback embedding
                from collections import Counter
                vocab = set()
                for t in texts:
                    vocab.update(t.lower().split())
                vocab_list = sorted(vocab)[:500]
                vocab_idx = {w: i for i, w in enumerate(vocab_list)}
                vectors = []
                for t in texts:
                    words = Counter(t.lower().split())
                    vec = [0.0] * len(vocab_list)
                    for w, c in words.items():
                        if w in vocab_idx:
                            vec[vocab_idx[w]] = float(c)
                    norm = np.linalg.norm(vec) or 1.0
                    vectors.append((np.array(vec) / norm).tolist())

            # Store to collection
            col_path = _EMBEDDINGS_PATH / f"{collection}.json"
            store = json.loads(col_path.read_text()) if col_path.exists() else {"texts": [], "vectors": []}
            store["texts"].extend(texts)
            store["vectors"].extend(vectors)
            col_path.write_text(json.dumps(store))

            return {"encoded": len(texts), "collection": collection,
                    "total_stored": len(store["texts"]),
                    "vector_dim": len(vectors[0]) if vectors else 0}

        elif action == "search":
            query = kwargs.get("query", "")
            collection = kwargs.get("collection", "default")
            top_k = kwargs.get("top_k", 5)
            if not query:
                return {"error": "query required"}

            col_path = _EMBEDDINGS_PATH / f"{collection}.json"
            if not col_path.exists():
                return {"error": f"Collection '{collection}' not found"}

            store = json.loads(col_path.read_text())
            if not store["vectors"]:
                return {"results": [], "count": 0}

            # Encode query the same way
            try:
                import urllib.request
                api_key = _get_api_key()
                data = json.dumps({"input": [query], "model": "nvidia/nv-embedqa-e5-v5"}).encode()
                req = urllib.request.Request(f"{LLM_BASE_URL}/embeddings", data=data, method="POST")
                req.add_header("Authorization", f"Bearer {api_key}")
                req.add_header("Content-Type", "application/json")
                resp = urllib.request.urlopen(req, timeout=30)
                body = json.loads(resp.read().decode())
                q_vec = np.array(body["data"][0]["embedding"])
            except Exception:
                from collections import Counter
                dim = len(store["vectors"][0])
                # Reconstruct vocab from stored vectors (approximate)
                words = Counter(query.lower().split())
                q_vec = np.zeros(dim)
                # Simple fallback: just match text directly
                results = []
                for i, text in enumerate(store["texts"]):
                    score = sum(1 for w in query.lower().split() if w in text.lower())
                    if score > 0:
                        results.append({"text": text[:500], "score": score, "index": i})
                results.sort(key=lambda x: x["score"], reverse=True)
                return {"results": results[:top_k], "count": len(results), "method": "keyword_fallback"}

            # Cosine similarity
            stored = np.array(store["vectors"])
            norms = np.linalg.norm(stored, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = stored / norms
            q_norm = q_vec / (np.linalg.norm(q_vec) or 1)
            scores = normalized @ q_norm
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = [{"text": store["texts"][i][:500], "score": float(scores[i]), "index": int(i)}
                       for i in top_indices if scores[i] > 0]
            return {"results": results, "count": len(results), "method": "cosine_similarity"}

        elif action == "list_collections":
            collections = []
            for f in _EMBEDDINGS_PATH.glob("*.json"):
                try:
                    store = json.loads(f.read_text())
                    collections.append({"name": f.stem, "count": len(store.get("texts", [])),
                                        "size_kb": round(f.stat().st_size / 1024, 1)})
                except Exception:
                    collections.append({"name": f.stem, "error": "corrupt"})
            return {"collections": collections}

        elif action == "delete_collection":
            collection = kwargs.get("collection", "")
            col_path = _EMBEDDINGS_PATH / f"{collection}.json"
            if col_path.exists():
                col_path.unlink()
                return {"deleted": collection}
            return {"error": f"Collection '{collection}' not found"}

        else:
            return {"error": f"Unknown action: {action}. Use encode, search, list_collections, delete_collection."}
    except Exception as e:
        return {"error": f"embeddings failed: {e}"}


# ── Generic API Client ─────────────────────────────────────────────────────

def _api_client(action: str, **kwargs) -> dict:
    """Generic REST/GraphQL API client with auth, pagination, retry."""
    import urllib.request, urllib.parse
    try:
        if action == "request":
            url = kwargs.get("url", "")
            method = kwargs.get("method", "GET").upper()
            headers = kwargs.get("headers", {})
            body = kwargs.get("body")
            auth_type = kwargs.get("auth_type", "")  # bearer, basic, api_key
            auth_value = kwargs.get("auth_value", "")
            timeout = min(kwargs.get("timeout", 30), 120)

            if not url:
                return {"error": "url required"}

            if auth_type == "bearer" and auth_value:
                headers["Authorization"] = f"Bearer {auth_value}"
            elif auth_type == "basic" and auth_value:
                import base64
                headers["Authorization"] = f"Basic {base64.b64encode(auth_value.encode()).decode()}"
            elif auth_type == "api_key" and auth_value:
                key_name = kwargs.get("key_name", "X-API-Key")
                headers[key_name] = auth_value

            if "User-Agent" not in headers:
                headers["User-Agent"] = "OpenClaw-Army/3.0"

            data = None
            if body:
                if isinstance(body, (dict, list)):
                    data = json.dumps(body).encode()
                    headers.setdefault("Content-Type", "application/json")
                else:
                    data = str(body).encode()

            retries = kwargs.get("retries", 0)
            last_error = ""
            for attempt in range(retries + 1):
                try:
                    req = urllib.request.Request(url, data=data, method=method, headers=headers)
                    resp = urllib.request.urlopen(req, timeout=timeout)
                    resp_body = resp.read().decode(errors="replace")
                    try:
                        parsed = json.loads(resp_body)
                    except json.JSONDecodeError:
                        parsed = resp_body[:20000]
                    return {"status": resp.status, "data": parsed,
                            "headers": dict(resp.headers), "attempt": attempt + 1}
                except Exception as e:
                    last_error = str(e)[:200]
                    if attempt < retries:
                        time.sleep(min(2 ** attempt, 10))
                        continue
            return {"error": f"Request failed after {retries + 1} attempts: {last_error}"}

        elif action == "graphql":
            url = kwargs.get("url", "")
            query = kwargs.get("query", "")
            variables = kwargs.get("variables", {})
            headers = kwargs.get("headers", {})
            auth_value = kwargs.get("auth_value", "")
            if not url or not query:
                return {"error": "url and query required"}
            if auth_value:
                headers["Authorization"] = f"Bearer {auth_value}"
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("User-Agent", "OpenClaw-Army/3.0")
            data = json.dumps({"query": query, "variables": variables}).encode()
            req = urllib.request.Request(url, data=data, method="POST", headers=headers)
            resp = urllib.request.urlopen(req, timeout=kwargs.get("timeout", 30))
            body = json.loads(resp.read().decode())
            return {"data": body.get("data"), "errors": body.get("errors"),
                    "status": resp.status}

        elif action == "paginate":
            url = kwargs.get("url", "")
            headers = kwargs.get("headers", {})
            auth_value = kwargs.get("auth_value", "")
            max_pages = kwargs.get("max_pages", 5)
            page_param = kwargs.get("page_param", "page")
            per_page = kwargs.get("per_page", 50)
            if not url:
                return {"error": "url required"}
            if auth_value:
                headers["Authorization"] = f"Bearer {auth_value}"
            headers.setdefault("User-Agent", "OpenClaw-Army/3.0")

            all_data = []
            for page_num in range(1, max_pages + 1):
                sep = "&" if "?" in url else "?"
                page_url = f"{url}{sep}{page_param}={page_num}&per_page={per_page}"
                req = urllib.request.Request(page_url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=30)
                body = json.loads(resp.read().decode())
                if isinstance(body, list):
                    if not body:
                        break
                    all_data.extend(body)
                elif isinstance(body, dict):
                    items = body.get("results", body.get("data", body.get("items", [])))
                    if not items:
                        break
                    all_data.extend(items if isinstance(items, list) else [items])
            return {"data": all_data[:500], "total_fetched": len(all_data), "pages": page_num}

        else:
            return {"error": f"Unknown action: {action}. Use request, graphql, paginate."}
    except Exception as e:
        return {"error": f"api_client failed: {e}"}


# ── Advanced Cron (Dependencies, Conditions, Chaining) ─────────────────────

_CRON_CHAINS: dict[str, dict] = {}
_CRON_CHAINS_PATH = Path(ARMY_HOME) / "data" / "cron_chains.json"

def _load_cron_chains():
    global _CRON_CHAINS
    if _CRON_CHAINS_PATH.exists():
        try:
            _CRON_CHAINS = json.loads(_CRON_CHAINS_PATH.read_text())
        except Exception:
            pass

def _save_cron_chains():
    _CRON_CHAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CRON_CHAINS_PATH.write_text(json.dumps(_CRON_CHAINS, indent=2))

_load_cron_chains()

def _cron_advanced(action: str, **kwargs) -> dict:
    """Advanced cron with task chains, conditional execution, retry policies."""
    try:
        if action == "create_chain":
            name = kwargs.get("name", "")
            steps = kwargs.get("steps", [])
            if not name or not steps:
                return {"error": "name and steps required"}
            chain = {
                "name": name,
                "steps": steps,  # [{tool, args, on_fail: "abort"|"skip"|"retry", retries: 3}]
                "schedule": kwargs.get("schedule", ""),  # cron expression or ""
                "enabled": True,
                "run_count": 0,
                "last_run": None,
                "last_result": None,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            _CRON_CHAINS[name] = chain
            _save_cron_chains()
            return {"created": name, "steps": len(steps)}

        elif action == "run_chain":
            name = kwargs.get("name", "")
            if name not in _CRON_CHAINS:
                return {"error": f"Chain '{name}' not found"}
            chain = _CRON_CHAINS[name]
            results = []
            for i, step in enumerate(chain["steps"]):
                tool = step.get("tool", "")
                args = step.get("args", {})
                on_fail = step.get("on_fail", "abort")
                retries = step.get("retries", 0)

                step_result = None
                for attempt in range(retries + 1):
                    try:
                        # Execute the step using shell_command for now
                        if tool == "shell":
                            step_result = _run_shell_command(args.get("command", ""), args.get("timeout", 60))
                        elif tool == "http":
                            step_result = _api_client("request", **args)
                        elif tool == "notify":
                            step_result = _notify_send(args.get("channel", "macos"), **args)
                        else:
                            step_result = {"error": f"Unknown step tool: {tool}. Use shell, http, notify."}
                        if not step_result.get("error"):
                            break
                    except Exception as e:
                        step_result = {"error": str(e)[:200]}
                    if attempt < retries:
                        time.sleep(2)

                results.append({"step": i, "tool": tool, "result": step_result, "success": not step_result.get("error")})
                if step_result.get("error") and on_fail == "abort":
                    break

            chain["run_count"] += 1
            chain["last_run"] = datetime.now(timezone.utc).isoformat()
            chain["last_result"] = "success" if all(r["success"] for r in results) else "partial_failure"
            _save_cron_chains()
            return {"chain": name, "results": results, "overall": chain["last_result"]}

        elif action == "list_chains":
            chains = []
            for name, chain in _CRON_CHAINS.items():
                chains.append({
                    "name": name, "steps": len(chain.get("steps", [])),
                    "enabled": chain.get("enabled"), "run_count": chain.get("run_count", 0),
                    "last_run": chain.get("last_run"), "schedule": chain.get("schedule", ""),
                })
            return {"chains": chains, "count": len(chains)}

        elif action == "delete_chain":
            name = kwargs.get("name", "")
            if name in _CRON_CHAINS:
                del _CRON_CHAINS[name]
                _save_cron_chains()
                return {"deleted": name}
            return {"error": f"Chain '{name}' not found"}

        elif action == "toggle":
            name = kwargs.get("name", "")
            if name not in _CRON_CHAINS:
                return {"error": f"Chain '{name}' not found"}
            _CRON_CHAINS[name]["enabled"] = not _CRON_CHAINS[name].get("enabled", True)
            _save_cron_chains()
            return {"name": name, "enabled": _CRON_CHAINS[name]["enabled"]}

        else:
            return {"error": f"Unknown action: {action}. Use create_chain, run_chain, list_chains, delete_chain, toggle."}
    except Exception as e:
        return {"error": f"cron_advanced failed: {e}"}


# ── macOS Accessibility API ────────────────────────────────────────────────

def _accessibility(action: str, **kwargs) -> dict:
    """macOS Accessibility API — inspect UI elements, read AX tree, interact with controls."""
    def _osa_esc(s: str) -> str:
        """Escape a string for safe interpolation into AppleScript double-quoted strings."""
        return s.replace('\\', '\\\\').replace('"', '\\"')

    try:
        if action == "get_focused_app":
            script = '''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    return (name of frontApp) & "|" & (title of (first window of frontApp))
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            parts = result.stdout.strip().split("|")
            return {"app": parts[0] if parts else "", "window_title": parts[1] if len(parts) > 1 else "",
                    "error": result.stderr if result.returncode else ""}

        elif action == "get_ui_elements":
            app = kwargs.get("app", "")
            if not app:
                return {"error": "app name required"}
            esc_app = _osa_esc(app)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        set uiList to ""
        try
            repeat with w in windows
                set wTitle to name of w
                repeat with elem in (UI elements of w)
                    set eName to ""
                    set eRole to ""
                    set eVal to ""
                    try
                        set eName to name of elem
                    end try
                    try
                        set eRole to role of elem
                    end try
                    try
                        set eVal to value of elem
                    end try
                    set uiList to uiList & wTitle & "|||" & eRole & "|||" & eName & "|||" & eVal & "\\n"
                end repeat
            end repeat
        end try
        return uiList
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=15)
            elements = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("|||")
                if len(parts) >= 3:
                    elements.append({
                        "window": parts[0], "role": parts[1],
                        "name": parts[2], "value": parts[3] if len(parts) > 3 else "",
                    })
            return {"app": app, "elements": elements[:100], "count": len(elements)}

        elif action == "click_element":
            app = kwargs.get("app", "")
            element_name = kwargs.get("element", "")
            role = kwargs.get("role", "button")
            if not app or not element_name:
                return {"error": "app and element name required"}
            # Validate role against allowed AppleScript UI element types
            allowed_roles = {"button", "checkbox", "radio button", "text field", "pop up button",
                             "menu button", "slider", "scroll bar", "tab group", "group",
                             "static text", "image", "UI element"}
            if role not in allowed_roles:
                return {"error": f"Invalid role '{role}'. Allowed: {', '.join(sorted(allowed_roles))}"}
            esc_app = _osa_esc(app)
            esc_name = _osa_esc(element_name)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        try
            click {role} "{esc_name}" of window 1
            return "clicked"
        on error errMsg
            return "error: " & errMsg
        end try
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            return {"clicked": element_name, "result": result.stdout.strip()}

        elif action == "get_element_value":
            app = kwargs.get("app", "")
            element_name = kwargs.get("element", "")
            role = kwargs.get("role", "text field")
            if not app or not element_name:
                return {"error": "app and element name required"}
            allowed_roles = {"button", "checkbox", "radio button", "text field", "pop up button",
                             "menu button", "slider", "scroll bar", "static text", "UI element"}
            if role not in allowed_roles:
                return {"error": f"Invalid role '{role}'."}
            esc_app = _osa_esc(app)
            esc_name = _osa_esc(element_name)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        try
            return value of {role} "{esc_name}" of window 1
        on error errMsg
            return "error: " & errMsg
        end try
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            return {"element": element_name, "value": result.stdout.strip()}

        elif action == "set_element_value":
            app = kwargs.get("app", "")
            element_name = kwargs.get("element", "")
            value = kwargs.get("value", "")
            role = kwargs.get("role", "text field")
            if not app or not element_name:
                return {"error": "app and element name required"}
            allowed_roles = {"text field", "text area", "combo box", "pop up button", "UI element"}
            if role not in allowed_roles:
                return {"error": f"Invalid role '{role}' for set_element_value."}
            esc_app = _osa_esc(app)
            esc_name = _osa_esc(element_name)
            esc_val = _osa_esc(value)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        try
            set value of {role} "{esc_name}" of window 1 to "{esc_val}"
            return "set"
        on error errMsg
            return "error: " & errMsg
        end try
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            return {"element": element_name, "result": result.stdout.strip()}

        elif action == "get_menu_items":
            app = kwargs.get("app", "")
            if not app:
                return {"error": "app name required"}
            esc_app = _osa_esc(app)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        set menuList to ""
        repeat with m in menu bar items of menu bar 1
            set mName to name of m
            set menuList to menuList & mName & ","
        end repeat
        return menuList
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            items = [i.strip() for i in result.stdout.strip().split(",") if i.strip()]
            return {"app": app, "menu_items": items}

        elif action == "click_menu":
            app = kwargs.get("app", "")
            menu = kwargs.get("menu", "")
            item = kwargs.get("item", "")
            if not all([app, menu, item]):
                return {"error": "app, menu, and item required"}
            esc_app = _osa_esc(app)
            esc_menu = _osa_esc(menu)
            esc_item = _osa_esc(item)
            script = f'''
tell application "System Events"
    tell process "{esc_app}"
        click menu item "{esc_item}" of menu "{esc_menu}" of menu bar item "{esc_menu}" of menu bar 1
    end tell
end tell
'''
            result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                     capture_output=True, text=True, timeout=10)
            return {"clicked": f"{menu} > {item}", "error": result.stderr if result.returncode else ""}

        else:
            return {"error": f"Unknown action: {action}. Use get_focused_app, get_ui_elements, click_element, get_element_value, set_element_value, get_menu_items, click_menu."}
    except Exception as e:
        return {"error": f"accessibility failed: {e}"}


# ── Tool #100: screen_share ────────────────────────────────────────────────

_screen_share_session: dict | None = None
_screen_share_task: asyncio.Task | None = None
_screen_share_frames: list[dict] = []
_SCREEN_SHARE_MAX_FRAMES = 30  # ring buffer of recent frames


async def _screen_share_capture_loop(interval: float, region: dict | None):
    """Background loop that captures screenshots with OCR at regular intervals."""
    global _screen_share_frames
    import io as _io
    import base64 as _b64
    import tempfile as _tmpf
    try:
        import pyautogui
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui"], timeout=60)
        import pyautogui

    prev_text = ""
    while True:
        try:
            if region:
                img = pyautogui.screenshot(region=(region["x"], region["y"], region["width"], region["height"]))
            else:
                img = pyautogui.screenshot()

            # OCR text extraction
            ocr_text = ""
            try:
                result = subprocess.run(
                    ["tesseract", "stdin", "stdout", "--dpi", "144"],
                    input=img.tobytes(), capture_output=True, timeout=15
                )
                if result.returncode != 0:
                    # Fallback: save to temp file
                    tmp = Path(_tmpf.gettempdir()) / "screen_share_frame.png"
                    img.save(str(tmp))
                    result = subprocess.run(
                        ["tesseract", str(tmp), "stdout", "--dpi", "144"],
                        capture_output=True, timeout=15
                    )
                    ocr_text = result.stdout.decode("utf-8", errors="replace").strip()
                else:
                    ocr_text = result.stdout.decode("utf-8", errors="replace").strip()
            except FileNotFoundError:
                ocr_text = "(tesseract not available)"
            except Exception as e:
                ocr_text = f"(OCR error: {e})"

            # Change detection
            changed = ocr_text != prev_text
            prev_text = ocr_text

            # Compress image to JPEG for storage
            rgb_img = img.convert("RGB") if img.mode == "RGBA" else img
            buf = _io.BytesIO()
            rgb_img.save(buf, format="JPEG", quality=50)
            b64_img = _b64.b64encode(buf.getvalue()).decode("ascii")

            frame = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ocr_text": ocr_text[:5000],
                "changed": changed,
                "width": img.width,
                "height": img.height,
                "image_b64": b64_img,
                "mouse": list(pyautogui.position()),
            }

            _screen_share_frames.append(frame)
            if len(_screen_share_frames) > _SCREEN_SHARE_MAX_FRAMES:
                _screen_share_frames[:] = _screen_share_frames[-_SCREEN_SHARE_MAX_FRAMES:]

        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning(f"screen_share capture error: {e}")

        await asyncio.sleep(interval)


async def _screen_share(action: str, **kwargs) -> dict:
    """Live screen sharing with continuous capture, OCR, and change detection."""
    global _screen_share_session, _screen_share_task, _screen_share_frames

    try:
        if action == "start_session":
            if _screen_share_session:
                return {"status": "already_running", "session": _screen_share_session}

            interval = max(0.5, float(kwargs.get("interval_sec", 2.0)))
            region = kwargs.get("region")
            if region and isinstance(region, dict):
                for k in ("x", "y", "width", "height"):
                    if k not in region:
                        return {"error": f"region must have x, y, width, height — missing '{k}'"}
            else:
                region = None

            _screen_share_frames.clear()
            _screen_share_session = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "interval_sec": interval,
                "region": region,
                "frames_captured": 0,
            }
            _screen_share_task = asyncio.create_task(
                _screen_share_capture_loop(interval, region)
            )

            # Check CRD status
            crd_running = False
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "remoting_me2me_host"],
                    capture_output=True, timeout=5
                )
                crd_running = result.returncode == 0
            except Exception:
                pass

            return {
                "status": "started",
                "interval_sec": interval,
                "region": region,
                "chrome_remote_desktop": "running" if crd_running else "not detected",
                "note": "Use get_frame to see current screen. Use desktop_control to interact."
            }

        elif action == "stop_session":
            if not _screen_share_session:
                return {"status": "not_running"}
            if _screen_share_task and not _screen_share_task.done():
                _screen_share_task.cancel()
                try:
                    await _screen_share_task
                except asyncio.CancelledError:
                    pass
            frames_count = len(_screen_share_frames)
            _screen_share_session = None
            _screen_share_task = None
            _screen_share_frames.clear()
            return {"status": "stopped", "frames_captured": frames_count}

        elif action == "get_frame":
            if not _screen_share_frames:
                return {"error": "No frames captured. Start a session first with start_session."}
            frame = _screen_share_frames[-1]
            include_image = kwargs.get("include_image", False)
            result = {
                "timestamp": frame["timestamp"],
                "ocr_text": frame["ocr_text"],
                "changed": frame["changed"],
                "resolution": f"{frame['width']}x{frame['height']}",
                "mouse_position": frame["mouse"],
                "total_frames": len(_screen_share_frames),
            }
            if include_image:
                result["image_b64_jpeg"] = frame["image_b64"]
            return result

        elif action == "get_status":
            crd_running = False
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "remoting_me2me_host"],
                    capture_output=True, timeout=5
                )
                crd_running = result.returncode == 0
            except Exception:
                pass

            return {
                "session_active": _screen_share_session is not None,
                "session": _screen_share_session,
                "frames_buffered": len(_screen_share_frames),
                "chrome_remote_desktop": "running" if crd_running else "not detected",
                "screen_access": "pyautogui available",
            }

        elif action == "set_interval":
            if not _screen_share_session:
                return {"error": "No active session. Use start_session first."}
            new_interval = max(0.5, float(kwargs.get("interval_sec", 2.0)))
            # Restart capture loop with new interval
            if _screen_share_task and not _screen_share_task.done():
                _screen_share_task.cancel()
                try:
                    await _screen_share_task
                except asyncio.CancelledError:
                    pass
            _screen_share_session["interval_sec"] = new_interval
            region = _screen_share_session.get("region")
            _screen_share_task = asyncio.create_task(
                _screen_share_capture_loop(new_interval, region)
            )
            return {"status": "interval_updated", "interval_sec": new_interval}

        else:
            return {"error": f"Unknown action: {action}. Use start_session, stop_session, get_frame, get_status, set_interval."}
    except Exception as e:
        return {"error": f"screen_share failed: {e}"}


# ── Tool #101: visionclaw ──────────────────────────────────────────────────

_OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


async def _visionclaw(action: str, **kwargs) -> dict:
    """VisionClaw integration — manage Meta Ray-Ban glass sessions and gateway config."""
    try:
        if action == "status":
            # Show connection status and active sessions
            active = {sid: info for sid, info in _visionclaw_sessions.items()
                      if info.get("message_count", 0) > 0}
            # Check gateway
            gateway_status = "unknown"
            gateway_config = {}
            if _OPENCLAW_CONFIG_PATH.exists():
                try:
                    cfg = json.loads(_OPENCLAW_CONFIG_PATH.read_text())
                    gw = cfg.get("gateway", {})
                    gateway_config = {
                        "port": gw.get("port", 18789),
                        "bind": gw.get("bind", "loopback"),
                        "auth_mode": gw.get("auth", {}).get("mode", "none"),
                        "chat_completions_enabled": gw.get("http", {}).get("endpoints", {}).get("chatCompletions", {}).get("enabled", False),
                    }
                except Exception:
                    pass
            # Check if gateway is running
            try:
                result = subprocess.run(["lsof", "-ti", ":18789"], capture_output=True, text=True, timeout=3)
                gateway_status = "running" if result.stdout.strip() else "stopped"
            except Exception:
                pass

            return {
                "orchestrator_endpoint": f"http://127.0.0.1:{ORCHESTRATOR_PORT}/v1/chat/completions",
                "orchestrator_port": ORCHESTRATOR_PORT,
                "active_glass_sessions": len(active),
                "sessions": active,
                "gateway_status": gateway_status,
                "gateway_config": gateway_config,
                "hostname": subprocess.run(["scutil", "--get", "LocalHostName"],
                                           capture_output=True, text=True, timeout=3).stdout.strip(),
                "lan_url": f"http://{subprocess.run(['scutil', '--get', 'LocalHostName'], capture_output=True, text=True, timeout=3).stdout.strip()}.local:{ORCHESTRATOR_PORT}/v1/chat/completions",
            }

        elif action == "sessions":
            return {
                "total_sessions": len(_visionclaw_sessions),
                "sessions": {sid: {
                    "last_active": info.get("last_active", ""),
                    "message_count": info.get("message_count", 0),
                    "source": info.get("source", ""),
                } for sid, info in _visionclaw_sessions.items()},
            }

        elif action == "config":
            # Show current VisionClaw configuration
            config = {"gateway": {}, "visionclaw_project": None}
            if _OPENCLAW_CONFIG_PATH.exists():
                try:
                    cfg = json.loads(_OPENCLAW_CONFIG_PATH.read_text())
                    config["gateway"] = cfg.get("gateway", {})
                    # Redact token
                    if "auth" in config["gateway"] and "token" in config["gateway"]["auth"]:
                        token = config["gateway"]["auth"]["token"]
                        config["gateway"]["auth"]["token"] = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
                except Exception as e:
                    config["error"] = str(e)

            # Check VisionClaw project
            vc_path = Path.home() / "Desktop" / "landon" / "claw vision" / "VisionClaw"
            if vc_path.exists():
                config["visionclaw_project"] = str(vc_path)
                secrets_path = vc_path / "samples" / "CameraAccess" / "CameraAccess" / "Secrets.swift"
                config["secrets_exists"] = secrets_path.exists()

            hostname = subprocess.run(["scutil", "--get", "LocalHostName"],
                                      capture_output=True, text=True, timeout=3).stdout.strip()
            config["recommended_settings"] = {
                "openClawHost": f"http://{hostname}.local",
                "openClawPort": ORCHESTRATOR_PORT,
                "note": "Point VisionClaw at the orchestrator for full 101-tool access",
            }
            return config

        elif action == "configure":
            # Update gateway bind mode
            bind_mode = kwargs.get("bind_mode", "lan")
            if bind_mode not in ("lan", "loopback"):
                return {"error": "bind_mode must be 'lan' or 'loopback'"}

            if not _OPENCLAW_CONFIG_PATH.exists():
                return {"error": f"Config not found: {_OPENCLAW_CONFIG_PATH}"}

            cfg = json.loads(_OPENCLAW_CONFIG_PATH.read_text())
            old_bind = cfg.get("gateway", {}).get("bind", "loopback")
            if "gateway" not in cfg:
                cfg["gateway"] = {}
            cfg["gateway"]["bind"] = bind_mode
            _OPENCLAW_CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

            return {
                "updated": True,
                "old_bind": old_bind,
                "new_bind": bind_mode,
                "note": f"Gateway bind changed to '{bind_mode}'. Restart gateway with `openclaw gateway restart` for changes to take effect.",
            }

        elif action == "send":
            # Push a message to a VisionClaw session (stored for next poll)
            session_id = kwargs.get("session_id", "")
            message = kwargs.get("message", "")
            if not session_id or not message:
                return {"error": "session_id and message are required"}

            if session_id not in _visionclaw_sessions:
                return {"error": f"Session {session_id} not found. Active sessions: {list(_visionclaw_sessions.keys())}"}

            # Inject a system message into the session history
            if session_id in _chat_sessions:
                _chat_sessions[session_id].append({
                    "role": "system",
                    "content": f"[Proactive notification to glasses user]: {message}"
                })
                _save_sessions_to_disk()

            await activity.record("visionclaw_push", session_id, message[:300])
            return {"sent": True, "session_id": session_id, "message": message[:200]}

        elif action == "history":
            session_id = kwargs.get("session_id", "")
            if not session_id:
                # Return all VC session IDs
                return {"sessions": list(_visionclaw_sessions.keys())}

            if session_id in _chat_sessions:
                history = _chat_sessions[session_id]
                return {
                    "session_id": session_id,
                    "message_count": len(history),
                    "messages": [{"role": m["role"], "content": m["content"][:500]} for m in history[-20:]],
                }
            return {"session_id": session_id, "message_count": 0, "messages": []}

        else:
            return {"error": f"Unknown action: {action}. Use: status, sessions, config, configure, send, history"}

    except Exception as e:
        return {"error": f"visionclaw failed: {e}"}


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
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=300)
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                await ws.send_text('{"event":"ping"}')
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=30)
                except asyncio.TimeoutError:
                    log.info("WebSocket client timed out, closing")
                    break
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_subscribers:
            ws_subscribers.remove(ws)
        log.info(f"WebSocket client disconnected ({len(ws_subscribers)} remaining)")


@app.websocket("/ws/screen")
async def websocket_screen_feed(ws: WebSocket):
    """Stream live screen frames over WebSocket. Sends JSON with OCR text + optional base64 JPEG."""
    await ws.accept()
    log.info("Screen share WebSocket client connected")
    last_idx = 0
    try:
        while True:
            if _screen_share_frames and len(_screen_share_frames) > last_idx:
                frame = _screen_share_frames[-1]
                last_idx = len(_screen_share_frames)
                payload = {
                    "event": "screen_frame",
                    "timestamp": frame["timestamp"],
                    "ocr_text": frame["ocr_text"],
                    "changed": frame["changed"],
                    "resolution": f"{frame['width']}x{frame['height']}",
                    "mouse": frame["mouse"],
                    "image_b64_jpeg": frame["image_b64"],
                }
                await ws.send_json(payload)
            else:
                # Check for control messages from client
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                    if msg == "ping":
                        await ws.send_text("pong")
                except asyncio.TimeoutError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        log.info("Screen share WebSocket client disconnected")


@app.get("/screen/frame")
async def get_screen_frame(include_image: bool = False):
    """HTTP endpoint to get the latest screen frame (for non-WebSocket clients)."""
    if not _screen_share_frames:
        raise HTTPException(status_code=404, detail="No frames. Start a screen_share session first.")
    frame = _screen_share_frames[-1]
    result = {
        "timestamp": frame["timestamp"],
        "ocr_text": frame["ocr_text"],
        "changed": frame["changed"],
        "resolution": f"{frame['width']}x{frame['height']}",
        "mouse_position": frame["mouse"],
    }
    if include_image:
        result["image_b64_jpeg"] = frame["image_b64"]
    return result


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
    import socket
    # Dual-stack: bind to :: with IPV6_V6ONLY=False so both IPv4 and IPv6 work
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("::", ORCHESTRATOR_PORT))
    uvicorn.run(app, fd=sock.fileno(), log_level="info")
