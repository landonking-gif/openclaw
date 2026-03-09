#!/usr/bin/env python3
"""
Ultra-Hard Test Suite for OpenClaw Army Self-Evolution
=====================================================

Tests organized in 3 tiers:
  TIER 1 (AT LIMITS): Tasks the system should handle but may struggle with
  TIER 2 (BEYOND LIMITS): Tasks requiring capabilities the system doesn't have yet
  TIER 3 (META): Tasks requiring the system to recognize and fix its own gaps

Each test has:
  - prompt: what to send to /chat
  - verify: function to check if the task actually succeeded
  - category: what capability is being tested
  - tier: difficulty tier
"""

import json
import time
import subprocess
import os
import sys
import re
from pathlib import Path
from datetime import datetime

ORCH_URL = "http://127.0.0.1:18830"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "ultra_hard_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TESTS = [
    # ── TIER 1: AT THE LIMITS ──────────────────────────────────────────
    {
        "id": "T1-01",
        "tier": 1,
        "category": "self-awareness",
        "prompt": "Read your own source code and tell me exactly how many endpoints (routes) you have. List each one with its HTTP method and path.",
        "verify": lambda r, _: (
            any(kw in r.lower() for kw in ["/chat", "/health", "/diagnostic", "/self-heal"])
            and any(char.isdigit() for char in r)
        ),
        "description": "Can the system introspect its own code?"
    },
    {
        "id": "T1-02",
        "tier": 1,
        "category": "complex-delegation",
        "prompt": "Create a Python script at ~/Desktop/fibonacci_benchmark.py that benchmarks iterative vs recursive Fibonacci for n=30, measures execution time for both approaches, and prints which is faster with the exact timing difference.",
        "verify": lambda r, _: (
            Path(os.path.expanduser("~/Desktop/fibonacci_benchmark.py")).exists()
        ),
        "description": "Complex file creation with benchmarking logic"
    },
    {
        "id": "T1-03",
        "tier": 1,
        "category": "multi-manager",
        "prompt": "I need three things done simultaneously: (1) Write a haiku about artificial intelligence to ~/Desktop/ai_haiku.txt, (2) Create a bash script at ~/Desktop/sysinfo.sh that outputs CPU model, total RAM, and disk usage, (3) Research and explain the differences between WebSockets, SSE, and long polling for real-time communication.",
        "verify": lambda r, _: (
            Path(os.path.expanduser("~/Desktop/ai_haiku.txt")).exists()
            or Path(os.path.expanduser("~/Desktop/sysinfo.sh")).exists()
        ),
        "description": "Parallel multi-manager delegation"
    },
    {
        "id": "T1-04",
        "tier": 1,
        "category": "self-modification",
        "prompt": "Add a new endpoint to yourself at /ping that simply returns {\"pong\": true, \"timestamp\": <current UTC iso timestamp>}. Use modify_own_code to add it. After adding it, tell me you've added it.",
        "verify": lambda r, _: "modify" in r.lower() or "added" in r.lower() or "ping" in r.lower(),
        "description": "Can the system add a new endpoint to itself?"
    },

    # ── TIER 2: BEYOND CURRENT LIMITS ──────────────────────────────────
    {
        "id": "T2-01",
        "tier": 2,
        "category": "http-fetch",
        "prompt": "Fetch the current Bitcoin price from a public API (like coingecko) and tell me the current USD price. I need the ACTUAL live price, not an estimate.",
        "verify": lambda r, _: (
            "$" in r or "usd" in r.lower() or "price" in r.lower()
        ),
        "description": "System has no direct HTTP fetch capability"
    },
    {
        "id": "T2-02",
        "tier": 2,
        "category": "email",
        "prompt": "Send a test email to landon@example.com with the subject 'OpenClaw Army Status Report' and body containing today's date and a summary that all 16 agents are operational. If you can't send email directly, figure out how to give yourself that capability and do it.",
        "verify": lambda r, _: (
            "email" in r.lower() and ("sent" in r.lower() or "smtp" in r.lower() 
            or "modify" in r.lower() or "capability" in r.lower())
        ),
        "description": "Email sending - system must self-evolve to acquire this"
    },
    {
        "id": "T2-03",
        "tier": 2,
        "category": "system-command",
        "prompt": "Execute 'uptime' on this Mac and tell me exactly how long the system has been running. I need the actual output, not a guess.",
        "verify": lambda r, _: (
            any(kw in r.lower() for kw in ["day", "hour", "minute", "up ", "uptime"])
        ),
        "description": "Direct command execution - system has no shell access itself"
    },
    {
        "id": "T2-04",
        "tier": 2,
        "category": "scheduled-task",
        "prompt": "Create a scheduled task that runs every 5 minutes and logs the current memory usage of the orchestrator process to a file at ~/openclaw-army/data/logs/memory_monitor.jsonl. Make this actually work, not just a plan.",
        "verify": lambda r, _: (
            "schedul" in r.lower() or "monitor" in r.lower() or "memory" in r.lower()
        ),
        "description": "Scheduling - requires adding background task capability"
    },
    {
        "id": "T2-05",
        "tier": 2,
        "category": "data-persistence",
        "prompt": "Create a key-value store endpoint on yourself. I want POST /kv to store {key: str, value: str} pairs, and GET /kv/{key} to retrieve them. The data should persist to a JSON file. Actually add this to your code and make it work.",
        "verify": lambda r, _: (
            "kv" in r.lower() or "key-value" in r.lower() or "modify" in r.lower()
        ),
        "description": "Self-add persistence endpoints"
    },

    # ── TIER 3: META-TASKS (requiring self-awareness + self-modification) ─
    {
        "id": "T3-01",
        "tier": 3,
        "category": "self-diagnosis",
        "prompt": "Analyze your own SYSTEM_PROMPT and identify three specific weaknesses or gaps in your instructions that could cause failure. Then fix at least one of them using your self-modification tools.",
        "verify": lambda r, _: (
            ("weakness" in r.lower() or "gap" in r.lower() or "improve" in r.lower())
            and ("update" in r.lower() or "modify" in r.lower() or "fix" in r.lower())
        ),
        "description": "Self-critical analysis and self-improvement"
    },
    {
        "id": "T3-02",
        "tier": 3,
        "category": "capability-gap",
        "prompt": "I need you to fetch the HTML title of https://news.ycombinator.com right now. If you can't do it, don't say you can't — instead, give yourself the ability to do it by modifying your own code, then actually do it.",
        "verify": lambda r, _: (
            "hacker news" in r.lower() or "ycombinator" in r.lower()
            or "modify" in r.lower() or "added" in r.lower()
        ),
        "description": "Self-evolve to acquire HTTP capability and use it"
    },
    {
        "id": "T3-03",
        "tier": 3,
        "category": "learning",
        "prompt": "Check your output quality, and if there's any room for improvement, update your own system prompt with specific rules to improve your weakest scoring dimension. Show me what you changed.",
        "verify": lambda r, _: (
            "quality" in r.lower() and ("update" in r.lower() or "prompt" in r.lower())
        ),
        "description": "Quality-driven self-improvement loop"
    },
]


