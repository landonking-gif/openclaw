# Discord Setup Guide

## Issue
Discord message delivery failing: `Unknown target "heartbeat"`

## Solution

### Step 1: Check OpenClaw Channels
```bash
openclaw channels list
```

### Step 2: Configure Discord Channel
Edit `~/.config/openclaw/channels.yaml`:

```yaml
channels:
  discord:
    type: discord
    token: "YOUR_BOT_TOKEN"  # From Discord Developer Portal
    default_channel_id: "YOUR_CHANNEL_ID"
```

### Step 3: Get Channel ID
1. Enable Developer Mode in Discord (Settings > Advanced)
2. Right-click channel → "Copy Channel ID"

### Step 4: Test
```bash
openclaw send --channel discord --message "Test from Agentic-3"
```

## Creating Bot Token
1. Go to https://discord.com/developers/applications
2. Create New Application
3. Bot tab → "Add Bot"
4. Copy Token
5. Enable MESSAGE CONTENT INTENT (important!)

## Permissions Needed
- Send Messages
- Read Message History
- Embed Links
- Add Reactions (optional)
