#!/usr/bin/env python3
"""Analyze results from stress test."""
import json, sys
from pathlib import Path

RESULTS = Path("/Users/landonking/openclaw-army/tests/stress_test/results.jsonl")

results = []
with open(RESULTS) as f:
    for line in f:
        if line.strip():
            results.append(json.loads(line))

print(f"Total results: {len(results)}\n")
print("=== RESULTS SUMMARY ===\n")

for r in results:
    text = r.get("text", "")
    issues = []
    
    # Self-awareness checks
    if r["id"] == 13 and "kimi" not in text.lower():
        issues.append("IDENTITY: Says Claude, should know its Kimi K2.5")
    if r["id"] == 11 and "16" not in text:
        issues.append("WRONG: Does not mention 16 agents")
    if r["id"] == 15 and "memory" not in text.lower():
        issues.append("INCOMPLETE: May not list all services")
    if r["elapsed"] > 100:
        issues.append(f"SLOW: {r['elapsed']}s")
    
    # Delegation checks
    expect = r.get("expect", "")
    if "delegate_alpha" in expect and "DIRECT" in r["status"]:
        issues.append("SHOULD_DELEGATE: Expected alpha delegation")
    if "delegate_beta" in expect and "DIRECT" in r["status"]:
        issues.append("SHOULD_DELEGATE: Expected beta delegation")
    if "delegate_gamma" in expect and "DIRECT" in r["status"]:
        issues.append("SHOULD_DELEGATE: Expected gamma delegation")
    
    issue_str = " | ".join(issues) if issues else "OK"
    print(f"  [{r['id']:3d}] {r['status']:15s} {r['elapsed']:6.1f}s | {r['cat']:20s} | {issue_str}")

# Stats
print(f"\n=== STATS ===")
statuses = {}
for r in results:
    s = r["status"]
    statuses[s] = statuses.get(s, 0) + 1
for s, c in sorted(statuses.items()):
    print(f"  {s}: {c}")

avg_time = sum(r["elapsed"] for r in results) / len(results)
print(f"  Avg response time: {avg_time:.1f}s")
print(f"  Slowest: {max(r['elapsed'] for r in results):.1f}s (test {max(results, key=lambda r: r['elapsed'])['id']})")
print(f"  Fastest: {min(r['elapsed'] for r in results):.1f}s (test {min(results, key=lambda r: r['elapsed'])['id']})")
