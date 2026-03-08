# Budget Impact — Cron Spam

## Token Consumption Analysis
**Date:** 2026-03-07  
**Incident:** Cron duplicate triggers

## Trigger Count (Estimate)
| Period | Triggers | Responses |
|--------|----------|-----------|
| 3-4 PM | ~15 | ~10 |
| 5-7 PM | ~20 | ~15 |
| 7-9 PM | ~10 | ~8 |
| **Total** | **~50** | **~35** |

## Cost Impact
- **Model:** kimi-k2.5 (free via NVAPI)
- **Actual Cost:** $0 (free model)
- **If Paid (claude-3-opus):** ~$15-20
- **If Paid (gpt-4o):** ~$10-15

## Lessons
1. Free models mitigate spam costs
2. NO_REPLY essential for spam control
3. Cron needs redundancy checks

## Prevention
- Single schedule source
- Gateway-level deduplication
- Alert on trigger frequency
