# Health Audit Schedule

## Daily (via cron)
- **09:00** - Morning health check
- **15:00** - Midday system audit  
- **21:00** - Evening summary

## Weekly (Sundays)
- Archive old memory files
- Audit permission grants
- Review cost trends

## Monthly (1st of month)
- Full system health audit
- Clean stale sessions
- Update documentation

## Cron Expression Examples
```
# Daily at 9 AM, 3 PM, 9 PM
0 9,15,21 * * *

# Weekly on Sunday at midnight
0 0 * * 0

# Monthly on 1st at 2 AM
0 2 1 * *
```
