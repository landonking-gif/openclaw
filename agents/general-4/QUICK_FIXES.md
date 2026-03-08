# Quick Fixes — Common Issues

## Cron Spam
**Problem:** Duplicate triggers every 15 minutes
**Fix:**
```bash
openclaw gateway stop
crontab -e  # Remove duplicates
openclaw gateway start
```

## Permission Denied (exec)
**Problem:** Cannot run shell commands
**Fix:** Request elevation or work around

## Memory Service Down
**Problem:** Port 18820 error 422
**Fix:** File-based memory workaround

## Web Search Blocked
**Problem:** Missing API keys
**Fix:** Configure with `openclaw configure --section web`

## Model Errors
**Problem:** "single tool-call only" errors
**Fix:** Call tools one at a time
