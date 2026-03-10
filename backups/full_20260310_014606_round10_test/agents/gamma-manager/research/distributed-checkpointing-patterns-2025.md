# Distributed Task Checkpointing & State Persistence Research
**Research Date:** 2026-03-07  
**Focus:** How agents save mid-task state and resume after failures

---

## Executive Summary

Modern workflow engines use four primary checkpointing strategies:

| Engine | Checkpointing Mechanism | Persistence Layer | Recovery Time |
|--------|------------------------|-------------------|---------------|
| **Temporal** | Event sourcing (command → event → history) | Temporal Service + pluggable storage | Replay from last event |
| **Cadence** | Same as Temporal (descendant) | Persistence via Cassandra/MySQL/Postgres | Replay from last event |
| **Airflow** | DAG serialization + task state | Metadata DB (Postgres/MySQL) | Resume from task |
| **LangGraph** | Checkpoint every graph step | Memory/Postgres/Redis/SQLite | Resume from step |
| **CrewAI Flows** | Pydantic state + restart hooks | Manual implementation | User-defined |

**Key Pattern:** Workflow engines separate **orchestration** (what to do) from **execution** (how to do it), enabling transparent failure recovery.

---

## 1. Temporal: Deterministic Replay with Event Sourcing

### 1.1 Core Concept

Temporal implements **Durable Execution** through event sourcing:

1. **Commands** issued by Worker → Temporal Service
2. **Events** recorded durably → Event History
3. **Replay** on failure → code recreates pre-failure state

> "If the Worker crashes, the Worker uses the Event History to replay the code and recreate the state of the Workflow Execution to what it was immediately before the crash. It then resumes progress from the point of failure as if the failure never occurred."

**Source:** https://docs.temporal.io/encyclopedia/event-history

### 1.2 Implementation Pattern

**Python SDK Example:**

```python
from temporalio import workflow
from datetime import timedelta

@workflow.defn(name="AgentTask")
class AgentTask:
    @workflow.run
    async def run(self, agent_input: TaskInput) -> TaskOutput:
        # Step 1: Research agent (checkpointed after activity)
        research_result = await workflow.execute_activity(
            run_research_agent,
            agent_input.query,
            start_to_close_timeout=timedelta(minutes=2),
            # Implicit checkpoint here
        )
        
        # Step 2: Analysis agent (resumes here on failure)
        analysis_result = await workflow.execute_activity(
            run_analysis_agent,
            research_result,
            start_to_close_timeout=timedelta(minutes=3),
        )
        
        return TaskOutput(analysis_result)
```

**Key Requirements:** Workflow code must be **deterministic**:
- No `random`, `datetime.now()`, network calls
- All external operations wrapped in Activities
- Timers via `workflow.sleep()`, not `asyncio.sleep()`

### 1.3 State Recovery Example

```python
# Workflow with async checkpoints
@workflow.defn(name="MultiAgentCrew")
class MultiAgentCrew:
    @workflow.run
    async def run(self, task: str) -> str:
        # Checkpoint after each await
        agent1_result = await workflow.execute_activity(
            agent1.run,
            task,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # State automatically checkpointed here
        agent2_result = await workflow.execute_activity(
            agent2.run,
            agent1_result,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Long-running task with intermediate checkpoint
        await workflow.execute_activity(
            agent3.run,
            agent2_result,
            start_to_close_timeout=timedelta(hours=1),
        )
        
        return agent2_result
```

**On crash:** Temporal detects failed worker, reschedules task on new worker, replays Event History up to last completed Activity, resumes from next Activity.

### 1.4 Event History Structure

```
WorkflowExecutionStarted
WorkflowTaskScheduled
WorkflowTaskStarted
WorkflowTaskCompleted
ActivityTaskScheduled (run_research_agent)
ActivityTaskStarted
ActivityTaskCompleted (result stored)
[Worker crashes here]
[new Worker replays above events without executing Activities]
WorkflowTaskScheduled
ActivityTaskScheduled (run_analysis_agent)  # Resumes here
...
```

**Source:** https://docs.temporal.io/dev-guide/python/foundations

---

## 2. CrewAI Flows: Explicit State Management

### 2.1 Pattern Overview

CrewAI Flows uses **decorator-based** flow control with explicit state:

