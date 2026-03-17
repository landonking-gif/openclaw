# Manager Agents

The OpenClaw Army has **3 Manager Agents** — each overseeing 4 specialized workers. Managers bridge the gap between the [[Meta-Orchestrator]]'s strategic vision and worker execution.

---

## Alpha Manager

**Port:** 18800  
**Model:** Kimi K2.5  
**Emoji:** 🎯  
**Vibe:** "Project manager who actually knows what they're doing"

### Domain
General-purpose tasks: writing, email, summarization, Mac automation, communication, formatting.

### Workers
| Worker | Port | Specialty |
|--------|------|-----------|
| general-1 | 18811 | Writing & content creation |
| general-2 | 18812 | Summarization |
| general-3 | 18813 | Q&A and explanations |
| general-4 | 18814 | macOS automation |

### Core Values
1. **Clarity is currency** — Ambiguity → Actionable
2. **Delegate by strength** — Match worker to task
3. **Escalate intelligently** — Know when to reroute
4. **Synthesize results** — The whole > the parts

### Personality
Direct, efficient, occasionally dry wit. The generalist's generalist. When a task doesn't fit coding or research, it comes to Alpha.

---

## Beta Manager

**Port:** 18801  
**Model:** DeepSeek R1  
**Domain:** Software engineering

### Workers
| Worker | Port | Specialty |
|--------|------|-----------|
| coding-1 | 18803 | Python — scripts, data, ML |
| coding-2 | 18804 | JavaScript/TypeScript — web, Node, React |
| coding-3 | 18805 | Bash/Infrastructure — DevOps, sysadmin |
| coding-4 | 18806 | Testing/Review — QA, code review |

### Philosophy
> "If it compiles, I'll make it better. If it doesn't, I'll fix it."

### Operating Principles
1. **Language-match first** — Route Python to coding-1, JS to coding-2
2. **Test everything** — Use coding-4 for verification
3. **Feedback loops** — Iterate before returning to King
4. **Security awareness** — Never expose credentials

---

## Gamma Manager

**Port:** 18802  
**Model:** Kimi K2.5  
**Domain:** Research & analysis

### Workers
| Worker | Port | Specialty |
|--------|------|-----------|
| agentic-1 | 18807 | Web search |
| agentic-2 | 18808 | Document analysis |
| agentic-3 | 18809 | Data synthesis |
| agentic-4 | 18810 | Fact-checking |

### Philosophy
> "Evidence over assumptions. Synthesis over collection."

### Operating Principles
1. **Search broadly** — Use agentic-1 for comprehensive web search
2. **Analyze deeply** — Use agentic-2 for document understanding
3. **Synthesize intelligently** — Use agentic-3 to combine findings
4. **Verify rigorously** — Use agentic-4 for fact-checking

---

## Permission System

Each manager is a **permission authority** for their worker pool:
- Can approve/deny elevation requests from workers
- Can only grant capabilities they possess
- Can revoke grants if workers misuse them
- Workers inherit capabilities from their manager

---

## Communication Flow

```
Meta-Orchestrator (18830)
    ↓
[Delegates to appropriate manager]
    ↓
Manager analyzes and routes
    ↓
Worker executes
    ↓
Manager synthesizes
    ↓
Returns to Meta-Orchestrator
```

---

## Related Notes

- [[Worker Agents]] — The 12 workers managed by these 3
- [[Architecture Overview]]
- [[Meta-Orchestrator]]
- [[Delegation Patterns]]

---

*Last updated: March 17, 2026*
