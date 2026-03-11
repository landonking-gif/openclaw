# Event Sourcing for Agent State Reconstruction
**Research Date:** 2026-03-07  
**Focus:** Event sourcing patterns for LLM agent state persistence and replay

---

## Executive Summary

Event sourcing is the architectural pattern underlying Temporal's durable execution. It stores state changes as immutable events and supports complete rebuild, temporal queries, and event replay — critical for deterministic agent coordination.

| Framework | Event Store | Replay Pattern | Best For |
|-----------|-------------|----------------|----------|
| **EventStoreDB (Kurrent)** | Native event store | Full stream replay | Audit, compliance |
| **Axon Framework** | Axon Server/RDBMS | Event replay + snapshots | CQRS, DDD |
| **Temporal** | Pluggable (Cassandra/Postgres) | Command → Event replay | Workflow durability |
| **Spring Event Sourcing** | JPA/event store | Manual replay | JVM-based systems |

**Key Insight:** Event sourcing enables "time travel" debugging for agent swarms — replay historical events to understand why an agent made a specific decision.

---

## 1. Event Sourcing Fundamentals

### 1.1 Core Pattern (Martin Fowler)

> "Event Sourcing ensures that all changes to application state are stored as a sequence of events."

**Primary Capabilities:**

1. **Complete Rebuild:** Discard state, replay events from empty
2. **Temporal Query:** State at any point in time
3. **Event Replay:** Fix past events, recompute consequences

**Source:** https://martinfowler.com/eaaDev/EventSourcing.html

### 1.2 Domain Events for Agent Systems

**Event Types for LLM Agents:**

| Event Type | Payload Example | Purpose |
|------------|-----------------|---------|
| `AgentStarted` | `{agent_id, task_id, timestamp}` | Traceability |
| `ToolInvoked` | `{tool_name, args, result}` | Decision audit |
| `LLMCalled` | `{model, prompt_hash, response_hash}` | Cost/quality |
| `CheckpointSaved` | `{state_hash, sequence_number}` | Recovery |
| `HumanApproved` | `{decision_id, approver, timestamp}` | Compliance |
| `AgentFailed` | `{error, stack_trace, retry_count}` | Failover |

### 1.3 State Reconstruction Process

```
Empty Agent State
    ↓
Replay Events from Stream
    ↓
Apply Event Handlers (fold-left)
    ↓
Current Agent State Restored
```

**Code Example (Conceptual):**

```python
class AgentState:
    def __init__(self):
        self.messages = []
        self.memory = {}
        self.tool_calls = []
        self.done = False

class AgentEventStream:
    def replay(self, events: List[Event]) -> AgentState:
        state = AgentState()
        for event in events:
            state = self.apply(event, state)
        return state
    
    def apply(self, event: Event, state: AgentState) -> AgentState:
        handlers = {
            "MessageAdded": lambda e, s: s.add_message(e.content),
            "ToolCalled": lambda e, s: s.record_tool(e.tool, e.result),
            "MemoryUpdated": lambda e, s: s.update_memory(e.key, e.value),
        }
        return handlers.get(event.type, lambda e, s: s)(event, state)
```

---

## 2. Production Event Stores

### 2.1 EventStoreDB (Kurrent)

**Features:**
- Immutable append-only log of events
- Event indexing for fast retrieval
- Native pub/sub for real-time sync
- Time travel: replay events to any point
- Supports multiple languages (.NET, Java, Node, Python, Go, Rust)

**Agent State Reconstruction Pattern:**

```python
from kurrentdb import KurrentDBClient

class AgentEventStore:
    def __init__(self, client: KurrentDBClient, stream_name: str):
        self.client = client
        self.stream = stream_name
    
    def append_event(self, event_type: str, payload: dict):
        """Append agent event to stream"""
        event = EventData(
            type=event_type,
            data=json.dumps(payload).encode()
        )
        self.client.append_to_stream(self.stream, [event])
    
    def replay_to_state(self) -> AgentState:
        """Reconstruct agent state from event history"""
        events = self.client.read_stream(self.stream)
        state = AgentState()
        
        for event in events:
            payload = json.loads(event.data)
            state = self.apply_event(event.type, payload, state)
            state.version = event.revision
        
        return state
    
    def restore_to_point(self, revision: int) -> AgentState:
        """Time travel: restore agent state at specific event"""
        events = self.client.read_stream(
            self.stream, 
            revision=revision,
            direction=Direction.Forward
        )
        return self.replay_to_state(events)
```

**Source:** https://www.kurrent.io/event-sourcing

### 2.2 Axon Framework (Java)

**Architecture:**
- **Command Bus:** Routes commands to aggregates
- **Event Bus:** Publishes events to event handlers
- **Query Bus:** Handles read model queries
- **Event Store:** Axon Server or relational DB

**Snapshot Pattern:**
- Store full aggregate state periodically (every N events)
- Fast replay: load snapshot + events since snapshot
- Reduces replay time from minutes to milliseconds

### 2.3 Temporal's Event Store

**Implementation:**
- Commands → Temporal Service → Events → History
- Activity results cached (not replayed if already executed)
- Deterministic constraint: same inputs → same outputs

---

## 3. Event Sourcing for LLM Agent Systems

### 3.1 Agent as Event-Sourced Aggregate

**Pattern:** Treat each agent as an aggregate root with its own event stream.

```typescript
// Agent Event Stream Contract
interface AgentEvent {
  type: string;
  aggregateId: string;  // Agent ID
  version: number;      // Sequence number
  timestamp: Date;
  payload: any;
}

// Core Agent Events
type AgentEvent =
  | { type: "AgentCreated"; payload: { agentId: string; config: AgentConfig } }
  | { type: "TaskAssigned"; payload: { taskId: string; description: string } }
  | { type: "ThinkingStarted"; payload: { thoughtId: string; context: Context } }
  | { type: "ToolSelected"; payload: { tool: string; args: any } }
  | { type: "ToolCompleted"; payload: { tool: string; result: any; duration: number } }
  | { type: "ResponseGenerated"; payload: { content: string; tokens: {in: number; out: number} } }
  | { type: "CheckpointSaved"; payload: { stateSnapshot: AgentState; checkpointId: string } }
  | { type: "AgentFailed"; payload: { error: string; recoverable: boolean } }
  | { type: "AgentCompleted"; payload: { finalOutput: any; duration: number } };
```

### 3.2 State Reconstruction with Snapshotting

**Why Snapshotting is Critical:**
- Pure event replay for long-running agents (1000s of LLM calls) is too slow
- Snapshot every N events (e.g., every 100 events or hourly)
- Reconstruct: Load snapshot + replay events since snapshot

```python
class SnapshottingAgentStore:
    def __init__(self, event_store, snapshot_store):
        self.events = event_store
        self.snapshots = snapshot_store
        self.snapshot_frequency = 100
    
    def save_agent_state(self, agent_id: str, state: AgentState):
        # Always append event
        self.events.append(agent_id, AgentCheckpointed(state))
        event_count = self.events.count(agent_id)
        
        # Periodically save snapshot
        if event_count % self.snapshot_frequency == 0:
            self.snapshots.save(agent_id, state, event_count)
    
    def reconstruct_agent(self, agent_id: str) -> AgentState:
        stream = self.events.get_stream(agent_id)
        
        # Try to load latest snapshot
        snapshot = self.snapshots.load_latest(agent_id)
        
        if snapshot:
            # Fast path: load snapshot + replay delta
            state =