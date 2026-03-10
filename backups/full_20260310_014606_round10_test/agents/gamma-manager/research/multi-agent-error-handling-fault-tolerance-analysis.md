# Multi-Agent Error Handling and Fault Tolerance: Deep-Dive Analysis

**Research Date:** 2026-03-07  
**Researcher:** Gamma Manager (AI Research Specialist)  
**Source:** Research task from Orchestrator (c54e5f78-7ec)  
**Workers:** agentic-1 (web search), agentic-2 (supervisor patterns), agentic-3 (recovery mechanisms), agentic-4 (case studies)

---

## Executive Summary

This analysis examines fault tolerance mechanisms in multi-agent AI systems, synthesizing patterns from Microsoft AutoGen v0.4+, LangGraph, CrewAI, Erlang OTP, and academic research. The key finding is that **resilient multi-agent architectures require three core layers: (1) Circuit-break-protected communication, (2) OTP-style supervision trees, and (3) Checkpoint-based state persistence.**

For OpenClaw Army specifically, we recommend implementing a **Hybrid Supervision Model** combining LangGraph's durable execution with Erlang-style supervisor hierarchies.

---

## 1. Retry Strategies in Agent Swarms

### 1.1 Exponential Backoff with Jitter

**Problem:** Naive retries can create "thundering herd" problems where all agents retry simultaneously.

**Solution Pattern (adapted from AWS SDK and LangGraph):**

```python
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class FailureType(Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MODEL_ERROR = "model_error"
    CONTEXT_OVERFLOW = "context_overflow"
    HALLUCINATION = "hallucination"

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        # Exponential backoff: base * 2^attempt
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        # Add jitter: ±25% randomization
        if self.jitter:
            delay *= random.uniform(0.75, 1.25)
        
        return delay

# Per-failure-type policies
RETRY_POLICIES = {
    FailureType.TIMEOUT: RetryPolicy(max_attempts=3, base_delay=2.0),
    FailureType.RATE_LIMIT: RetryPolicy(max_attempts=5, base_delay=5.0),  # Back off significantly
    FailureType.MODEL_ERROR: RetryPolicy(max_attempts=2, base_delay=1.0),  # Fail fast
    FailureType.CONTEXT_OVERFLOW: RetryPolicy(max_attempts=1),  # Don't retry - requires truncation
    FailureType.HALLUCINATION: RetryPolicy(max_attempts=2),  # Retry with different prompt
}
```

### 1.2 Retry Decorator with Failure Classification

```python
from functools import wraps
import time
from typing import Callable, TypeVar

T = TypeVar('T')

def classify_failure(exception: Exception) -> FailureType:
    """Classify exceptions into failure types for targeted retry."""
    if "timeout" in str(exception).lower():
        return FailureType.TIMEOUT
    elif "rate limit" in str(exception).lower() or "429" in str(exception):
        return FailureType.RATE_LIMIT
    elif "context length" in str(exception).lower() or "too long" in str(exception):
        return FailureType.CONTEXT_OVERFLOW
    elif "hallucination" in str(exception).lower():
        return FailureType.HALLUCINATION
    else:
        return FailureType.MODEL_ERROR

def with_retry(
    policy: Optional[RetryPolicy] = None,
    on_failure: Optional[Callable[[Exception, FailureType], None]] = None
):
    """Decorator for agent tool calls with intelligent retry."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    failure_type = classify_failure(e)
                    
                    # Get specific policy for this failure type
                    specific_policy = RETRY_POLICIES.get(failure_type, policy)
                    
                    if attempt >= specific_policy.max_attempts - 1:
                        break
                    
                    # Calculate and apply backoff
                    delay = specific_policy.calculate_delay(attempt)
                    
                    if on_failure:
                        on_failure(e, failure_type)
                    
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator

# Usage on agent tools
class ResearchAgent:
    @with_retry(policy=RetryPolicy(max_attempts=3))
    def search_web(self, query: str) -> str:
        # Tool implementation
        pass
    
    @with_retry(policy=RETRY_POLICIES[FailureType.CONTEXT_OVERFLOW])
    def summarize_long_document(self, content: str) -> str:
        # Uses different retry logic
        pass
```

**Source:** Adapted from AWS SDK retry logic, LangGraph durable execution patterns, and Microsoft AutoGen v0.4 CancellationToken patterns.

---

## 2. Circuit Breakers in Agent Swarms

### 2.1 Circuit Breaker State Machine

The circuit breaker pattern, adapted from microservices (Martin Fowler, Netflix), prevents cascading failures in agent swarms:

```
                    ┌─────────────┐
                    │   CLOSED    │ ← Normal operation
                    │ (requests   │
        Success →   │  allowed)   │ ← Failure threshold
                    └──────┬──────┘
                           │ Failure
                           ▼
                    ┌─────────────┐
                    │   OPEN      │ ← All requests fail fast
              ┘     │ (timeout    │
        Timeout →   │  period)    │
                    └──────┬──────┘
                           │ Half-open test
                           ▼
                    ┌─────────────┐
              ┌─────│ HALF_OPEN   │ ← Limited probe requests
        Failure →   │ (testing    │
                    │  recovery)  │
                    └─────────────┘
```

**Source:** microservices.io/patterns/reliability/circuit-breaker.html

### 2.2 Agent-Specific Circuit Breaker Implementation

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import time
import threading