```python
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

class AgentState(BaseModel):
    task_id: str = ""
    intermediate_results: list = []
    final_result: str = ""

class AgentWorkflow(Flow[AgentState]):
    @start()
    def init_task(self):
        self.state.task_id = str(uuid.uuid4())
        return "task_initialized"
    
    @listen(init_task)
    def run_agent_one(self, _):
        result = agent1.run(self.state.task_id)
        self.state.intermediate_results.append(result)
        return result
    
    @listen(run_agent_one)
    def run_agent_two(self, prev_result):
        result = agent2.run(prev_result)
        self.state.final_result = result
        return result

# Restart on failure: re-instantiate and kickoff
flow = AgentWorkflow()
flow.kickoff()  # Full replay required on crash
```

**Limitation:** No automatic recovery; must implement external checkpointing.

### 2.2 Manual Checkpoint Pattern

```python
import json
from pathlib import Path

class CheckpointableFlow(Flow[AgentState]):
    def save_checkpoint(self, step: str):
        checkpoint = {
            "state": self.state.model_dump_json(),
            "completed_step": step
        }
        Path("checkpoints/").mkdir(exist_ok=True)
        with open(f"checkpoints/{self.state.task_id}.json", "w") as f:
            json.dump(checkpoint, f)
    
    @start()
    def agent_one(self):
        result = agent1.run()
        self.state.task = result
        self.save_checkpoint("agent1_complete")
        return result
    
    @listen(agent_one)
    def agent_two(self, _):
        # On restart, check for checkpoint
        if Path(f"checkpoints/{self.state.task_id}.json").exists():
            with open(f"checkpoints/{self.state.task_id}.json") as f:
                checkpoint = json.load(f)
            if checkpoint["completed_step"] == "agent1_complete":
                return checkpoint["state"]["final_result"]
        
        result = agent2.run(self.state.task)
        self.save_checkpoint("agent2_complete")
        return result
```

**Source:** https://docs.crewai.com/concepts/flows

---

## 3. LangGraph: Step-Level Checkpointing

### 3.1 Checkpoint Interface

LangGraph provides a `Checkpointer` interface for state persistence:

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

# In-memory (single process)
memory_checkpointer = MemorySaver()

# Production: PostgreSQL
import psycopg2
conn = psycopg2.connect("postgresql://user:pass@localhost/db")
pg_checkpointer = PostgresSaver(conn)

# Compile graph with checkpointer
graph = StateGraph(State)
app = graph.compile(checkpointer=pg_checkpointer)

# Every graph node is checkpointed after execution
```

### 3.2 Resumption Pattern

```python
config = {"configurable": {"thread_id": "agent-conv-123"}}

# First run
events = app.stream({"messages": [HumanMessage("Hello")]}, config)
for event in events:
    print(event)

# [Worker crashes here]

# Second run: automatic resume from step 3
# LangGraph loads checkpoint, skips completed steps
checkpoint = {"configurable": {"thread_id": "agent-conv-123"}}
for event in app.stream(None, config):
    # Only events after crash point
    print(event)
```

**Key Feature:** Human-in-the-loop interrupts for long-running tasks:

```python
# Human interrupt at checkpoint
for event in app.stream(input, config):
    if should_interrupt(event):
        # Pause execution here
        break

# Resume later with None
for event in app.stream(None, config, stream_mode="updates"):
    yield event
```

**Source:** https://langchain-ai.github.io/langgraph/concepts/persistence/

---

## 4. Architectural Patterns Comparison

### 4.1 Pattern Matrix

| Checkpoint Type | Deterministic Replay | Granularity | Recovery Speed | Code Changes |
|-----------------|----------------------|-------------|----------------|--------------|
| **Temporal** | Required | Activity boundary | Medium (replay) | Must determinize |
| **LangGraph** | Not required | Graph step | Fast (load state) | Minimal |
| **CrewAI** | Not required | Manual | Manual | Significant |
| **AutoGen** | Not required | Message | Fast (load state) | Minimal |

### 4.2 Deterministic vs Snapshot Checkpointing

**Deterministic (Temporal):**
- Store inputs → Replay code → Rebuild state
- Smaller storage footprint
- Requires determinism constraints
- Universal recovery (any worker)

**Snapshot (LangGraph):**
- Store full state → Load and continue
- Larger storage footprint
- No code constraints
- Faster recovery

### 4.3 Recovery Scenarios

**Scenario 1: Worker Crash During Long LLM Call**

```python
# Temporal
result = await workflow.execute_activity(
    call_llm,
    prompt,
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(maximum_attempts=3)
)
# On crash: Activity timeout detected, retried automatically
# No duplicate LLM calls (idempotent by Activity retry)

