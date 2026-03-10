# Discord Integration Guide

## Current Issue
- No active Discord sessions found
- `message` tool fails with "Unknown target 'heartbeat' for discord"

## Why It Fails
Discovered sessions: only `heartbeat` and `cron` (no `discord`)

## Solutions

### Option 1: Pre-start Discord Session
User starts Discord session before cron runs:
```bash
# In Discord chat, user says:
@gamma-manager start session
```

### Option 2: Use Gateway Channel
Configure `cron-event` to deliver to Discord:
```json
{
  "delivery": {
    "type": "discord",
    "channel_id": "YOUR_CHANNEL_ID"
  }
}
```

### Option 3: Use sessions_send
```javascript
sessions_send({
  sessionKey: "agent:main:discord-session",
  message: "Status update..."
})
```

## Recommended Fix
Configure Discord channel in `openclaw.json` cron settings.
