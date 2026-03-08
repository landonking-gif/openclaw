# Cron Fix Guide — General-3 Spam Issue

## Quick Fix Commands

```bash
# 1. Check current crontab
crontab -l

# 2. Look for duplicates
crontab -l | sort | uniq -c | grep -v "^\s*1 "

# 3. Edit crontab, remove duplicates
crontab -e

# 4. Check system-wide cron
sudo cat /etc/crontab
ls /etc/cron.d/

# 5. Restart services
openclaw gateway stop
openclaw gateway start

# 6. Verify
openclaw gateway status
```

## Prevention

- Use single cron entry per agent
- Add logging: `* * * * * cmd >> /var/log/cron.log 2>&1`
- Test with 5-minute interval first
- Check for duplicate config files

## Monitoring

Watch for:
- Multiple timestamps in same minute
- Error messages in reminder content
- Response loops

## Escalation

If issues persist after fix:
- Check OpenClaw logs: `openclaw logs`
- Review gateway config
- Contact admin
