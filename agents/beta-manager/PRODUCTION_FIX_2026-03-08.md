# URGENT: Production Crash Fix

## Incident
- **Time:** 2026-03-08 ~14:50 CDT
- **Affected:** general-1, general-2, general-4 (3/4 general workers)
- **Error:** `Cannot read properties of undefined (reading 'filter')`

## Root Cause
**OpenClaw framework bug:** Tool result processing code calls `.filter()` on undefined when tools return empty responses.

**Trigger pattern:**
1. Heartbeat triggers tool calls (`check_budget`, `list_elevation_requests`)
2. Tool returns `{isError: false}` with NO `content` field
3. Framework attempts: `toolResult.content.filter(...)` → CRASH

**Evidence from logs:**
```
general-4: check_budget @ 1772999756057 → {isError:false} [no content] → crash @ 1772999756080
general-2: list_elevation_requests + check_budget + subagents → crash @ 1772999686633  
general-1: subagents + list_elevation_requests → crash @ 1772999670864
```

## Fix Required

### Immediate: Framework Patch (REQUIRED)
Location: OpenClaw source - tool result processing code

```javascript
// BEFORE (crashes on empty):
const formatted = toolResult.content.filter(item => ...);

// AFTER (safe):
const formatted = (toolResult.content || []).filter(item => ...);
// OR
toolResult.content = toolResult.content || [];
const formatted = toolResult.content.filter(item => ...);
```

### Secondary: Tool Consistency
Update these tools to always return content:
- `check_budget` - currently returns empty when no budget
- `list_elevation_requests` - currently returns empty when no requests
- Audit all tools for empty response handling

```javascript
// Ensure minimum response structure:
{
  "content": [{"type": "text", "text": "{}"}]
}
```

## Files
- Full analysis: `CRASH_ANALYSIS_2026-03-08.md`
- This fix doc: `PRODUCTION_FIX_2026-03-08.md`

## Status
- ✅ Root cause identified
- ✅ Fix documented
- ⏳ Framework patch needed (requires manual edit/restart)
- ⏳ Workers need restart after fix

---
Reported by: Beta Manager