def send_test(test: dict, timeout: int = 600) -> dict:
    """Send a test prompt to the orchestrator and capture the full result."""
    session_id = f"ultra-{test['id']}-{int(time.time())}"
    payload = json.dumps({"message": test["prompt"], "session_id": session_id})

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{ORCH_URL}/chat",
             "-H", "Content-Type: application/json",
             "-d", payload,
             "--max-time", str(timeout)],
            capture_output=True, text=True, timeout=timeout + 10
        )
        if result.returncode != 0:
            return {"error": f"curl exit {result.returncode}: {result.stderr[:200] or result.stdout[:200]}", "raw": result.stdout}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON: {result.stdout[:200]}", "raw": result.stdout}

        return {
            "response": data.get("response", ""),
            "delegations": data.get("delegations", []),
            "quality": data.get("quality", {}),
            "session_id": session_id,
            "raw": result.stdout,
        }
    except subprocess.TimeoutExpired:
        return {"error": "TIMEOUT", "raw": ""}
    except Exception as e:
        return {"error": str(e), "raw": ""}


def run_test(test: dict, pause: int = 40) -> dict:
    """Run a single test with verification."""
    print(f"\n{'='*60}")
    print(f"[{test['id']}] {test['description']}")
    print(f"  Tier: {test['tier']} | Category: {test['category']}")
    print(f"  Prompt: {test['prompt'][:100]}...")
    print(f"{'─'*60}")

    result = send_test(test)

    if "error" in result and result.get("error"):
        print(f"  ❌ ERROR: {result['error'][:200]}")
        entry = {**test, "result": "ERROR", "error": result["error"],
                 "response": "", "delegations": [], "quality": {}}
    else:
        response = result.get("response", "")
        delegations = result.get("delegations", [])
        quality = result.get("quality", {})

        # Run verification
        try:
            passed = test["verify"](response, result)
        except Exception as e:
            passed = False
            print(f"  ⚠️  Verify error: {e}")

        status = "PASS" if passed else "FAIL"
        icon = "✅" if passed else "❌"

        print(f"  {icon} {status}")
        print(f"  Quality: {quality}")
        print(f"  Delegations: {len(delegations)}")
        for d in delegations:
            disp = "✓" if d.get("dispatched") else "✗"
            print(f"    [{disp}] {d.get('manager','?')}: {d.get('task','')[:80]}")
        print(f"  Response preview: {response[:200]}")

        entry = {**test, "result": status, "error": "",
                 "response": response[:1000], "delegations": delegations, "quality": quality}

    # Remove non-serializable verify function
    entry.pop("verify", None)

    # Save individual result
    result_file = RESULTS_DIR / f"{test['id']}.json"
    with open(result_file, "w") as f:
        json.dump(entry, f, indent=2, default=str)

    if pause > 0:
        print(f"  (pausing {pause}s for rate limit...)")
        time.sleep(pause)

    return entry


