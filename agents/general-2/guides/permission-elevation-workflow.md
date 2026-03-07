# Permission Elevation Workflow

## Overview
General-2 operates under restricted permissions. This guide documents when and how to request elevated capabilities.

## Current Restrictions
- ❌ No shell execution (`exec`, `bash`)
- ❌ No cross-agent messaging (only respond to manager)
- ❌ No filesystem access outside workspace
- ❌ No elevated/sudo operations

## Request Process

### Step 1: Assess Need
Before requesting, confirm the task genuinely requires the capability.

### Step 2: Submit Request
```javascript
request_elevation({
  capability: "exec", // or sessions_send, fs_unrestricted, elevated, etc.
  reason: "Specific detailed reason",
  duration_minutes: 15
})
```

### Step 3: Wait for Approval
Do NOT retry the blocked tool before receiving approval.

### Step 4: Execute (if approved)
Use the capability within the granted timeframe.

### Step 5: Graceful Degradation (if denied)
Explain alternative approach or report inability to complete.

## Recent Requests
| Date | Capability | Status | Reason |
|------|------------|--------|--------|
| N/A | — | — | No requests made |

## Notes
- Grants are temporary
- Minimum duration should be used
- Check `check_permissions` to see remaining time
