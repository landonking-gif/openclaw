#!/usr/bin/env python3
import json
import time
import os

# Get memory info for the orchestrator process (port 18830)
import subprocess

try:
    # Find the orchestrator process
    result = subprocess.run(
        ["lsof", "-i", ":18830", "-t"],
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip():
        pid = result.stdout.strip()
        # Get memory info in bytes
        with open(f"/proc/{pid}/status") as f:
            lines = f.readlines()
            mem_info = {}
            for line in lines:
                if line.startswith("VmRSS:"):
                    mem_info["rss_mb"] = int(line.split()[1]) / 1024
                elif line.startswith("VmSize:"):
                    mem_info["vms_mb"] = int(line.split()[1]) / 1024
                elif line.startswith("VmPeak:"):
                    mem_info["peak_mb"] = int(line.split()[1]) / 1024
        
        # Get system memory
        with open("/proc/meminfo") as f:
            mem_total = None
            mem_available = None
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) / 1024 / 1024  # GB
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1]) / 1024 / 1024  # GB
        
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "pid": int(pid),
            "rss_mb": round(mem_info.get("rss_mb", 0), 2),
            "vms_mb": round(mem_info.get("vms_mb", 0), 2),
            "peak_mb": round(mem_info.get("peak_mb", 0), 2),
            "system_total_gb": round(mem_total, 2) if mem_total else None,
            "system_available_gb": round(mem_available, 2) if mem_available else None
        }
    else:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "error": "Orchestrator process not found on port 18830"
        }
except Exception as e:
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "error": str(e)
    }

# Append to JSONL file
log_file = os.path.expanduser("~/openclaw-army/data/logs/memory_monitor.jsonl")
with open(log_file, "a") as f:
    f.write(json.dumps(log_entry) + "\n")

# Keep only last 10000 lines to prevent unbounded growth
subprocess.run([
    "bash", "-c",
    f"tail -n 10000 {log_file} > {log_file}.tmp && mv {log_file}.tmp {log_file}"
], capture_output=True)
