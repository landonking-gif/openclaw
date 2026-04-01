#!/usr/bin/env python3
"""Re-run failed and timed-out tests from the stress test."""
import sys
sys.path.insert(0, "/Users/landonking/openclaw-army/scripts")
from stress_test import TESTS, send_chat, verify_result
import json, time
from datetime import datetime
from pathlib import Path

RESULTS_FILE = Path("/Users/landonking/openclaw-army/data/test_results") / f"rerun_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

# Tests to re-run: timeouts + failures
RERUN_IDS = [31, 68, 95]

print(f"Re-running {len(RERUN_IDS)} tests: {RERUN_IDS}")
print(f"Results: {RESULTS_FILE}\n")

for tid in RERUN_IDS:
    test = [t for t in TESTS if t["id"] == tid][0]
    print(f"Test #{tid:>3} [{test['cat']:>12}] {test['prompt'][:55]}...", end=" ", flush=True)

    result = send_chat(test["prompt"], timeout=300)

    if result["error"]:
        status = "ERROR"
        detail = f"HTTP error: {result['error'][:100]}"
    else:
        if test.get("expect_delegation") and result.get("delegations"):
            time.sleep(8)
        verified, detail = verify_result(test, result["response"], result.get("delegations", []))
        if "HALLUCINATION" in detail:
            status = "HALLUCINATION"
        elif verified:
            status = "PASS"
        else:
            status = "FAIL"

    d = len(result.get("delegations", []))
    t = result["time_sec"]
    print(f"[{status:>13}] {t:>5.1f}s d={d} | {detail[:60]}")

    record = {
        "test_id": tid, "category": test["cat"], "prompt": test["prompt"],
        "response": result.get("response", "")[:2000],
        "delegations": result.get("delegations", []),
        "time_sec": t, "error": result.get("error"),
        "verified": verified if not result["error"] else False,
        "verify_detail": detail, "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

    time.sleep(3)

print("\nDone. Analyzing re-run results:")
results = [json.loads(l) for l in RESULTS_FILE.read_text().strip().split("\n")]
for r in results:
    print(f"  #{r['test_id']:3d} [{r['category']:>12}] {r['status']:>13} | {r['verify_detail'][:60]}")