class CircuitState(Enum):
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing fast
    HALF_OPEN = "half_open"    # Testing recovery

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 2      # Successes to close
    timeout_seconds: float = 60.0   # Time before half-open
    
@dataclass
class CircuitBreaker:
    name: str
    config: CircuitBreakerConfig
    _state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = field(default=0)
    _success_count: int = field(default=0)
    _last_failure_time: Optional[float] = field(default=None)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _on_state_change: Optional[Callable[[str, CircuitState, CircuitState], None]] = None
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state
    
    def record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset on success
    
    def record_failure(self) -> bool:
        """Record a failure. Returns True if circuit should open."""
        with self._lock:
            now = time.time()
            self._last_failure_time = now
            
            if self._state == CircuitState.HALF_OPEN:
                # Failed recovery test - back to OPEN
                self._transition_to(CircuitState.OPEN)
                return True
            
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    return True
            
            return False
    
    def can_execute(self) -> bool:
        """Check if request can proceed through circuit breaker."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            elif self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.timeout_seconds:
                        self._transition_to(CircuitState.HALF_OPEN)
                        self._success_count = 0
                        return True  # Allow probe request
                return False
            
            elif self._state == CircuitState.HALF_OPEN:
                return True  # Allow limited probes
            
            return False
    
    def _transition_to(self, new_state: CircuitState):
        old_state = self._state
        self._state = new_state
        if self._on_state_change:
            self._on_state_change(self.name, old_state, new_state)


class AgentCircuitRegistry:
    """Registry of circuit breakers for different agents/services."""
    
    def __init__(self):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_or_create(self, agent_id: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        with self._lock:
            if agent_id not in self._circuits:
                self._circuits[agent_id] = CircuitBreaker(
                    name=agent_id,
                    config=config
                )
            return self._circuits[agent_id]
    
    def get_status(self) -> Dict[str, str]:
        """Get status map of all circuits for monitoring."""
        with self._lock:
            return {name: cb.state.value for name, cb in self._circuits.items()}


# Usage in OpenClaw Army
class OpenClawAgentExecutor:
    """Example: Circuit breaker-protected agent execution."""
    
    def __init__(self):
        self.circuit_registry = AgentCircuitRegistry()
        self.default_config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30
        )
    
    async def execute_agent(self, agent_id: str, task: dict) -> dict:
        circuit = self.circuit_registry.get_or_create(agent_id, self.default_config)
        
        if not circuit.can_execute():
            return {
                "status": "circuit_open",
                "error": f"Circuit breaker open for agent {agent_id}. Try again later.",
                "retry_after": circuit.config.timeout_seconds
            }
        
        try:
            # Execute agent task
            result = await self._run_agent(agent_id, task)
            circuit.record_success()
            return result
            
        except Exception as e:
            should_open = circuit.record_failure()
            if should_open:
                # Alert supervisor
                await self._alert_supervisor(agent_id, e)
            raise
    
    async def _run_agent(self, agent_id: str, task: dict) -> dict:
        # Actual agent execution
        pass
    
    async def _alert_supervisor(self, agent_id: str, error: Exception):
        # Notify supervisor of circuit open
        pass
```

### 2.3 Circuit Breaker Metrics and Monitoring

**Key Metrics to Track:**

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `failure_rate` | % of failed requests | > 50% |
| `circuit_open_count` | Times breaker opened | > 5/hour |
| `avg_recovery_time` | Time from OPEN → CLOSED | > 5 min |
| `rejected_requests` | Fast-failures due to OPEN | Per minute |

---

## 3. Supervisor/Watchdog Patterns

### 3.1 Erlang OTP-Style Supervision

**Source:** Erlang OTP Design Principles — highly adapted for agent systems.

Supervision trees are the cornerstone of fault-tolerant agent systems:

```
                        ┌──────────────┐
                        │   Root       │
                        │ Supervisor   │
                        └──────┬───────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ Manager  │       │ Manager  │       │ Manager  │
    │Supervisor│       │Supervisor│       │Supervisor│
    │ (Alpha)  │       │ (Beta)   │       │ (Gamma)  │
    └────┬─────┘       └────┬─────┘       └────┬─────┘
         │                  │                  │
    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
    │  Worker │        │  Worker │        │  Worker │
    │ Agents  │        │ Agents  │        │ Agents  │
    └─────────┘        └─────────┘        └─────────┘
```

### 3.2 Supervisor Implementation

```python
from typing import List, Callable, Coroutine, Any
from dataclasses import dataclass
from enum import Enum, auto
import asyncio
import logging

class RestartStrategy(Enum):
    """OTP-style restart strategies."""
    ONE_FOR_ONE = auto()      # Restart only failed child
    ONE_FOR_ALL = auto()      # Restart all children if one fails
    REST_FOR_ONE = auto()     # Restart failed and all children after it

class AgentStatus(Enum):
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"
    STOPPED = "stopped"

@dataclass
class ChildSpec:
    """Specification for a supervised agent/worker."""
    id: str
    agent_type: str
    start_func: Callable[[], Coroutine[Any, Any, Any]]
    restart_policy: str = "permanent"  # permanent, temporary, transient
    max_restarts: int = 5
    max_seconds: int = 60  # Time window for max_restarts

class Supervisor:
    """OTP-style supervisor for agent hierarchies."""
    
    def __init__(self, name: str, strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE):
        self.name = name
        self.strategy = strategy
        self.children: Dict[str, ChildSpec] = {}
        self.agents: Dict
