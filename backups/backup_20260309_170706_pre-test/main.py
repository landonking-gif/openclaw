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
- **run_shell_command**: Execute shell commands directly on this Mac. Use for: uptime, file operations, running scripts, checking processes, system info, etc. This is YOUR capability — you don't need to delegate to any manager for shell commands.
- **http_fetch**: Make HTTP requests directly — fetch APIs, check web pages, download data. You CAN access the internet through this tool directly.
- **install_package**: Install any Python package via pip. Need a social media library? `install_package("tweepy")`. Need a database driver? `install_package("chromadb")`. Need web scraping? `install_package("selenium")`. This is how you acquire NEW capabilities instantly.
- **restart_self**: Restart your process to apply code changes. Automatically sources .env so all API keys persist. Use after modify_own_code when needed.
- **git_command**: Full git access in the project directory. Commit changes, create branches, view history, push/pull. Use this to version-control your own evolution.
- **create_backup**: Create timestamped backups of data/, main.py, and .env before risky operations.
- **setup_launchd**: Install/manage a macOS launchd plist so the orchestrator auto-starts on boot and auto-restarts on crash. Actions: 'install', 'uninstall', 'status'.

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
You are a self-evolving system. If you encounter something you cannot currently do, you have the tools to give yourself that capability:
- Need to post to Twitter/X? → install_package("tweepy"), then register_new_tool with a Twitter posting handler.
- Need to send SMS? → install_package("twilio"), then register_new_tool with an SMS handler.
- Need a vector database? → install_package("chromadb"), then register_new_tool with vector search.
- Need to browse the web interactively? → install_package("selenium") + install_package("webdriver-manager"), then build a browsing tool.
- Need to process images/audio/video? → install_package("Pillow") / install_package("pydub") / install_package("moviepy").
- Need to interact with any API? → install_package the SDK, then register_new_tool.
- Need push notifications? → install_package("pushover") or build a webhook tool.
- Need to schedule recurring tasks? → Use setup_launchd or register a cron-like tool.
- The ONLY hard limits are: physical hardware access (no camera/microphone) and rate limits from external APIs.
- Everything else is achievable through self-modification. ACT on gaps — don't just report them.

OPERATIONAL NOTES:
- Email sending depends on SMTP credentials in the Notification Service.
- macOS automation requires proper system permissions.
- You CAN access the internet via http_fetch and run_shell_command (curl).
- You CAN install any Python library and immediately use it in register_new_tool.
- You CAN version-control your own changes with git_command.
- You CAN set yourself up to auto-start with setup_launchd.
- You CAN create backups before risky operations with create_backup.

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
            "description": "Fetch a URL and return the response. Use this to access APIs, check web pages, download data, etc. Supports GET and POST methods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                    "method": {"type": "string", "description": "HTTP method: GET or POST. Default GET.", "default": "GET"},
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
    "register_new_tool", "register_new_agent",
    "update_system_prompt", "remove_prompt_section",
    "check_quality", "view_modification_history",
    "read_own_code", "run_shell_command", "http_fetch",
    "install_package", "restart_self", "git_command",
    "create_backup", "setup_launchd",
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
    MAX_TOOL_TURNS = 5           # safety cap (most tasks complete in 2-3 turns)
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
    if method not in ("GET", "POST"):
        return {"error": f"Unsupported method: {method}", "status": 0, "body": ""}

    req_headers = headers or {}
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "OpenClaw-Army/3.0"

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            kwargs = {"headers": req_headers}
            if method == "POST" and body:
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
        "logging": logging,
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
    await activity.record("system", "", "Orchestrator started",
                          {"port": ORCHESTRATOR_PORT,
                           "agents": len(AGENT_PORTS),
                           "manifests": len(_manifest_cache)})
    asyncio.create_task(_health_watchdog())


# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT, log_level="info")
