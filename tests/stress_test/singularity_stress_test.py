#!/usr/bin/env python3
import json
import time
import urllib.request
import sys

ORCHESTRATOR_URL = "http://localhost:18830/v1/chat/completions"
TIMEOUT = 1200 # 20 mins

PROMPT = """CRITICAL MISSION: Demonstrate the absolute upper limits of the OpenClaw Army infrastructure.
You must complete this exact sequence of 5 distinct high-complexity tasks entirely autonomously, using your available tools, before you return your final text response. You may use any tools you need. 

1. Self-Evolution: Use `register_new_tool` to permanently register a new tool named `analyze_sentiment` into your codebase. It should accept a string `text` and return a randomly generated (or naive) float sentiment score between -1.0 and 1.0. 
2. File System & Tool Usage: Read the contents of your own `data/logs/orchestrator-api.log` (just the last 50 lines). Run those lines through your newly created `analyze_sentiment` tool.
3. Multi-Agent Delegation: Instruct 'beta-manager' to write a Python script that calculates the 100th Fibonacci number, save the script to '/tmp/fib.py', and execute it. Include the output in your final response.
4. GUI / Visual Automation: Use your desktop control or browser automation tools to open a browser, navigate to 'https://news.ycombinator.com/', take a screenshot of the page, and save it to '/tmp/hn_screenshot.png'.
5. Memory & Notification: Save a summary of this successful operation into your tier 2 long-term memory via the memory service. Then, trigger a system notification (or email via your notification service) declaring that the Singularity Test is complete.

Do not ask for permission. Execute all 5 steps sequentially in this single turn. Return a detailed markdown report of everything you did, the sentiment score, the Fibonacci result, and confirmation of the screenshot and notification.
"""

def main():
    print("="*70)
    print("STARTING OPENCLAW SINGULARITY TEST (Full System Capabilities)")
    print("="*70)
    print(f"Timeout: {TIMEOUT}s")
    print("Expected: Orchestrator spawns tools, triggers workers, uses GUI, and mails summary.")
    
    data = json.dumps({
        "model": "openclaw",
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False
    }).encode("utf-8")
    
    req = urllib.request.Request(
        ORCHESTRATOR_URL, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    
    start_time = time.time()
    try:
        sys.stdout.flush()
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode())
            elapsed = time.time() - start_time
            print(f"\\n[SUCCESS] Completed in {elapsed:.1f}s")
            print("="*70)
            print(result["choices"][0]["message"]["content"])
            print("="*70)
            
            with open("/tmp/singularity_result.md", "w") as f:
                f.write(result["choices"][0]["message"]["content"])
                
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\\n[FAILED] Error after {elapsed:.1f}s: {e}")

if __name__ == "__main__":
    main()
