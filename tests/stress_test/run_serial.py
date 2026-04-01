#!/usr/bin/env python3
"""
Robust test runner that processes one test at a time with proper error handling.
Writes each result immediately to results.jsonl.
Usage: python3 run_serial.py <start> <end>
"""
import json, time, sys, socket
from pathlib import Path
from datetime import datetime, timezone
from http.client import HTTPConnection

BASE_HOST = "127.0.0.1"
BASE_PORT = 18830
DIR = Path(__file__).parent
PROMPTS = DIR / "prompts.json"
RESULTS = DIR / "results.jsonl"

def chat(msg):
    """Send a chat message and return (response_dict, elapsed_seconds)."""
    body = json.dumps({"message": msg}).encode()
    t0 = time.time()
    try:
        conn = HTTPConnection(BASE_HOST, BASE_PORT, timeout=180)
        conn.request("POST", "/chat", body, {"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        return data, round(time.time() - t0, 2)
    except Exception as e:
        return {"error": str(e)}, round(time.time() - t0, 2)

def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    tests = [t for t in json.loads(PROMPTS.read_text()) if start <= t["id"] <= end]
    
    w = sys.stdout.write
    w(f"\n=== Tests {start}-{end} ({len(tests)} prompts) ===\n\n")
    sys.stdout.flush()
    
    for t in tests:
        w(f"[{t['id']:3d}] {t['cat']:20s} | {t['prompt'][:65]}\n")
        sys.stdout.flush()
        
        resp, elapsed = chat(t["prompt"])
        
        text = resp.get("response", "")
        dels = resp.get("delegations", [])
        err = resp.get("error", "")
        tag = f"DELEGATED({len(dels)})" if dels else ("ERROR" if err else "DIRECT")
        
        w(f"      [{tag}] {elapsed}s\n")
        preview = (text or str(err))[:180].replace("\n", " ")
        w(f"      {preview}\n\n")
        sys.stdout.flush()
        
        # Write result to file
        result = {
            "id": t["id"], "cat": t["cat"], "prompt": t["prompt"],
            "expect": t["expect"], "status": tag, "elapsed": elapsed,
            "text": text[:3000], "delegations": dels,
            "error": str(err) if err else None,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        with open(RESULTS, "a") as f:
            f.write(json.dumps(result) + "\n")
        
        time.sleep(3)
    
    w(f"=== Done. {len(tests)} results appended to {RESULTS.name} ===\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
