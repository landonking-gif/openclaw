# Troubleshooting Guide — General-3

## Permission Errors

### "Permission denied: 'worker' role cannot use 'exec'"
**Cause:** Guardrails restriction  
**Fix:** Request elevation: `request_elevation(capability="exec", reason="...", duration_minutes=15)`  
**Alternative:** Work without shell commands

### "Filesystem sandboxed"
**Cause:** Worker role restriction  
**Fix:** Use `fs_unrestricted` elevation or work within workspace

## Tool Errors

### "Memory service error: 422"
**Cause:** Port 18820 down (OpenAI API key issue)  
**Status:** System-wide, not agent-specific  
**Workaround:** Use file-based memory instead

### "web_search: missing_brave_api_key"
**Cause:** API key not configured  
**Fix:** `openclaw configure --section web`

### "Message: Unknown target 'heartbeat' for discord"
**Cause:** Discord channel not configured  
**Fix:** Check gateway config

## Cron Issues

### Duplicate triggers
See: `CRON_FIX_GUIDE.md`  
Quick check: `crontab -l | sort | uniq -c | grep -v "^\s*1 "`

### Error messages in reminders
**Example:** "400 This model only supports single tool-calls at once!"  
**Cause:** Cron daemon passing its own errors  
**Fix:** Restart gateway, verify crontab

## Session Errors

### Subagent timeout
**Action:** `subagents kill <id>` then retry

### Session not responding
**Action:** `sessions_list` → check status → escalate if needed

## When All Else Fails
1. Check `check_permissions`
2. Review error logs
3. Report to Alpha Manager
4. Document in memory
