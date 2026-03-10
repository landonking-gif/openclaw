# HEARTBEAT.md — Alpha Manager

Periodic checks to perform (read-only audits):

## Daily Tasks (2-4x per day)

### Morning Check (via cron/heartbeat)
- [ ] Review memory logs from yesterday
- [ ] Check for pending elevation requests from workers
- [ ] Verify all 4 workers are responsive
- [ ] Check budget status (daily spend)

### Midday Check
- [ ] Audit active subagents
- [ ] Review any error states
- [ ] Check Knowledge Vault connectivity

### Evening Check (via cron)
- [ ] Summarize day's activity
- [ ] Update MEMORY.md with key learnings
- [ ] Check for stuck processes

---

## Weekly Tasks
- [ ] Review and archive old memory files
- [ ] Audit permission grants
- [ ] Check for tool/resource deprecations
- [ ] Update documentation

---

## Monthly Tasks
- [ ] Full system health audit
- [ ] Clean stale sessions
- [ ] Review cost trends
- [ ] Archive old daily logs

---

## NOTES
Keep this file minimal to reduce token burn.
Only add tasks that require periodic human-style attention.
