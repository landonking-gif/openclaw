# Manager Heartbeat Configuration

## Current Status
| Manager | Port | Heartbeat | Status |
|---------|------|-----------|--------|
| Alpha Manager | 18800 | Disabled | ⚠️ Needs enable |
| Beta Manager | 18801 | Disabled | ⚠️ Needs enable |
| Gamma Manager | 18802 | Disabled | ⚠️ Needs enable |
| King AI (main) | 18789 | 30m | ✅ Active |

## Configuration Template
```json
{
  "heartbeat": {
    "enabled": true,
    "intervalMinutes": 30,
    "includeReasoning": false,
    "suppressToolErrorWarnings": false
  }
}
```

## Activation Steps
1. Edit each manager's `openclaw.json`
2. Add heartbeat config under `agents.defaults`
3. Restart agent session

## Recommended Checks (per HEARTBEAT.md)
- Review worker logs
- Check for elevation requests
- Verify agent responsiveness
- Audit active subagents
