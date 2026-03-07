# Security Fixes Applied - 2026-03-07

## Changes Made

### 1. CRITICAL: Disabled Device Auth Bypass
**Before:**
```json
"controlUi": { "enabled": true, "allowInsecureAuth": true, "dangerouslyDisableDeviceAuth": true }
```

**After:**
```json
"controlUi": { "enabled": true, "allowInsecureAuth": false, "dangerouslyDisableDeviceAuth": false }
```

**Impact:** Device identity checks are now enforced for Control UI access.

---

### 2. Security: Added plugins.allow Whitelist

Before: No whitelist defined - extensions could auto-load  
After: explicit whitelist configured:

```json
"plugins": {
  "enabled": true,
  "allow": [
    "memory-core",
    "permission-broker",
    "cost-tracker",
    "reasoning-engine",
    "diagnostics-otel",
    "device-pair",
    "copilot-proxy"
  ],
  ...
}
```

---

### 3. CRITICAL: Small Model Sandbox Warning Remains

**Status:** ⚠️ **NOT FIXED** (requires user decision)

The system still has small models (70B) with web tools enabled:
- `nvidia/meta/llama-3.3-70b-instruct`
- `nvidia/nvidia/llama-3.1-nemotron-70b-instruct`

**Recommended Fix Options:**
1. Enable sandbox for all agents: `"sandbox": { "mode": "all" }`
2. Remove web tools for small models: `tools.deny: ["group:web", "browser"]`
3. Use only large models (131K+ context) for web operations

---

## Remaining Warnings

1. Reverse proxy headers not trusted (low priority - Control UI is local-only)
2. Discord channel needs configuration to enable messaging
3. Heartbeats disabled for all subordinate agents

---

## Next Steps

- [ ] Decide on small model sandboxing approach
- [ ] Configure Discord token and enable channel
- [ ] Enable heartbeats for manager agents
- [ ] Update agents to latest version (2026.3.2 available)

---

*Applied by: King AI*  
*Date: 2026-03-07 02:55 AM CST*
