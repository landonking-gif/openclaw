# HEARTBEAT.md — General-3

## Daily Checks (On Heartbeat)

### When This Runs
- Every 30 minutes (if enabled)
- Trigger: cron heartbeat

### Tasks to Check

- [ ] **Active Subagents** — Run: `subagents list`
  - Any stuck processes?
  - Kill if needed
  
- [ ] **Sessions Review** — Check: `sessions_list`
  - Active sessions needing attention?
  - Messages waiting?

- [ ] **Memory Update** — Review:
  - Does `memory/YYYY-MM-DD.md` exist?
  - Any important events to log?
  - Update `MEMORY.md` with key learnings

- [ ] **Workspace Health** — Look for:
  - Orphan files
  - Temp files to clean
  - Documentation needing updates

### Action Items

If all clear → Reply: **HEARTBEAT_OK**

If issues found → Execute fixes, document in memory

### Last Run
- **Date:** 2026-03-07
- **Time:** Variable (cron spam issue ongoing)
- **Status:** Active monitoring

## Notes

- Cron currently misfiring (see: `CRON_FIX_GUIDE.md`)
- Responding to heartbeats despite duplicates
- Ready for actual tasks
