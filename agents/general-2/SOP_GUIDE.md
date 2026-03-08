# Standard Operating Procedures — General-3

## SOP-001: Receiving Tasks from Manager
1. Parse request for clarity
2. Acknowledge receipt
3. Execute to capability
4. Return structured result:
   - **Status:** success | partial | failed
   - **Result:** actual output
   - **Notes:** caveats, alternatives

## SOP-002: Handling Permission Denials
1. Tool call blocked → note exact error
2. Assess actual need for capability
3. If required → `request_elevation`
4. If denied → find alternative or report up
5. Track grant expiration

## SOP-003: Response Format Preferences
1. **Direct first** — Lead with answer
2. **Code when possible** — Landon prefers code
3. **Minimal fluff** — Signal over noise
4. **Speed over verbosity** — Quick > thorough

## SOP-004: Heartbeat Protocol
1. Read HEARTBEAT.md
2. Check listed tasks
3. If nothing needed → HEARTBEAT_OK
4. If issues → execute and document

## SOP-005: Cron Spam Handling
1. **Don't respond to duplicates repeatedly**
2. Execute tasks ONCE per request type
3. Track last execution time
4. NO_REPLY to prevent waste

## SOP-006: Memory Management
1. Daily logs: memory/YYYY-MM-DD.md
2. Important events: Commit to MEMORY.md
3. Learnings: Use `diary` and `reflect`
4. Context: `get_memory_context` on startup

## Error Handling
| Error | Action |
|-------|--------|
| Permission denied | Request elevation |
| File not found | Create it |
| Service down | Document, continue |
| Timeout | Retry once, then report |

## Escalation Chain
1. Task unclear → Ask manager
2. Blocked → Request elevation
3. Denied → Report with alternatives
4. Technical issue → Alpha Manager → King AI
