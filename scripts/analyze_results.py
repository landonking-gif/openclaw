#!/usr/bin/env python3
"""Analyze all stress test results."""
import json
from pathlib import Path

results_dir = Path("/Users/landonking/openclaw-army/data/test_results")
all_results = {}

for f in sorted(results_dir.glob("stress_test_*.jsonl")):
    for line in f.read_text().strip().split("\n"):
        if line.strip():
            r = json.loads(line)
            tid = r["test_id"]
            all_results[tid] = r

cats = {}
for tid in sorted(all_results.keys()):
    r = all_results[tid]
    cat = r["category"]
    status = r["status"]
    if cat not in cats:
        cats[cat] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "HALLUCINATION": 0}
    cats[cat][status] = cats[cat].get(status, 0) + 1

print(f"Total tests with results: {len(all_results)}")
missing = sorted(set(range(1, 101)) - set(all_results.keys()))
print(f"Missing tests ({len(missing)}): {missing}")
print()
print(f"{'Category':<15} {'PASS':>5} {'FAIL':>5} {'ERR':>5} {'HALLUC':>6}")
print("-" * 40)
total_p = total_f = total_e = total_h = 0
for cat, c in cats.items():
    print(f"{cat:<15} {c['PASS']:>5} {c['FAIL']:>5} {c['ERROR']:>5} {c['HALLUCINATION']:>6}")
    total_p += c["PASS"]
    total_f += c["FAIL"]
    total_e += c["ERROR"]
    total_h += c["HALLUCINATION"]
print("-" * 40)
print(f"{'TOTAL':<15} {total_p:>5} {total_f:>5} {total_e:>5} {total_h:>6}")

print("\n=== FAILURES & ISSUES ===")
for tid in sorted(all_results.keys()):
    r = all_results[tid]
    if r["status"] != "PASS":
        print(f"  #{tid:>3} [{r['category']:>12}] {r['status']:>13} | {r['verify_detail'][:80]}")
        if r.get("error"):
            print(f"       ERROR: {r['error'][:100]}")
        resp = r.get("response", "")
        if resp:
            print(f"       RESPONSE (first 200 chars): {resp[:200]}")
