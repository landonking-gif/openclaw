#!/usr/bin/env python3
import requests
import json
import time

# Configuration
ORCHESTRATOR_URL = "http://localhost:18830/v1/chat/completions"
TIMEOUT = 600  # 10 minutes per task

TASKS = [
    {
        "name": "Cross-Application Data Transfer",
        "description": "Spotlight (Cmd+Space) -> Calculator (999 * 555) -> Copy -> Notes -> Paste",
        "prompt": "Use your computer control skills to open Spotlight (Command+Space). Type 'Calculator' and hit enter to open it. Wait 2 seconds. Use the keyboard to calculate 999 * 555. Copy the result using Command+C. Open 'Notes' using Spotlight. Create a new note (Command+N) and paste the result. Return 'Done' when finished."
    },
    {
        "name": "Stealth Terminal Engineering",
        "description": "Spotlight -> Terminal -> Type echo command -> Enter",
        "prompt": "Use Spotlight to open a new instance of the 'Terminal' application. Do NOT use the `run_command` or bash tools for this. You must physically type the following command into the visible GUI terminal window using your keyboard typing tool: `echo \"OpenClaw Physical GUI Control Works!\" > /tmp/gui_proof.txt`. Then press Enter. Return 'Done' when finished."
    },
    {
        "name": "Kinesthetic Skill Execution",
        "description": "Write and execute draw.py on Desktop to move mouse in a circle",
        "prompt": "Write a temporary Python script on the Desktop called `draw.py`. This script should use `pyautogui` to smoothly move the mouse cursor in a large circle on the screen over 3 seconds. Then, execute the script. Do this all entirely autonomously using your available tools. Return 'Done' when finished."
    }
]

def run_task(task):
    print(f"\n[{TASKS.index(task)+1}/{len(TASKS)}] GOAL: {task['name']}")
    print(f"Description: {task['description']}")
    print(f"Sending request... (Timeout: {TIMEOUT}s)")
    
    start_time = time.time()
    try:
        response = requests.post(
            ORCHESTRATOR_URL,
            json={
                "model": "openclaw",
                "messages": [{"role": "user", "content": task["prompt"]}],
                "stream": False
            },
            timeout=TIMEOUT
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            print(f"Result: TASK FINISHED")
            print(f"Time: {duration:.1f}s")
            return True
        else:
            print(f"Result: ERROR (Code {response.status_code})")
            print(response.text)
            return False
            
    except requests.exceptions.Timeout:
        print(f"Result: CRITICAL SYSTEM ERROR / TIMEOUT (>{TIMEOUT}s)")
        return False
    except Exception as e:
        print(f"Result: EXCEPTION: {e}")
        return False

def main():
    print("="*70)
    print("STARTING ULTIMATE GUI AUTONOMY STRESS TEST")
    print("="*70)
    print(f"Total tasks: {len(TASKS)}")
    print(f"Timeout per task: {TIMEOUT}s")
    print("="*70)

    success_count = 0
    for task in TASKS:
        if run_task(task):
            success_count += 1

    print("\n" + "="*70)
    print("FINAL ULTIMATE GUI AUTONOMY REPORT")
    print("="*70)
    print(f"Success Rate: {success_count}/{len(TASKS)} ({(success_count/len(TASKS))*100:.0f}%)")
    print("="*70)

if __name__ == "__main__":
    main()
