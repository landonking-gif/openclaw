# Error Log — General-3

## 2026-03-07

### 3:19 PM — Cron Spam Begins
- **Type:** Scheduling error
- **Count:** 20+ duplicate triggers
- **Impact:** Token waste, notification spam
- **Root:** Multiple crontab entries suspected
- **Fix:** See `CRON_FIX_GUIDE.md`

### 3:19 PM — Permission Denied: exec
**Error:** `Permission denied: 'worker' role cannot use 'exec'`  
**Cause:** Guardrails restriction  
**Action:** Noted restriction, worked around
**Status:** Ongoing restriction

### 3:19 PM — Permission Denied: web_search/web_fetch
**Error:** Both blocked  
**Cause:** Guardrails  
**Action:** Documented in blockers list
**Status:** Awaiting elevation if needed

### 3:37 PM — Memory Service Error 422
**Error:** `Memory service error: 422 {"detail":[{"type":"missing","loc":["body","success"],"msg":"Field required","input": ...}}`  
**Cause:** Port 18820 down (OpenAI API key issue)  
**Scope:** System-wide  
**Action:** Switched to file-based memory
**Status:** Persistent

### 4:00 PM — Model Error
**Error:** `400 This model only supports single tool-calls at once!`  
**Source:** Cron daemon error pollution  
**Action:** Documented, working around
**Status:** Cron issue, not agent issue

### 5:12 PM — Discord Send Failed
**Error:** `Unknown target "heartbeat" for discord`  
**Cause:** Discord channel not properly configured  
**Action:** Reported via other means
**Status:** Non-blocking

## Pattern Analysis
- **Most common:** Permission denials (expected for worker role)
- **Systemic:** Cron spam, memory service down
- **Resolution:** Documentworkarounds, request elevation when critical

## Lessons
- Use file-based memory when service down
- NO_REPLY prevents duplicate processing waste
- Elevation requests must be specific and justified
