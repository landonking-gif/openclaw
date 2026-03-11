# Learnings — March 7, 2026

## Technical
1. **Cron deduplication** — Gateway should handle this
2. **Free models** — NVAPI kimi-k2.5 = zero cost
3. **Memory alternatives** — File-based when service down
4. **Permission workflow** — Request → Wait → Execute

## Process
1. **Productivity sweeps** — Batch tasks efficiently
2. **Documentation** — Create reference materials
3. **NO_REPLY** — Essential for spam control
4. **Escalation** — Clear paths to managers

## System
1. **Cron failure modes** — Multiple ways to break
2. **Error pollution** — Cron passing its errors
3. **Bundled messages** — Complex trigger patterns
4. **Timestamp mixing** — Schedules not synchronized

## Recommendations
- Add cron validation to gateway
- Implement response rate limiting
- Create error deduplication filter
- Monitor trigger frequency
