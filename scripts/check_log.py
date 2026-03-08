#!/usr/bin/env python3
"""Quick check of activity log structure."""
import json

with open("/Users/landonking/openclaw-army/data/logs/activity.jsonl") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

sids = set()
types = {}
for l in lines:
    e = json.loads(l)
    sid = e.get("session_id", "")
    sids.add(sid)
    t = e["type"]
    types[t] = types.get(t, 0) + 1

print(f"Unique session_ids: {sids}")
print(f"Types: {types}")
print()
# Show first entry
e = json.loads(lines[0])
print(f"First entry keys: {list(e.keys())}")
print(f"First entry: {json.dumps(e, indent=2)[:500]}")
