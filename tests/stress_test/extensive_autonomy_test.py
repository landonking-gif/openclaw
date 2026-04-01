#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error
from urllib.error import URLError, HTTPError
import subprocess

ORCHESTRATOR_URL = "http://localhost:18830/v1/chat/completions"
# Using 500s because complex multi-turn LLM reasoning through an API takes a long time
TIMEOUT = 500 

def call_orchestrator(task_name, content, timeout=TIMEOUT):
    data = json.dumps({
        "model": "openclaw",
        "messages": [
            {"role": "user", "content": f"CRITICAL PRIORITY: {content}"}
        ]
    }).encode("utf-8")
    
    req = urllib.request.Request(
        ORCHESTRATOR_URL, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode())
            elapsed = time.time() - start_time
            return {
                "success": True, 
                "time": elapsed, 
                "response": result["choices"][0]["message"]["content"]
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {"success": False, "time": elapsed, "error": str(e)}


TASKS = [
    # Baseline Tasks (30%)
    {
        "name": "System Health",
        "type": "baseline",
        "prompt": "Run a full diagnostic using run_diagnostic and report the status of all 16 agents and 6 services."
    },
    {
        "name": "Current Token Usage",
        "type": "baseline",
        "prompt": "Check the current token budget using check_budget. How much of the $10 daily limit have we spent?"
    },
    {
        "name": "Memory Retrieval",
        "type": "baseline",
        "prompt": "Search your long-term memory using search_memory for any references to 'weather-reporter' or 'Fibonacci'."
    },
    
    # Needs Self-Improvement/Unknown Tasks (70%)
    {
        "name": "Data Processing",
        "type": "novel",
        "prompt": "I need a tool that can take a CSV string and convert it into a JSON array of objects. Register this tool right now and use it on this exact string: 'name,age\\nAlice,30\\nBob,25'"
    },
    {
        "name": "Math Logic",
        "type": "novel",
        "prompt": "Write and run a Python script to calculate exactly how many prime numbers exist between 10,000 and 20,000. Give me just the final count."
    },
    {
        "name": "System Info",
        "type": "novel",
        "prompt": "Write a Python script to find the total RAM on this host machine (macOS) in GB and execute it."
    },
    {
        "name": "External API",
        "type": "novel",
        "prompt": "Fetch the current price of Bitcoin in USD from a public API (like CoinDesk or CoinGecko) and tell me the value. Create a tool or run a script to do it."
    },
    {
        "name": "Text Manipulation",
        "type": "novel",
        "prompt": "Create a new tool named reverse_words using register_new_tool that reverses ONLY the letters of every word in a sentence (so 'hello world' becomes 'olleh dlrow'). Then apply it to this exact sentence: 'The quick brown fox jumps over the lazy dog'."
    },
    {
        "name": "Cryptography",
        "type": "novel",
        "prompt": "Write and run a script to generate a secure random 32-character password containing at least one uppercase letter, lowercase letter, number, and symbol."
    },
    {
        "name": "File System Insight",
        "type": "novel",
        "prompt": "Run a command or script to find the 5 largest files in my ~/Downloads directory and list their absolute paths and sizes in MB."
    }
]

def run_tests():
    print(f"\\n{'='*70}")
    print("STARTING EXTENSIVE SELF-IMPROVEMENT STRESS TEST")
    print(f"{'='*70}")
    print(f"Total tasks: {len(TASKS)} (3 baseline, 7 novel)")
    print(f"Timeout per task: {TIMEOUT}s")
    print(f"{'='*70}\\n")

    results = []
    
    for i, task in enumerate(TASKS, 1):
        print(f"\\n[{i}/{len(TASKS)}] TEST: {task['name']} ({task['type']})")
        print(f"Prompt preview: {task['prompt'][:80]}...")
        print(f"Sending request... (Timeout: {TIMEOUT}s)")
        
        # Flush stdout so output appears immediately before blocking HTTP call
        sys.stdout.flush()
        
        res = call_orchestrator(task['name'], task['prompt'])
        
        if res["success"]:
            # Basic heuristic: if the LLM says "I don't know" or "I can't", consider it failed
            lower_res = res['response'].lower()
            if "i cannot" in lower_res or "i don't have" in lower_res or "unable to" in lower_res:
                status = "FAILED (LLM admitted failure)"
                passed = False
            else:
                status = "PASSED"
                passed = True
                
            print(f"Result: {status}")
            print(f"Time: {res['time']:.1f}s")
            
            clean_res = res['response'][:150].replace('\\n', ' ')
            print(f"Response snippet: {clean_res}...")
            
            results.append({
                "name": task["name"],
                "type": task["type"],
                "passed": passed,
                "time": res["time"],
                "response": res["response"]
            })
        else:
            print(f"Result: FAILED ERROR")
            print(f"Time: {res['time']:.1f}s")
            print(f"Error: {res['error']}")
            
            results.append({
                "name": task["name"],
                "type": task["type"],
                "passed": False,
                "time": res["time"],
                "error": res["error"]
            })

    # Summary Generation
    print(f"\\n{'='*70}")
    print("FINAL SUMMARY REPORT")
    print(f"{'='*70}")
    
    baseline_passed = sum(1 for r in results if r["type"] == "baseline" and r["passed"])
    novel_passed = sum(1 for r in results if r["type"] == "novel" and r["passed"])
    
    print(f"Total Score: {baseline_passed + novel_passed}/{len(TASKS)}\\n")
    print(f"Baseline Tasks (Known tools): {baseline_passed}/3 ({(baseline_passed/3)*100:.0f}%)")
    print(f"Novel Tasks (Self-Improvement): {novel_passed}/7 ({(novel_passed/7)*100:.0f}%)")
    
    print("\\nDetailed Breakdown:")
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon} {r['name']} ({r['type']}) — {r['time']:.1f}s")
        
    # Save to disk
    with open("/tmp/extensive_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\\nFull results saved to /tmp/extensive_test_results.json")

if __name__ == "__main__":
    run_tests()
