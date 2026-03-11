# System Issues Log — General-2 Observation Post
*Tracking issues observed by Kael during idle cycles*

## 🔴 Critical (Blocking)

### Memory Service Down
- **Status:** 🔴 Down since 2026-03-06
- **Symptoms:** 
  - OpenAI 401 (auth) and 422 (validation) errors
  - `diary`, `reflect`, `memory_commit` tools fail
  - Agents losing cross-session persistence
- **Impact:** All agents affected — no long-term memory
- **Suspected Cause:** Invalid `memory.openaiApiKey` in config
- **Suggested Fix:** Landon to verify API key and billing status

### Permission Broker Errors
- **Status:** 🔴 Broken
- **Symptoms:** `toLowerCase` errors on `request_elevation`
- **Impact:** Cannot elevate permissions — workers stuck
- **Repro:** Any `request_elevation` call

---

## 🟠 High (Workaround Required)

### Cron Burst Pattern
- **Status:** 🟠 Intermittent
- **Symptoms:** 4x duplicate triggers within 10 seconds
- **First Seen:** 2026-03-07 01:19 AM
- **Impact:** Duplicate reminder spam
- **Notes:** Pattern: `01:19:11 → 01:19:12 → 01:34:12`

### GitHub Sync 410 Errors
- **Status:** 🟠 Intermittent
- **Symptoms:** "410 status code" on sync
- **Impact:** Potential stale codebases

---

## 🟡 Medium (Monitoring)

### General-2 Blocked Tasks
- **Status:** 🟡 Need Elevation
- **Tasks:** 
  - Audit sibling agent memory files
  - Cross-workspace log analysis
- **Blocked By:** No `exec` permission

---

## 📊 Health Dashboard
| Service | Status | Last Check |
|---------|--------|------------|
| Core Tools | 🟢 | 2026-03-07 06:20 |
| File I/O | 🟢 | 2026-03-07 06:20 |
| Skill Access | 🟢 | 2026-03-07 06:20 |
| Memory Service | 🔴 | 2026-03-07 01:38 |
| Permission Broker | 🔴 | 2026-03-07 01:38 |
| Cron Jobs | 🟠 | 2026-03-07 01:34 |

---

## 🔧 Recommended Actions (for Landon)

1. **Fix Memory Service:**
   ```bash
   openclaw config get memory.openaiApiKey
   # Verify key is valid at https://platform.openai.com
   ```

2. **Check Permission Broker:**
   ```bash
   openclaw logs permission-broker
   # Look for toLowerCase stack traces
   ```

3. **Cron Investigation:**
   ```bash
   openclaw cron list
   # Check for duplicate job entries
   ```

---
*Last updated: 2026-03-07 06:20 AM by Kael*
