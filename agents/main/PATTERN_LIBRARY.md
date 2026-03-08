# Pattern Library — Reusable Structures

## Documentation Patterns

### Header Pattern
```markdown
# Title
**Date:** YYYY-MM-DD  
**Status:** [Draft|Review|Final]  
**Owner:** Agent-X

## Overview
Brief description

## Details
```

### Table Pattern
```markdown
| Field | Value | Status |
|-------|-------|--------|
| Name | Value | ✅ |
```

### Status Pattern
- ✅ Complete
- ⏳ In Progress
- ⚠️ Blocked
- ❌ Failed

## Report Structures

### Synthesis Report
1. Executive summary
2. Sources table
3. Key findings
4. Conflicts & resolutions
5. Gaps & unknowns
6. Recommendations

### Status Update
1. Current state
2. Last period work
3. Next period plan
4. Blockers

## Naming Conventions
- Files: `kebab-case.md`
- Dates: `YYYY-MM-DD`
- Time: `HH:MM` (24-hour)
- Status: emoji indicators

## Variables
- `{{DATE}}` — Current date
- `{{TIME}}` — Current time
- `{{AGENT}}` — Agent name
- `{{STATUS}}` — Task status

## Checklist Patterns
- Daily: Startup, work, shutdown
- Weekly: Review, archive, learn
- Session: Start, process, end
