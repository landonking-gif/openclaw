# Multi-Agent Error Handling & Resilience Patterns
**Research Date:** 2026-03-07  
**Focus:** Error handling, retry strategies, circuit breaker patterns for agent swarms

---

## Executive Summary

Contemporary LLM multi-agent systems (2024-2026) implement resilience through three primary mechanisms:
1. **Guardrails** — Input/output validation with tripwires (OpenAI Agents SDK, LangGraph)
2. **Durable Execution** — Checkpointing and resumption (LangGraph, AutoGen v0.4+)
3. **Controller Patterns** — Exception aggregation and failure isolation (AutoGen Core API)

**Key Research Finding:** Microsoft AutoGen v0.4 introduces message-level error propagation where exceptions bubble up through `send_message()` calls, enabling sophisticated retry logic at the orchestration layer.

**Source:** https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/message-and-communication.html

---

## 1. Guardrail-Based Error Prevention

### 1.1 OpenAI Agents SDK Guardrails

**Execution Modes:**
- **Parallel (default):** Guardrail runs concurrently with agent; tripwire cancels execution mid-stream
- **Blocking:** Guardrail completes before agent starts; prevents token waste

**Three Guardrail Types:**
1. **Input Guardrails:** Run on initial user input only (first agent)
2. **Output Guardrails:** Run on final agent output only (last agent)
3. **Tool Guardrails:** Wrap every function tool invocation

**Implementation Pattern:**

```python
from agents import Agent, input_guardrail, GuardrailFunctionOutput, Runner
from pydantic import BaseModel

class ValidOutput(BaseModel):
    is_valid: bool
    reasoning: str

@input_guardrail
async def validate_input(ctx, agent, input):
    result = await Runner.run(validation_agent, input)
    return GuardrailFunctionOutput(
        tripwire_triggered=not result.final_output.is_valid,
        output_info=result.final_output
    )

agent = Agent(
    name="processor",
    instructions="Process user requests",
    input_guardrails=[validate_input]  # Parallel by default
)

# Blocking mode for cost optimization:
agent = Agent(
    input_guardrails=[validate_input],
    run_in_parallel=False  # Blocks agent execution
)
```

**Tool Guardrail Pattern (Pre/Post execution):**

```python
from agents import tool_input_guardrail, tool_output_guardrail, ToolGuardrailFunctionOutput

@tool_input_guardrail
def pre_check(data):
    args = json.loads(data.context.tool_arguments or "{}")
    if contains_sensitive_data(args):
        return ToolGuardrailFunctionOutput.reject_content("Blocked: sensitive data")
    return ToolGuardrailFunctionOutput.allow()

@tool_output_guardrail  
def post_check(data):
    if "error" in str(data.output):
        return ToolGuardrailFunctionOutput.reject_content("Tool returned error")
    return ToolGuardrailFunctionOutput.allow()

@function_tool(
    tool_input_guardrails=[pre_check],
    tool_output_guardrails=[post_check]
)
def risky_operation(param: str) -> str:
    """May fail or return sensitive data."""
    pass
```

**Source:** https://openai.github.io/openai-agents-python/guardrails/

---

## 2. Durable Execution & Persistence

### 2.1 LangGraph Durable Execution

**Core Capabilities:**
- **Automatic resumption** from failures
- **Human interrupts** — inspect/modify/resume any state
- **Streaming** — real-time output from any node
- **Comprehensive memory** — short-term + long-term + thread-scoped

**Checkpointer Pattern:**

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

# Persistence enables durability
workflow = StateGraph(State)
workflow.add_node("agent", agent_node)
workflow.add_edge("agent", END)

# MemorySaver for single-machine durability
app = workflow.compile(checkpointer=MemorySaver())

# PostgreSQL for production durability
from langgraph.checkpoint.postgres import PostgresSaver
app = workflow.compile(checkpointer=PostgresSaver(conn))
```

**Resume from interruption:**
```python
config = {"configurable": {"thread_id": "conversation-123"}}

# Human interrupts at any step
for event in app.stream(input, config):
    if human_wants_to_interrupt(event):
        # State is automatically checkpointed
        break

# Later: resume from exact checkpoint
for event in app.stream(None, config, stream_mode="updates"):
    yield event
```

**Source:** https://langchain-ai.github.io/langgraph/concepts/persistence/

---

## 3. Retry Strategies & Exponential Backoff

### 3.1 Framework-Native Support Matrix

| Framework | Native Retry | Exponential Backoff | Circuit Breaker |
|-----------|-----------|--------------------|:---------------:|
| **AutoGen v0.4** | ✅ Message-level propagation | ⚠️ Manual `send_message()` wrapper | ⚠️ Custom implementation |
| **LangGraph** | ✅ Tool/node retries via config | ✅ LangChain `retry_with_exponential_backoff` | ⚠️ Custom node |
| **CrewAI** | ✅ Task-level retries | ⚠️ Via `max_retries` parameter | ❌ |
| **OpenAI SDK** | ⚠️ HTTP-level | ✅ Internal HTTP retry | ❌ |

### 3.2 AutoGen Error Propagation Pattern

**Key Mechanism:** Exceptions propagate through `send_message()` calls

```python
from autogen_core import AgentId

class Orchestrator(RoutedAgent):
    @message_handler
    async def on_task(self, message: TaskMessage, ctx: MessageContext):
        target = AgentId("worker", self.id.key)
        
        # Try with exponential backoff
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.send_message(message, target)
                return response
            except RetryableError as e:
                wait = 2 ** attempt + random.uniform(0, 1)
                await asyncio.sleep(wait)
            except FatalError:
                # Propagate to caller
                raise
                
        raise MaxRetriesExceeded("Worker failed after backoff")
```

**Note:** As per AutoGen Core docs: 
> "If the invoked agent raises an exception while the sender is awaiting, the exception will be propagated back to the sender."

**Source:** https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/message-and-communication.html

### 3.3 LangGraph Retry Configuration

```python
from langgraph.graph import StateGraph
from langgraph.pregel import RetryPolicy

workflow = StateGraph(State)

# Node-level retry policy
workflow.add_node(
    "risky_agent",
    risky_agent_node,
    retry=RetryPolicy(
        max_attempts=3,
        backoff_factor=2.0,  # Exponential: 1s, 2s, 4s
        max_interval=60.0,
        jitter=True
    )
)
```

---

## 4. Circuit Breaker Patterns

### 4.1 Implementation Approach

**State Machine:**
- `CLOSED` — Normal operation, requests pass through
- `OPEN` — Failure threshold exceeded, requests blocked fast-fail
- `HALF_OPEN` — Testing recovery with limited traffic

**Recommended for Multi-Agent Systems:**
1. **Per-agent circuit breakers** — Individual agent health
2. **Per-tool circuit breakers** — External service protection
3. **Global swarm circuit breaker** — Cascading failure prevention

### 4.2 Pseudo-Implementation for Agent Swarm

```python
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "closed"      # Normal
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open" # Testing

class AgentCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        
    async def call(self, agent, message):
        if self.state ==