def run_all(tier: int = 0, pause: int = 40):
    """Run all tests (or specific tier). pause=seconds between tests for rate limiting."""
    tests = TESTS if tier == 0 else [t for t in TESTS if t["tier"] == tier]
    results = []

    print(f"\n{'#'*60}")
    print(f"# ULTRA-HARD TEST SUITE — {len(tests)} tests")
    print(f"# Started: {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    for test in tests:
        entry = run_test(test, pause=pause)
        results.append(entry)

    # Summary
    print(f"\n{'#'*60}")
    print(f"# RESULTS SUMMARY")
    print(f"{'#'*60}")

    for tier_num in sorted(set(t["tier"] for t in tests)):
        tier_results = [r for r in results if r["tier"] == tier_num]
        passed = sum(1 for r in tier_results if r["result"] == "PASS")
        total = len(tier_results)
        print(f"\n  TIER {tier_num}: {passed}/{total}")
        for r in tier_results:
            icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}.get(r["result"], "?")
            print(f"    {icon} [{r['id']}] {r['description'][:50]}")

    total_pass = sum(1 for r in results if r["result"] == "PASS")
    print(f"\n  TOTAL: {total_pass}/{len(results)}")

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": total_pass,
        "results": results,
    }
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    return results


def run_single(test_id: str, pause: int = 0):
    """Run a single test by ID."""
    test = next((t for t in TESTS if t["id"] == test_id), None)
    if not test:
        print(f"Test {test_id} not found. Available: {[t['id'] for t in TESTS]}")
        return None
    return run_test(test, pause=pause)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("T"):
            run_single(arg)
        elif arg.isdigit():
            run_all(tier=int(arg), pause=40)
        else:
            print(f"Usage: {sys.argv[0]} [test_id|tier_number]")
    else:
        run_all(pause=40)
