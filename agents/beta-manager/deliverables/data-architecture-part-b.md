# System Architecture Document — Part B: Data Architecture

**Workflow ID:** 94f7824f-1dd  
**Subtask ID:** a3bfb79b  
**Status:** Complete  
**Date:** 2025-01-20

---

## Executive Summary

This document defines the data architecture for the multi-agent orchestration system, covering storage solutions, data flows, and consistency patterns across five specialized data stores.

---

## 1. Storage Components Overview

| Component | Technology | Purpose | Data Characteristics |
|-----------|------------|---------|---------------------|
| Primary Database | PostgreSQL 15+ | Transactional data, agent state | Structured, ACID |
| Cache Layer | Redis 7+ | Session context, hot data | Key-value, ephemeral |
| Document Store | S3-compatible | Logs, artifacts, exports | Immutable objects |
| Search Index | Elasticsearch 8+ | Full-text search on logs/memory | Inverted index |
| Analytics Warehouse | ClickHouse | Metrics, time-series, aggregations | Columnar, compressed |

---

## 2. PostgreSQL Schema (Primary Database)

### 2.1 Core Tables

```sql
-- Agents registry
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    role VARCHAR(64) NOT NULL, -- manager, worker, specialist
    status VARCHAR(32) DEFAULT 'inactive',
    port INTEGER,
    workspace_path TEXT,
    parent_agent_id UUID REFERENCES agents(id),
    capabilities JSONB DEFAULT '[]',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ
);

-- Agent hierarchy
CREATE TABLE agent_hierarchy (
    manager_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    worker_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (manager_id, worker_id)
);

-- Workflows
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    status VARCHAR(32) DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    owner_agent_id UUID REFERENCES agents(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Workflow tasks/subtasks
CREATE TABLE workflow_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(64) UNIQUE NOT NULL,
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    parent_task_id UUID REFERENCES workflow_tasks(id),
    title VARCHAR(256) NOT NULL,
    description TEXT,
    status VARCHAR(32) DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    assigned_to UUID REFERENCES agents(id),
    deliverable_type VARCHAR(64),
    specifications JSONB DEFAULT '{}',
    acceptance_criteria JSONB DEFAULT '{}',
    estimated_hours DECIMAL(4,1),
    actual_hours DECIMAL(4,1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ
);

-- Task dependencies
CREATE TABLE task_dependencies (
    task_id UUID REFERENCES workflow_tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID REFERENCES workflow_tasks(id) ON DELETE CASCADE,
    dependency_type VARCHAR(32) DEFAULT 'blocking',
    PRIMARY KEY (task_id, depends_on_task_id)
);

-- Sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key VARCHAR(128) UNIQUE NOT NULL,
    agent_id UUID REFERENCES agents(id),
    session_type VARCHAR(32) DEFAULT 'standard',
    status VARCHAR(32) DEFAULT 'active',
    context JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages/Interactions
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id VARCHAR(128) UNIQUE NOT NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id),
    direction VARCHAR(16) NOT NULL, -- inbound, outbound
    content_type VARCHAR(32) DEFAULT 'text',
    content TEXT,
    tool_calls JSONB DEFAULT '{}',
    tool_results JSONB DEFAULT '{}',
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd DECIMAL(10,6),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tool executions
CREATE TABLE tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id VARCHAR(128) UNIQUE NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    agent_id UUID REFERENCES agents(id),
    session_id UUID REFERENCES sessions(id),
    parameters JSONB DEFAULT '{}',
    result JSONB,
    success BOOLEAN,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Permissions and grants
CREATE TABLE permission_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id VARCHAR(128) UNIQUE NOT NULL,
    agent_id UUID REFERENCES agents(id),
    capability VARCHAR(64) NOT NULL,
    granted_by UUID REFERENCES agents(id),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES agents(id),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(64) NOT NULL,
    actor_agent_id UUID REFERENCES agents(id),
    target_agent_id UUID REFERENCES agents(id),
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(128),
    details JSONB DEFAULT '{}',
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.2 Indexes

```sql
-- Performance indexes
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_role ON agents(role);
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_owner ON workflows(owner_agent_id);
CREATE INDEX idx_tasks_workflow ON workflow_tasks(workflow_id);
CREATE INDEX idx_tasks_status ON workflow_tasks(status);
CREATE INDEX idx_tasks_assigned ON workflow_tasks(assigned_to);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
CREATE INDEX idx_tool_exec_agent ON tool_executions(agent_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_agent_id);

-- JSONB indexes for flexible querying
CREATE INDEX idx_agents_capabilities ON agents USING GIN(capabilities);
CREATE INDEX idx_workflows_metadata ON workflows USING GIN(metadata);
CREATE INDEX idx_tasks_specifications ON workflow_tasks USING GIN(specifications);
```

### 2.3 Partitioning Strategy

```sql
-- Partition messages by month for scale
CREATE TABLE messages_y2025m01 PARTITION OF messages
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Partition tool executions by month
CREATE TABLE tool_exec_y2025m01 PARTITION OF tool_executions
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Partition audit log by month
CREATE TABLE audit_y2025m01 PARTITION OF audit_log
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

---

## 3. Redis Cache Layer

### 3.1 Key Patterns

```
# Session context (Tier 1 memory)
session:{session_key}:context           # Recent messages + summaries
session:{session_key}:metadata          # Session metadata
session:{session_key}:last_activity   # TTL-based expiration

# Agent state
agent:{agent_id}:status                # Online/offline/busy
agent:{agent_id}:current_task          # Active task reference
agent:{agent_id}:last_heartbeat        # ISO timestamp

# Workflow state
workflow:{workflow_id}:status           # Overall progress