#!/usr/bin/env python3
"""Comprehensive activity log analyzer - shows all test sessions and outcomes."""
import json
from pathlib import Path

LOG = Path("/Users/landonking/openclaw-army/data/logs/activity.jsonl")

sessions = {}
order = []

for line in LOG.read_text().strip().split("\n"):
    if not line.strip():
        continue
    e = json.loads(line)
    sid = e.get("session", "")  # field is "session" not "session_id"
    if not sid:
        continue
    if sid not in sessions:
        sessions[sid] = {
            "prompts": [], "delegations": [], "responses": [], 
            "errors": [], "thinking": [], "tool_calls": []
        }
        order.append(sid)
    t = e["type"]
    if t == "user_message":
        sessions[sid]["prompts"].append(e["content"][:200])
    elif t == "delegation":
        sessions[sid]["delegations"].append(e)
    elif t == "response":
        sessions[sid]["responses"].append(e["content"][:300])
    elif t == "error":
        sessions[sid]["errors"].append(e["content"][:300])
    elif t == "llm_thinking":
        sessions[sid]["thinking"].append(e["content"][:300])
    elif t == "llm_tool_calls":
        sessions[sid]["tool_calls"].append(e)

print(f"Total sessions with IDs: {len(order)}\n")
for i, sid in enumerate(order):
    s = sessions[sid]
    nd = len(s["delegations"])
    ne = len(s["errors"])
    prompt = s["prompts"][0] if s["prompts"] else "?"
    
    deleg_info = ""
    for d in s["delegations"]:
        meta = d.get("meta", {})
        dispatched = meta.get("dispatched", "?")
        target = meta.get("manager", "?")
        task = meta.get("task", "")[:80]
        deleg_info += f"\n     -> {target} (dispatched={dispatched}): {task}"
    
    resp = s["responses"][-1][:200] if s["responses"] else "NO RESPONSE"
    
    status = "ERR" if ne > 0 else ("DEL" if nd > 0 else " OK")
    print(f"#{i+1:>2} [{status}] d={nd} e={ne} sid={sid[:15]}")
    print(f"     Q: {prompt}")
    if deleg_info:
        print(f"     DELEGATIONS:{deleg_info}")
    print(f"     A: {resp[:180]}...")
    print()
