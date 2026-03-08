# CRITICAL CRASH ANALYSIS - 2026-03-08 15:11 CDT

## Incident Summary
- **Time:** Started ~14:50 CDT (2:50 PM)
- **Affect:** 3/4 general workers down (general-1, general-2, general-4)
- **Healthy:** general-3 (hasn't triggered affected code path)
- **Type:** JavaScript runtime error in OpenClaw framework

## Error Pattern
```
"Cannot read properties of undefined (reading 'filter')"
```

## Root Cause
**Location:** OpenClaw agent framework - tool result processing code

**Bug:** When `check_budget` tool returns empty response (no `content` field), framework code attempts to call `.filter()` on undefined.

**Evidence from general-4 transcript:**
```javascript
// 1772999756057: check_budget called
{ 
  "role": "toolResult", 
  "toolName": "check_budget", 
  "isError": false,
  "timestamp": 1772999756057 
}
// NO content field!
// → immediate crash on .filter() call
```

## Affected Tools
Likely any tool that can return empty responses:
- `check_budget` - empty when no budget configured
- `list_elevation_requests` - empty when no pending requests
- Potentially others

## Fix Required

### Option 1: Guard in tool result processing (Framework level)
```javascript
// Before
const items = toolResult.content.filter(...);

// After
const items = (toolResult.content || []).filter(...);
```

### Option 2: Fix tools to always return content
Update `check_budget` and similar tools to always return at minimum:
```json
{ "content": [{"type": "text", "text": "{}"}] }
```

### Option 3: Both (Recommended)
- Fix framework to be defensive
- Fix tools to be consistent

## Timeline
```
1772999670864 - general-1 crash
1772999686633 - general-2 crash  
1772999756080 - general-4 crash
1772999756098 - general-4 heartbeat timed out
```

All crashes within ~85 seconds, consistent with heartbeat checks triggering `check_budget`.

## Detection Pattern
Crash follows this sequence:
1. Heartbeat triggered
2. Agent reads HEARTBEAT.md
3. Executes `check_budget` or `list_elevation_requests`
4. Tool returns empty/no content
5. Framework crashes on .filter()

## Next Steps
1. [ ] Restart crashed workers after framework fix
2. [ ] Audit all tools for empty response handling
3. [ ] Add null-safety guards to framework tool processing
4. [ ] Test with check_budget, list_elevation_requests, others

## Reporter
Beta Manager (coding specialist)
Analysis timestamp: 2026-03-08 15:20 CDT
