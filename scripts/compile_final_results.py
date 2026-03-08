#!/usr/bin/env python3
"""Compile final test results across all runs. Latest result per test_id wins."""
import json
from pathlib import Path
from collections import defaultdict

results = {}
for f in sorted(Path("data/test_results").glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        tid = r["test_id"]
        results[tid] = r

by_status = defaultdict(list)
by_cat = defaultdict(lambda: defaultdict(int))

for tid in sorted(results):
    r = results[tid]
    s = r.get("status", "UNKNOWN")
    by_status[s].append(tid)
    by_cat[r["category"]][s] += 1

print("=== FINAL RESULTS (latest per test) ===")
print(f"Total tests: {len(results)}")
for s in ["PASS", "FAIL", "ERROR", "HALLUCINATION", "UNKNOWN"]:
    ids = by_status.get(s, [])
    if ids:
        print(f"  {s:>15}: {len(ids):3d} -- {ids}")

print()
print("=== BY CATEGORY ===")
for cat in sorted(by_cat):
    counts = by_cat[cat]
    total = sum(counts.values())
    p = counts.get("PASS", 0)
    print(f"  {cat:>12}: {p}/{total} pass  {dict(counts)}")

print()
print("=== FAILED/ERROR DETAILS ===")
for tid in sorted(results):
    r = results[tid]
    if r.get("status") != "PASS":
        detail = r.get("verify_detail", "")[:80]
        prompt = r["prompt"][:80]
        cat = r["category"]
        status = r["status"]
        print(f"  #{tid:>3} [{cat:>12}] {status:>13} | {detail}")
        print(f"       prompt: {prompt}...")

print()
print("=== TIMING STATS ===")
times = [r["time_sec"] for r in results.values() if r.get("time_sec")]
if times:
    print(f"  Avg: {sum(times)/len(times):.1f}s  Min: {min(times):.1f}s  Max: {max(times):.1f}s")
    delegates = [r["time_sec"] for r in results.values() if r.get("delegations") and len(r["delegations"]) > 0]
    non_delegates = [r["time_sec"] for r in results.values() if not r.get("delegations") or len(r["delegations"]) == 0]
    if delegates:
        print(f"  Delegated tasks avg: {sum(delegates)/len(delegates):.1f}s ({len(delegates)} tasks)")
    if non_delegates:
        print(f"  Direct tasks avg: {sum(non_delegates)/len(non_delegates):.1f}s ({len(non_delegates)} tasks)")
