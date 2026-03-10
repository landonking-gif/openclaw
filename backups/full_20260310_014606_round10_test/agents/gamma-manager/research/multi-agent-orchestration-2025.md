# Multi-Agent Orchestration Systems Research Report
**Research Date:** 2026-03-07  
**Focus:** LLM-based multi-agent orchestration (2024-2026)

---

## Executive Summary

The LLM multi-agent orchestration landscape has consolidated around five major frameworks as of early 2026:
1. **Microsoft AutoGen** (v0.4+) — Most mature, now with layered API (Core + AgentChat)
2. **CrewAI** — Opinionated hierarchical crew-based system
3. **LangGraph** — Low-level stateful graph orchestration
4. **OpenAI Agents SDK** — Successor to Swarm, native OpenAI integration
5. **OpenAI Swarm** — Experimental (mostly superseded by Agents SDK)

Microsoft's research (AI Frontiers) has driven key insights on "tool-space interference" — an emerging problem where adding agents/tools can paradoxically reduce performance.

---

## 1. Hierarchical vs Flat Delegation Patterns

### Hierarchy in Practice

**CrewAI (Explicit Hierarchical)**
- **Process Types:** `sequential`, `hierarchical`, `consensual`
- **Hierarchical Process:** Manager LLM coordinates crew, assigns tasks, delegates to workers
- **Source:** https://docs.crewai.com/concepts/process

```python
# CrewAI hierarchical setup
crew = Crew(
    agents=[researcher, writer, editor],
    tasks=[research_task, write_task, edit_task],
    process=Process.hierarchical,  # Enables manager
    manager_llm=ChatOpenAI(model="gpt-4"),
    memory=True  # Uses memory for cross-agent context
)
```

**AutoGen (Flexible — Both Supported)**
- **Flat:** Group chat with round-robin or LLM-based selector
- **Hierarchical:** Nested group chats, Magentic-One pattern (Orchestrator → specialized sub-agents)

**Magentic-One Architecture** (Microsoft Research, 2024-2025):
- **Top-level:** Orchestrator agent
- **Sub-agents:** Coder, Terminal, Web Surfer, File Surfer
- **Pattern:** Vertically integrated, tasks delegated based on capability matching

### Performance Insights

| Pattern | Strengths | Trade-offs |
|---------|-----------|------------|
| **Hierarchical** | Clear accountability, explicit coordination, scalable to large teams | Bottleneck at manager, single point of failure |
| **Flat** | Direct collaboration, lower latency, emergent problem-solving | Coordination overhead, potential conflicts |

**Key Finding (Microsoft Research, Tool-Space Interference study):**
> "Adding more tools can sometimes hurt performance, introducing 'tool-space interference'" — Tyler Payne, Microsoft Research AI Frontiers

**Critical Threshold:** OpenAI recommends <20 tools (API max: 128). Many MCP servers exceed this, causing degraded performance.

**Source:** https://www.microsoft.com/en-us/research/blog/

---

## 2. Agent Communication Protocols

### 2.1 Message Passing (AutoGen Core API)

**Pattern:** Event-driven, pub-sub architecture

```python
# Core concepts: Topics, Subscriptions, Message Handlers
@message_handler
async def handle_message(self, message: MyMessage, ctx: MessageContext):
    await self.publish_message(response, topic_id=DefaultTopicId(type="topic"))
```

**Features:**
- Distributed runtime support
- Cross-language (Python + .NET)
- Type-safe message routing

**Source:** https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/

### 2.2 Shared Memory (LangGraph)

**Pattern:** Centralized state graph with checkpointing

```python
from langgraph.graph import StateGraph

# State is shared across all nodes
class State(TypedDict):
    messages: Annotated[list, add_messages]
    context: dict

graph = StateGraph(State)
```

**Key Capabilities:**
- Durable execution (resumable from failures)
- Human-in-the-loop (inspect/modify state)
- Comprehensive short-term + long-term memory

**Source:** https://langchain-ai.github.io/langgraph/concepts/persistence/

### 2.3 Direct Addressing / Handoffs

**OpenAI Agents SDK:**

