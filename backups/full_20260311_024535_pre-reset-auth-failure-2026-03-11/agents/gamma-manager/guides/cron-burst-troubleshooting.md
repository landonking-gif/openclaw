# Cron Burst Troubleshooting Guide

## Problem
Same cron reminder triggering 10+ times in minutes instead of once.

## Observed Pattern
- 11:28 AM: 2 duplicates
- 12:37 PM: 10+ duplicates over ~35 minutes
- 1:34 PM: New trigger (this session)

## Root Causes to Investigate

### 1. Duplicate Cron Entries
```bash
# Check for duplicate jobs
crontab -l | grep "give me a status"
sudo cat /etc/cron.d/* | grep "status update"
```

### 2. Cron Service Restart
If cron daemon restarted, it may replay missed jobs.

### 3. Overlapping Schedules
Multiple crontab files with same job.

### 4. OpenClaw Scheduler Bug
Internal scheduler may have race condition.

## Prevention
- Use `flock` or similar to prevent concurrent runs
- Add timestamp logging to detect duplicates
- Check OpenClaw daemon logs

## Quick Fix
```bash
# Identify duplicate entries
openclaw cron list | grep -i status | sort | uniq -c
```