# LangGraph
result = await agent.ainvoke(state, config)  
# On crash: Checkpointer saves before LLM call
# Resume: Load checkpoint, retry agent node

# CrewAI Flows
result = agent.run(prompt)
# On crash: Manual checkpoint restore
# Risk of duplicate calls unless manually handled
```

**Scenario 2: Multi-Agent Pipeline with Partial Completion**

```python
# Temporal: Automatic recovery
@workflow.defn(name="MultiAgentPipeline")
class Pipeline:
    @workflow.run
    async def run(self, task):
        r1 = await workflow.execute_activity(agent1.run, task)  # Completed
        r2 = await workflow.execute_activity(agent2.run, r1)      # Failed here
        r3 = await workflow.execute_activity(agent3.run, r2)      # Never started
        return r3
# On restart: r1 replayed (cached), r2 retried, r3 executed

# LangGraph: Automatic via checkpoint
graph.add_node("agent1", agent1_node)
graph.add_node("agent2", agent2_node)  
graph.add_node("agent3", agent3_node)
# On crash at agent2: Resume from agent2 checkpoint

# CrewAI: Requires manual per-step checkpoints
```

---

## 5. Recommended Agent Checkpointing Strategies

### 5.1 Hybrid Pattern: LangGraph + Temporal

```python
# Use LangGraph for agent primitives
# Use Temporal for workflow orchestration

from temporalio import workflow
from langgraph.checkpoint.postgres import PostgresSaver

@workflow.defn(name="CompositeAgentTask")
class CompositeAgentTask:
    @workflow.run
    async def run(self, input: TaskInput) -> Result:
        # LangGraph agent as Activity
        result = await workflow.execute_activity(
            run_langgraph_agent,
            input,
            start_to_close_timeout=timedelta(minutes=30),
        )
        return result

async def run_langgraph_agent(input):
    # Each LangGraph step is checkpointed
    graph = build_agent_graph(
        checkpointer=PostgresSaver(conn)
    )
    result = await graph.ainvoke(...)
    return result
```

### 5.2 Agent-Specific Checkpointing Best Practices

| Agent Type | Checkpoint Strategy | Recommended Engine |
|------------|--------------------:|--------------------|
| **LLM calls** | Before/after each call | LangGraph step |
| **Tool execution** | After success | Activity boundary |
| **Multi-step reasoning** | After each thought | LangGraph node |
| **External API calls** | After response | Temporal Activity |
| **Human-in-loop** | Interactive checkpoint | LangGraph interrupt |

### 5.3 Implementation Checklist

- [ ] Define checkpoint granularity (agent, step, or tool)
- [ ] Choose persistence backend (memory/Postgres/Redis)
- [ ] Implement idempotency for re-executed operations
- [ ] Add timeout handling for long-running agents
- [ ] Configure human interrupt points for review
- [ ] Test recovery with simulated failures
- [ ] Monitor checkpoint size (avoid >10MB payloads)

---

## 6. Key Research Findings

### 6.1 Worker Crash Resilience

All modern frameworks handle worker crashes, but with different semantics:

| Framework | Crash Detection | Auto-Retry | Human Resume |
|-----------|------------------|-----------|--------------|
| **Temporal** | Service-level poll | Yes | Via signal |
| **LangGraph** | Client handled | No (manual) | Yes (interrupts) |
| **CrewAI** | None | No | Manual |

### 6.2 State Size Limits

- **Temporal:** 2MB per Activity, 4MB per gRPC message (recommend <1MB)
- **LangGraph:** ~50MB PostgreSQL checkpoint, 1GB memory checkpoint
- **CrewAI:** User-defined (no framework limit)

---

## Source URLs

1. Temporal Event History: https://docs.temporal.io/encyclopedia/event-history
2. Temporal Python Foundations: https://docs.temporal.io/dev-guide/python/foundations
3. Temporal Workflows Overview: https://docs.temporal.io/workflows
4. CrewAI Flows: https://docs.crewai.com/concepts/flows
5. LangGraph Persistence: https://langchain-ai.github.io/langgraph/concepts/persistence/