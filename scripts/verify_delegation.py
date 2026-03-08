#!/usr/bin/env python3
"""Verify delegation actually creates files on disk."""
import json, time, os, urllib.request

ORCH = "http://127.0.0.1:18830"
TARGET = os.path.expanduser("~/Desktop/test_delegation.py")

# Clean up first
if os.path.exists(TARGET):
    os.remove(TARGET)

print("Sending delegation request...")
data = json.dumps({"message": "Create a Python file called test_delegation.py on my Desktop that prints Hello World. This must be created on disk."}).encode()
req = urllib.request.Request(f"{ORCH}/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)

print(f"Response (300ch): {result.get('response', '')[:300]}")
print(f"Delegations: {len(result.get('delegations', []))}")
for d in result.get("delegations", []):
    print(f"  Manager: {d.get('manager')}")
    print(f"  Dispatched: {d.get('dispatched')}")
    print(f"  Agent Response: {str(d.get('agent_response', ''))[:300]}")

# Wait for file creation
print("\nWaiting 10s for file creation...")
time.sleep(10)

# VERIFY
if os.path.exists(TARGET):
    content = open(TARGET).read()
    print(f"\n=== VERIFIED: File EXISTS ===")
    print(f"Content:\n{content}")
else:
    print(f"\n=== FAILED: File does NOT exist at {TARGET} ===")
    print("The delegation did NOT actually create the file.")
