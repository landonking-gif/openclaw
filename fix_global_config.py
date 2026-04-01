import json
import os
from pathlib import Path

config_path = Path.home() / ".openclaw" / "openclaw.json"
if config_path.exists():
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    plugins = data.get('plugins', {}).get('entries', {})
    noisy_plugins = [
        "voice-call", "matrix", "nostr", "tlon", "twitch", "diagnostics-otel",
        "irc", "line", "mattermost", "msteams", "nextcloud-talk", "signal",
        "slack", "synology-chat", "telegram", "zalo", "whatsapp", "feishu",
        "googlechat", "bluebubbles", "device-pair", "lobster"
    ]
    
    for p in noisy_plugins:
        if p in plugins:
            plugins[p]['enabled'] = False
    
    # Also disable Bonjour globally just in case
    if 'discovery' not in data:
        data['discovery'] = {}
    data['discovery']['mdns'] = "off"
    
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Fixed {config_path}")
