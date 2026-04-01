# Worker Agents

The OpenClaw Army has **12 Worker Agents** — 4 under each manager, each with specialized capabilities.

## Alpha Manager Workers

**Domain:** General-purpose tasks  
**Port Range:** 18810-18813

### general-1
**Specialization:** Writing & prose generation

- Long-form content
- Creative writing
- Documentation
- Reports
- Blog posts

### general-2
**Specialization:** Summarization & condensation

- TL;DR generation
- Executive summaries
- Meeting notes
- Article abstracts

### general-3
**Specialization:** Q&A & help desk

- Question answering
- Explanations
- Troubleshooting guides
- How-to responses

### general-4
**Specialization:** macOS automation

- AppleScript execution
- Shortcut creation
- System preferences
- File operations

---

## Beta Manager Workers

**Domain:** Software engineering  
**Port Range:** 18814-18817

### coding-1
**Specialization:** Python development

- Python scripts
- FastAPI/Flask apps
- Data processing
- ML pipelines

### coding-2
**Specialization:** JavaScript/TypeScript

- Frontend development
- Node.js backends
- React/Vue components
- Type definitions

### coding-3
**Specialization:** Bash/DevOps

- Shell scripts
- CI/CD pipelines
- Docker configurations
- Infrastructure as code

### coding-4
**Specialization:** Testing & QA

- Unit tests
- Integration tests
- Test automation
- Bug reproduction

---

## Gamma Manager Workers

**Domain:** Research & analysis  
**Port Range:** 18818-18821

### agentic-1
**Specialization:** Web search

- Google searches
- News aggregation
- Trend analysis
- Source finding

### agentic-2
**Specialization:** Document analysis

- PDF parsing
- Contract review
- Policy analysis
- Legal document review

### agentic-3
**Specialization:** Data synthesis

- Data integration
- Report generation
- Visualization
- Dashboard creation

### agentic-4
**Specialization:** Fact-checking

- Claim verification
- Source validation
- Cross-reference checking
- Bias detection

---

## Worker Communication

Workers communicate via:
- **Manager routing** — Work comes through managers
- **Direct messaging** — `agent_message()` to any worker
- **Redis pub/sub** — [[service_mesh]] for events
- **Memory service** — Shared context

## Worker Files

Each worker has:

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Who am I |
| `SOUL.md` | Behavioral rules |
| `MEMORY.md` | Conversation history |
| `AGENTS.md` | Peer capabilities |
| `TOOLS.md` | Available tools |
| `USER.md` | User preferences |

## Scaling

Workers can be:
- **Added** via `register_new_agent()`
- **Monitored** via Agent Registry
- **Restarted** via process watchdog
- **Replaced** by updating manager pools

## Related Notes

- [[Manager Agents]] — Who manages workers
- [[Meta-Orchestrator]] — Who delegates work
- [[Agent Registry]] — Registration & health
- [[Delegation Patterns]] — How work flows

---

**Tags:** #workers #agents #specialization #alpha #beta #gamma
