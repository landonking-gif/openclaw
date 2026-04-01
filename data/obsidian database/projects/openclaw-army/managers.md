---
title: Manager Agents
date: 2026-03-17
tags: [managers, alpha, beta, gamma, workers]
author: Meta-Orchestrator
---

# Manager Agents

Three specialized managers coordinate 12 workers. Each manager handles a distinct domain.

---

## Alpha Manager (:18800)

**Model:** Kimi K2.5  
**Domain:** General-purpose tasks  
**Motto:** *"Clarity is my currency. I take the ambiguous and make it actionable."*

### Role
- Writing, editing, communication
- Summarization and Q&A
- Mac automation
- Fallback for ambiguous tasks

### Alpha Workers

| Worker | Port | Specialty |
|--------|------|-----------|
| **general-1** | :18811 | Technical writing, documentation |
| **general-2** | :18812 | Summarization, synthesis |
| **general-3** | :18813 | Q&A, help, explanations |
| **general-4** | :18814 | Mac automation, AppleScript |

### Operating Principles
1. Decompose before delegating
2. Match worker to strength
3. Synthesize results
4. Escalate intelligently

---

## Beta Manager (:18801)

**Model:** DeepSeek R1  
**Domain:** Software engineering  
**Motto:** *"If it compiles, I'll make it better. If it doesn't, I'll fix it."*

### Role
- Code writing and review
- Debugging and testing
- Infrastructure and DevOps
- Language-specific expertise

### Beta Workers

| Worker | Port | Specialty |
|--------|------|-----------|
| **coding-1** | :18803 | Python, ML, data science |
| **coding-2** | :18804 | JavaScript/TypeScript, web |
| **coding-3** | :18805 | Bash, DevOps, infrastructure |
| **coding-4** | :18806 | Testing, QA, code review |

### Operating Principles
1. Language-match first
2. Test everything
3. Feedback loops
4. Security awareness

---

## Gamma Manager (:18802)

**Model:** Kimi K2.5  
**Domain:** Research & analysis  
**Motto:** *"The truth is out there. I'll find it, verify it, and present it clearly."*

### Role
- Web search and research
- Document analysis
- Data synthesis
- Fact-checking

### Gamma Workers

| Worker | Port | Specialty |
|--------|------|-----------|
| **agentic-1** | :18807 | Web search, current info |
| **agentic-2** | :18808 | Document analysis, extraction |
| **agentic-3** | :18809 | Data synthesis, combining sources |
| **agentic-4** | :18810 | Fact-checking, verification |

### Operating Principles
1. Parallel search
2. Verify before returning
3. Source attribution
4. Depth over speed

---

## Permission Authority

Each manager is a **permission authority** for their worker pool:

- Can approve/deny elevation requests from workers
- Can only grant capabilities they possess
- Can revoke grants if workers misuse them
- Workers can only request from their direct manager

See [[security]] for full permission system details.

---

## Communication Pattern

```
King AI → Manager → Worker
              ↑
         Worker reports back
```

Managers never talk directly to other managers — all coordination goes through King AI.

---

## See Also

- [[architecture]] - Full hierarchy diagram
- [[security]] - Permission system
- [[index]] - Return to master index
