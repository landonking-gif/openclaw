---
title: King AI v2 - System Documentation
description: Complete technical reference for the ai_final agent orchestration hierarchy
tags:
  - type/documentation
  - system/king-ai-v2
  - status/active
  - version/v2.0
created: 2026-03-17
updated: 2026-03-17
author: alpha-manager
---

# King AI v2 Documentation 🎯

> *"I am the planner, not the doer. I see the whole board and move the pieces."*

## Navigation

- [[king-ai-v2-documentation#Architecture Overview|Architecture]]
- [[king-ai-v2-documentation#Agent Capability Matrix|Capability Matrix]]
- [[king-ai-v2-documentation#Business Lifecycle|Task Lifecycle]]
- [[king-ai-v2-documentation#Risk Profiles|Risk Profiles]]
- [[king-ai-v2-documentation#Integration Mapping|Integrations]]

---

## Architecture Overview

King AI v2 implements a **three-tier hierarchical orchestration pattern** designed for complex multi-domain task execution. Unlike simple router-based systems, King AI acts as a strategic planner that decomposes tasks, manages dependencies, and synthesizes outputs from specialized manager teams.

### System Philosophy

The architecture follows the principle: **"Plan before acting"**. King AI does not merely classify and route—it creates comprehensive execution plans with explicit phase dependencies, distributes work to domain managers, tracks progress, and synthesizes final outputs from distributed results.

### Hierarchical Structure

```mermaid
graph TB
    K[King AI<br/>Port 18789<br/>Meta-Orchestrator]
    
    K --> A[Alpha Manager<br/>Port 18800<br/>General Tasks]
    K --> B[Beta Manager<br/>Port 18801<br/>Coding]
    K --> G[Gamma Manager<br/>Port 18802<br/>Research]
    
    A --> A1[general-1<br/>18811<br/>Writing]
    A --> A2[general-2<br/>18812<br/>Summarization]
    A --> A3[general-3<br/>18813<br/>Q&A]
    A --> A4[general-4<br/>18814<br/>Mac Automation]
    
    B --> B1[coding-1<br/>18803<br/>Python]
    B --> B2[coding-2<br/>18804<br/>JavaScript]
    B --> B3[coding-3<br/>18805<br/>Bash/DevOps]
    B --> B4[coding-4<br/>18806<br/>Testing]
    
    G --> G1[agentic-1<br/>18807<br/>Web Search]
    G --> G2[agentic-2<br/>18808<br/>Document Analysis]
    G --> G3[agentic-3<br/>18809<br/>Data Synthesis]
    G --> G4[agentic-4<br/>18810<br/>Fact-Checking]
    
    style K fill:#e1f5e1,stroke:#2e7d32,stroke-width:3px
    style A fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style B fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style G fill:#fff3e0,stroke:#e65100,stroke-width:2px
```

### Communication Flow

```mermaid
sequenceDiagram
    participant User
    participant King as King AI (18789)
    participant Orchestrator as Orchestrator API (18830)
    participant Alpha as Alpha Manager (18800)
    participant Beta as Beta Manager (18801)
    participant Gamma as Gamma Manager (18802)
    participant Workers as Worker Agents
    participant Memory as Memory Service (18820)
    
    User->>King: Complex Task
    King->>Orchestrator: POST /plan
    Orchestrator-->>King: Decomposed Plan
    
    King->>Memory: Commit plan context
    
    par Phase 1: Research
        King->>Gamma: Delegate research subtasks
        Gamma->>Workers: Distribute to agentic-*
        Workers-->>Gamma: Results
        Gamma-->>King: Researched findings
    and Phase 2: Implementation
        King->>Beta: Delegate coding subtasks
        Beta->>Workers: Distribute to coding-*
        Workers-->>Beta: Code/output
        Beta-->>King: Implementation complete
    and Phase 3: Communication
        King->>Alpha: Delegate synthesis/delivery
        Alpha->>Workers: Distribute to general-*
        Workers-->>Alpha: Drafted output
        Alpha-->>King: Final package
    end
    
    King->>King: Synthesize all outputs
    King->>Memory: Commit final result
    King-->>User: Coherent response
```

### Data Flow Architecture

```mermaid
flowchart LR
    subgraph Tier1["Tier 1: Redis (Hot)"]
        T1[Recent Context<br/>Last 100 interactions<br/>Sub-second access]
    end
    
    subgraph Tier2["Tier 2: PostgreSQL (Warm)"]
        T2[Session Summaries<br/>Cross-session learning<br/>Minutes-hours range]
    end
    
    subgraph Tier3["Tier 3: ChromaDB (Cold)"]
        T3[Long-term Knowledge<br/>Vector-indexed<br/>Semantic search]
    end
    
    Agents[
        All 16 Agents<br/>Port 18820
    ]
    
    Agents <-->|Read/Write| T1
    Agents -->|Commit| T2
    Agents -->|Query| T3
    T2 -.->|Archive| T3
    
    KB[(Knowledge Vault<br/>Port 18850<br/>Obsidian)]
    Agents <-->|HTTP API| KB
    
    style T1 fill:#ffebee,stroke:#c62828
    style T2 fill:#fff8e1,stroke:#f9a825
    style T3 fill:#e8f5e9,stroke:#2e7d32
```

---

## Agent Capability Matrix

| Agent | Port | Reports To | Domain | Specialty | Primary Tools | Restrictions |
|-------|------|------------|--------|-----------|---------------|--------------|
| **King AI** | 18789 | — | Orchestration | Strategic Planning | `sessions_send`, `memory_*`, `diary`, `reflect` | Cannot execute directly; plans only |
| **Alpha Manager** | 18800 | 18789 | General | Task Synthesis | `sessions_send` to workers, `memory_*` | No shell execution |
| **Beta Manager** | 18801 | 18789 | Coding | Code Coordination | `sessions_send`, code review | No direct coding |
| **Gamma Manager** | 18802 | 18789 | Research | Research Coordination | `sessions_send`, synthesis | No direct search |
| **general-1** | 18811 | 18800 | Writing | Technical Writing | `read`, `write`, `edit` | No shell, sandboxed FS |
| **general-2** | 18812 | 18800 | Summarization | Content Condensation | `read`, `web_fetch`, `summarize` | No shell, sandboxed FS |
| **general-3** | 18813 | 18800 | Q&A | Question Answering | `read`, `memory_search`, `get_memory_context` | No shell, sandboxed FS |
| **general-4** | 18814 | 18800 | Automation | Mac Automation | `exec` (elevated via approval), `read`, `write` | Requires elevation for exec |
| **coding-1** | 18803 | 18801 | Coding | Python Development | `read`, `write`, `edit`, `exec` (via approval) | No shell without approval |
| **coding-2** | 18804 | 18801 | Coding | JavaScript/TypeScript | `read`, `write`, `edit`, `exec` (via approval) | No shell without approval |
| **coding-3** | 18805 | 18801 | Coding | Bash/Infrastructure | `read`, `write`, `edit`, `exec` (via approval) | No shell without approval |
| **coding-4** | 18806 | 18801 | Coding | Testing/Review | `read`, `edit`, `sessions_spawn` | No shell without approval |
| **agentic-1** | 18807 | 18802 | Research | Web Search | `web_search`, `web_fetch` | No shell, sandboxed FS |
| **agentic-2** | 18808 | 18802 | Research | Document Analysis | `web_fetch`, `read`, `summarize` | No shell, sandboxed FS |
| **agentic-3** | 18809 | 18802 | Research | Data Synthesis | `read`, `memory_search`, `reflect` | No shell, sandboxed FS |
| **agentic-4** | 18810 | 18802 | Research | Fact-Checking | `web_search`, `web_fetch`, `memory_search` | No shell, sandboxed FS |

### Permission Requirements by Role

| Role | Cross-Agent Messaging | Shell Execution | Filesystem Scope | Reasoning Patterns | Elevation Authority |
|------|----------------------|----------------|------------------|-------------------|---------------------|
| **King AI** | ✅ All agents | ✅ Full | ✅ Unrestricted | ✅ All three | ✅ Can grant (via escalation) |
| **Managers** | ✅ Own workers only | ✅ Limited | ✅ Unrestricted | ✅ All three | ✅ Can approve workers |
| **Workers** | ❌ Manager only | 🟡 Via elevation | 🟡 Own workspace only | ✅ All three | ❌ Cannot grant |

---

## Business Lifecycle

### Task State Machine

```mermaid
stateDiagram-v2
    [*] --> Received: User Request
    
    Received --> Analyzing: King AI receives
    
    Analyzing --> Planning: Task decomposed
    Analyzing -->