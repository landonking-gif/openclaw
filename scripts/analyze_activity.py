#!/usr/bin/env python3
"""Analyze activity log to see all test sessions and their outcomes."""
import json, sys
from pathlib import Path
from collections import defaultdict

LOG = Path("/Users/landonking/openclaw-army/data/logs/activity.jsonl")

sessions = {}
order = []

for line in LOG.read_text().strip().split("\n"):
    if not line.strip():
        continue
    e = json.loads(line)
    sid = e.get("session_id", "")
    if not sid:
        continue
    if sid not in sessions:
        sessions[sid] = {"prompts": [], "delegations": [], "responses": [], "errors": [], "thinking": [], "tool_calls": []}
        order.append(sid)
    t = e["type"]
    if t == "user_message":
        sessions[sid]["prompts"].append(e["content"][:120])
    elif t == "delegation":
        sessions[sid]["delegations"].append(e)
    elif t == "response":
        sessions[sid]["responses"].append(e["content"][:200])
    elif t == "error":
        sessions[sid]["errors"].append(e["content"][:200])
    elif t == "llm_thinking":
        sessions[sid]["thinking"].append(e["content"][:200])
    elif t == "llm_tool_calls":
        sessions[sid]["tool_calls"].append(e)

print(f"Total sessions: {len(order)}\n")
for i, sid in enumerate(order):
    s = sessions[sid]
    nd = len(s["delegations"])
    ne = len(s["errors"])
    prompt = s["prompts"][0] if s["prompts"] else "?"
    
    # Check delegation details
    deleg_info = ""
    for d in s["delegations"]:
        meta = d.get("meta", {})
        dispatched = meta.get("dispatched", "?")
        target = meta.get("manager", "?")
        deleg_info += f"\n     -> delegated to {target} (dispatched={dispatched})"
    
    resp = s["responses"][-1][:150] if s["responses"] else "NO RESPONSE"
    
    status = "OK" if ne == 0 else "ERROR"
    print(f"#{i+1:>2} [{status}] delegations={nd} errors={ne}")
    print(f"     PROMPT: {prompt}")
    if deleg_info:
        print(f"     DELEGATIONS:{deleg_info}")
    print(f"     RESPONSE: {resp[:120]}...")
    print()
