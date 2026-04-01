#!/usr/bin/env python3
"""
OpenClaw Army Stress Test Runner
Sends prompts to the orchestrator, captures responses + activity traces.
Outputs results to tests/stress_test/results.jsonl
"""

import json, time, sys, os, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://127.0.0.1:18830"
RESULTS_FILE = Path(__file__).parent / "results.jsonl"
PROMPTS_FILE = Path(__file__).parent / "prompts.json"

def api(method, path, body=None, timeout=180):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:500]}
    except urllib.error.URLError as e:
        return {"error": f"URLError: {e.reason}"}
    except TimeoutError:
        return {"error": "timeout_180s"}
    except Exception as e:
        return {"error": str(e)}

def send_prompt(prompt_text, session_id=None):
    body = {"message": prompt_text}
    if session_id:
        body["session_id"] = session_id
    t0 = time.time()
    resp = api("POST", "/chat", body)
    elapsed = round(time.time() - t0, 2)
    return resp, elapsed

def get_activity_since(ts, limit=50):
    entries = api("GET", f"/activity?limit={limit}")
    if isinstance(entries, dict) and "entries" in entries:
        return [e for e in entries["entries"] if e.get("ts", "") >= ts]
    return entries if isinstance(entries, list) else []

def run_test(test, session_id=None):
    ts_before = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    time.sleep(0.1)
    
    resp, elapsed = send_prompt(test["prompt"], session_id)
    time.sleep(1)  # Let activity log catch up
    
    activity = get_activity_since(ts_before)
    
    result = {
        "id": test["id"],
        "cat": test["cat"],
        "prompt": test["prompt"],
        "expect": test["expect"],
        "response": resp,
        "elapsed_sec": elapsed,
        "activity_trace": activity,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return result

def run_range(start, end):
    with open(PROMPTS_FILE) as f:
        prompts = json.load(f)
    
    tests = [p for p in prompts if start <= p["id"] <= end]
    total = len(tests)
    print(f"\n{'='*60}")
    print(f"  Running tests {start}-{end} ({total} prompts)")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    results = []
    for test in tests:
        print(f"[{test['id']:3d}/{end}] {test['cat']:20s} | {test['prompt'][:60]}...")
        sys.stdout.flush()
        result = run_test(test)
        results.append(result)
        
        # Extract key info for display
        resp = result["response"]
        resp_text = resp.get("response", resp.get("error", "???"))
        if isinstance(resp_text, str):
            resp_text = resp_text[:120]
        delegations = resp.get("delegations", [])
        n_delegated = len(delegations)
        activity_types = [a.get("type", "?") for a in result.get("activity_trace", []) if isinstance(a, dict)]
        
        status = "DELEGATED" if n_delegated > 0 else ("ERROR" if "error" in resp else "DIRECT")
        print(f"       [{status}] {result['elapsed_sec']}s | Delegations: {n_delegated}")
        print(f"       {resp_text}")
        print()
        sys.stdout.flush()
        
        # Append to file
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(result) + "\n")
        
        # Small delay between tests to avoid rate limiting
        time.sleep(2)
    
    return results

if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    run_range(start, end)
