# HEARTBEAT.md — Zeta Manager

Periodic checks to perform (read-only audits):

## Daily Tasks (2-4x per day)

### Morning Check
- [ ] Review pending elevation requests from workers
- [ ] Check cloud cost dashboard for anomalies
- [ ] Verify all 4 infra workers responsive
- [ ] Review active alerts (if any monitoring configured)

### Midday Check
- [ ] Audit active subagents/spawned tasks
- [ ] Check for stuck or long-running infrastructure processes
- [ ] Review budget status (daily spend)

### Evening Check (via cron)
- [ ] Summarize day's infrastructure activity
- [ ] Update MEMORY.md with operational learnings
- [ ] Check certificate expiry (>30 days out)
- [ ] Verify no orphaned cloud resources

---

## Weekly Tasks

- [ ] Deep dive on cloud costs — identify optimization opportunities
- [ ] Review and archive old memory files
- [ ] Audit permission grants (who has what access)
- [ ] Update infrastructure documentation
- [ ] Review any incidents from the week

---

## Monthly Tasks

- [ ] Full infrastructure audit (resources, costs, security)
- [ ] Clean stale sessions and orphaned processes
- [ ] Review cost trends and forecasting
- [ ] Security scan and compliance check
- [ ] Archive old daily logs and incident reports
- [ ] Update runbooks based on lessons learned

---

## Rotating Checks

Spend 5 minutes on one of these each heartbeat:

| Day | Focus | Action |
|-----|-------|--------|
| Mon | Costs | Review billing dashboard |
| Tue | Security | Check access logs, scan for vulnerabilities |
| Wed | Performance | Review metrics, identify bottlenecks |
| Thu | Reliability | Review error rates, SLO compliance |
| Fri | Documentation | Update runbooks, incident summaries |
| Sat | Optimization | Identify right-sizing opportunities |
| Sun | Planning | Review upcoming changes, capacity |

---

## NOTES

Keep this file minimal to reduce token burn. Only add tasks that require periodic attention.

**Emergency Override:** If any check reveals a critical issue (security breach, major outage, runaway costs), escalate immediately to King AI and notify Landon.
