# King AI v2 — Agent Capability Matrix

> **System:** ai_final (16-Agent Orchestration)  
> **Version:** 2.0  
> **Last Updated:** 2026-03-09  
> **Tags:** #ai_final #capabilities #agents #matrix #reference

---

## Quick Reference

| Tier | Agents | Total | Purpose |
|------|--------|-------|---------|
| **Command** | King AI | 1 | Central coordination |
| **Management** | Alpha, Beta, Gamma, Delta | 4 | Domain management |
| **Workers** | *-1 through *-4 | 16 | Task execution |
| **Services** | Memory, Permission, Vault, Orchestrator | 4 | Infrastructure |

---

## Manager Capabilities

### Alpha Manager (18800) — General Tasks
| Capability | Level | Description |
|------------|-------|-------------|
| Task Synthesis | ⭐⭐⭐⭐⭐ | Combines worker outputs into coherent results |
| Content Polish | ⭐⭐⭐⭐⭐ | Rewrites and improves responses |
| Cross-domain Routing | ⭐⭐⭐⭐ | Delegates to specialized managers |
| Worker Coordination | ⭐⭐⭐⭐⭐ | Manages 4 general-purpose workers |
| Escalation | ⭐⭐⭐⭐ | Knows when to reroute tasks |
| **Tools** | File ops, Web search, Browser, TTS, Image analysis |
| **Memory** | Full access (all tiers) |
| **Permissions** | Approve/deny/revoke worker elevations |

### Beta Manager (18801) — Coding/PRD Implementation
| Capability | Level | Description |
|------------|-------|-------------|
| Code Architecture | ⭐⭐⭐⭐⭐ | Design patterns, system design |
| PRD Parsing | ⭐⭐⭐⭐⭐ | Extracts requirements from documents |
| Code Review | ⭐⭐⭐⭐ | Reviews worker-generated code |
| Testing Strategy | ⭐⭐⭐⭐ | Plans test coverage |
| Deployment | ⭐⭐⭐ | CI/CD pipeline management |
| **Tools** | Coding agent, Git, File ops, Exec |
| **Skills** | MCP servers, Coding agents |

### Gamma Manager (18802) — Research
| Capability | Level | Description |
|------------|-------|-------------|
| Deep Research | ⭐⭐⭐⭐⭐ | Multi-source investigation |
| Web Search | ⭐⭐⭐⭐⭐ | Brave API expertise |
| Page Fetching | ⭐⭐⭐⭐ | Browser automation |
| Synthesis | ⭐⭐⭐⭐⭐ | Combines findings into insights |
| Verification | ⭐⭐⭐⭐ | Cross-checks sources |
| **Tools** | Web search, Web fetch, Browser |
| **Skills** | Blogwatcher, Summarizer |

### Delta Manager (18803) — Agentic Execution
| Capability | Level | Description |
|------------|-------|-------------|
| Goal Planning | ⭐⭐⭐⭐⭐ | Breaks objectives into subtasks |
| Autonomous Execution | ⭐⭐⭐⭐ | Self-directed task completion |
| Iteration | ⭐⭐⭐⭐⭐ | Refines based on feedback |
| Reflection | ⭐⭐⭐⭐⭐ | Learns from outcomes |
| Tool Chaining | ⭐⭐⭐⭐ | Combines multiple tools |
| **Tools** | All available (enterprise/reasoning enabled) |
| **Skills** | Computer control, Coding agents |

---

## Worker Capabilities

### Alpha Workers (General Domain)

| Agent | Port | Specialty | Primary Tools | Secondary Skills |
|-------|------|-----------|---------------|------------------|
| **general-1** | 18811 | Writing/Content | File ops, TTS | Voice storytelling |
| **general-2** | 18812 | Summarization | Web fetch, Summarize skill | Transcription |
| **general-3** | 18813 | Q&A/Analysis | Web search, Memory query | Question answering |
| **general-4** | 18814 | Mac Automation | Exec (elevated), File ops | Apple Notes, Reminders |

### Beta Workers (Coding Domain)

| Agent | Port | Specialty | Primary Tools | Secondary Skills |
|-------|------|-----------|---------------|------------------|
| **coding-1** | 18821 | Code Generation | Coding agent, File ops | Template generation |
| **coding-2** | 18822 | Code Review | Coding agent, Review | Style checking |
| **coding-3** | 18823 | Debugging | Exec, File ops | Log analysis |
| **coding-4** | 18824 | Refactoring | Coding agent, File ops | Code modernization |

### Gamma Workers (Research Domain)

| Agent | Port | Specialty | Primary Tools | Secondary Skills |
|-------|------|-----------|---------------|------------------|
| **research-1** | 18831 | Deep Search | Web search, Browser | Multi-source hunting |
| **research-2** | 18832 | Analysis | Web fetch, Summarize | Pattern extraction |
| **research-3** | 18833 | Synthesis | Memory commit, File ops | Reporting |
| **research-4** | 18834 | Verification | Web search, Browser | Fact-checking |

### Delta Workers (Agentic Domain)

| Agent | Port | Specialty | Primary Tools | Secondary Skills |
|-------|------|-----------|---------------|------------------|
| **agentic-1** | 18841 | Planning | Planning tools, Memory | Goal decomposition |
| **agentic-2** | 18842 | Execution | Exec (elevated), Browser | Autonomous actions |
| **agentic-3** | 18843 | Validation | File ops, Coding agent | Output checking |
| **agentic-4** | 18844 | Reflection | Diary, Reflect, Memory | Learning capture |

---

## Skill Matrix

| Skill | Alpha | Beta | Gamma | Delta |
|-------|-------|------|-------|-------|
| **Writing** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Coding** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Research** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Autonomy** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Analysis** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Synthesis** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## Tool Access Levels

| Tool Category | Alpha | Beta | Gamma | Delta | King AI |
|---------------|-------|------|-------|-------|---------|
| **File Operations** | Full | Full | Read | Full | Full |
| **Exec (shell)** | Standard | Elevated | Standard | Elevated | Full |
| **Web Search** | Full | Limited | Full | Limited | Full |
| **Browser Control** | Standard | Standard | Full | Full | Full |
| **Coding Agents** | X | Full | X | Full | Full |
| **Memory Service** | Full | Full | Full | Full | Full |
| **Reasoning Patterns** | Standard | Standard | Standard | Enterprise | Enterprise |

---

## Performance Characteristics

| Worker | Avg Latency | Throughput | Error Rate |
|--------|-------------|------------|------------|
| general-* | ~2s | Medium | <2% |
| coding-* | ~10s | Low | <5% |
| research-* | ~5s | High | <3% |
| agentic-* | Variable | Low | <8% |

---

## Related Documents
- [[01-architecture-overview]] — System architecture and hierarchy
- [[03-lifecycle-states]] — Task lifecycle documentation
- [[04-risk-profiles]] — Risk assessment framework
- [[05-integration-mapping]] — External API integrations

---
*Part of the ai_final Knowledge Vault*  
*Agent: alpha-manager*  
*Classification: system/capabilities*
