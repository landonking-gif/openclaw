#!/usr/bin/env python3
"""Simple serial test runner — one prompt at a time, writes results immediately."""
import json, time, sys, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

BASE = "http://127.0.0.1:18830"
DIR = Path(__file__).parent
PROMPTS = DIR / "prompts.json"
RESULTS = DIR / "results.jsonl"

def chat(msg, timeout=180):
    body = json.dumps({"message": msg}).encode()
    req = urllib.request.Request(
        f"{BASE}/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)}

def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    tests = [t for t in json.loads(PROMPTS.read_text()) if start <= t["id"] <= end]
    print(f"=== Tests {start}-{end} ({len(tests)} prompts) ===", flush=True)

    for t in tests:
        pid, cat, prompt = t["id"], t["cat"], t["prompt"]
        print(f"\n[{pid}] {cat}: {prompt[:70]}...", flush=True)

        t0 = time.time()
        resp = chat(prompt)
        elapsed = round(time.time() - t0, 2)

        text = resp.get("response", "")
        dels = resp.get("delegations", [])
        err = resp.get("error", "")

        tag = f"DELEGATED({len(dels)})" if dels else ("ERROR" if err else "DIRECT")
        print(f"    [{tag}] {elapsed}s", flush=True)
        print(f"    {(text or str(err))[:160]}", flush=True)

        result = {"id": pid, "cat": cat, "prompt": prompt, "expect": t["expect"],
                  "status": tag, "elapsed": elapsed, "response_text": text[:2000],
                  "delegations": dels, "error": str(err) if err else None}
        with open(RESULTS, "a") as f:
            f.write(json.dumps(result) + "\n")

        time.sleep(3)  # rate limit spacing

    print(f"\n=== Done. {len(tests)} results written to {RESULTS} ===", flush=True)

if __name__ == "__main__":
    main()