```python
# Two primary patterns
triage_agent = Agent(
    name="Triage",
    instructions="Route to appropriate specialist",
    handoffs=[booking_agent, refund_agent]  # Decentralized
)

# Manager pattern (agents as tools)
customer_agent = Agent(
    name="Customer",
    tools=[booking_agent.as_tool(), refund_agent.as_tool()]  # Centralized
)
```

**AutoGen Handoff Pattern:**
- Delegate tools allow agents to pass control to other agents
- Maintains conversation history across handoff
- Implemented via special tool calls

**Source:** 
- https://openai.github.io/openai-agents-python/agents/
- https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/handoffs.html

### 2.4 Protocol Comparison

| Protocol | Framework | Best For | Scalability |
|----------|-----------|----------|-------------|
| **Message Passing** | AutoGen Core | Distributed systems, complex workflows | High |
| **Shared State** | LangGraph | Stateful workflows, human-in-the-loop | Medium |
| **Function Calls** | OpenAI SDK | Simple handoffs, rapid prototyping | Low-Medium |
| **Crew Process** | CrewAI | Team-based task delegation | Medium |

---

## 3. Framework Deep Dives

### 3.1 AutoGen (Microsoft)

**Version:** v0.4+ (stable)

**Architecture:** Three-layer design
1. **Core API:** Message passing, event-driven, distributed runtime
2. **AgentChat API:** Opinionated multi-agent patterns (group chat, two-agent)
3. **Extensions API:** Third-party integrations (MCP, OpenAI, etc.)

**Key Patterns:**
- **Group Chat:** Round-robin or LLM-based speaker selection
- **Handoffs:** Agent-to-agent delegation with history preservation
- **Magentic-One:** Research-grade generalist agent team

**Source:** https://github.com/microsoft/autogen

### 3.2 CrewAI

**Design Philosophy:** "Crews" of role-based agents

**Process Types:**
- **Sequential:** Tasks execute in order
- **Hierarchical:** Manager LLM coordinates and delegates
- **Consensual:** Agents vote on task completion

**Memory System:**
- Short-term: Current task context
- Long-term: Cross-session knowledge
- Entity: Key facts about entities mentioned

**Source:** https://docs.crewai.com/

### 3.3 LangGraph

**Philosophy:** "Pregel-inspired" graph computation for agents

**Key Differentiators:**
- **Durable execution:** Automatic resumption from failures
- **Human interrupts:** Pause/modify/resume any state
- **Streaming:** Real-time output from any node
- **Subgraphs:** Modular, composable agent components

**Multi-Agent Patterns:**
1. **Supervisor:** Central coordinator (hierarchical)
2. **Collaboration:** Agents hand off/have shared state (flat)
3. **Custom graphs:** Fully custom routing logic

**Source:** https://langchain-ai.github.io/langgraph/

### 3.4 OpenAI Agents SDK (ex-Swarm)

**Successor to:** Swarm (experimental, 2024)

**Core Concepts:**
- **Agents:** LLM + instructions + tools + handoffs
- **Runner:** Orchestrates execution
- **Guardrails:** Input/output validation
- **Tracing:** Built-in observability

**Multi-Agent Patterns:**
1. **Manager (agents as tools):** Central controller with sub-agents as callable tools
2. **Handoffs:** Decentralized; agents decide when to transfer control

**Source:** https://openai.github.io/openai-agents-python/

---

## 4. Emerging Patterns & Research

### 4.1 Tool-Space Interference

**Problem:** Adding agents/tools reduces performance unexpectedly

**Root Causes (Microsoft Research):**
1. Tool name collisions ("search", "web_search", "google_search")
2. Too many tools (>20 threshold)
3. Long tool responses (>128k tokens overflow context)
4. Model-specific prompting mismatches

**Recommendations:**
- Namespace tools uniquely
- Limit tools to <20 per agent
- Truncate tool responses
- Version MCP servers by tested models

**Source:** https://github.com/microsoft/MCP-Interviewer

---

## 5. Comparison Matrix

| Dimension | AutoGen v0.4+ | CrewAI | LangGraph | OpenAI