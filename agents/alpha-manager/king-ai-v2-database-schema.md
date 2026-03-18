# King AI v2 Database Schema

The database layer provides persistent storage for business units, tasks, evolution proposals, and comprehensive audit logs.

## Schema Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌───────────────┐    ┌───────────────┐                   │
│   │business_units │◄───│ business_logs │                   │
│   └───────┬───────┘    └───────────────┘                   │
│           │                                                  │
│           │         ┌───────────────┐                       │
│           └────────►│     tasks     │◄────┐                │
│                     └───────────────┘     │                │
│                           │               │                │
│                           │         ┌─────┴────┐          │
│                           │         │evolution │          │
│                           │         │proposals │          │
│                           │         └─────┬────┘          │
│                           │               │                │
│                     ┌─────┴────────┐ ┌─────┴────────┐       │
│                     │   agents     │ │   changes    │       │
│                     │   status     │ │   history    │       │
│                     └──────────────┘ └──────────────┘       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Core Tables

### 1. business_units

The central table for managing autonomous businesses.

```sql
CREATE TABLE business_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL,  -- 'dropshipping', 'saas', 'content'
    
    -- Lifecycle state
    current_stage VARCHAR(50) NOT NULL DEFAULT 'ideation'
      CHECK (current_stage IN ('ideation', 'validation', 'launch', 'growth', 'mature', 'sunset')),
    stage_progress FLOAT DEFAULT 0.0,  -- 0.0 to 1.0
    stage_entered_at TIMESTAMP DEFAULT NOW(),
    
    -- Financial tracking
    currency VARCHAR(3) DEFAULT 'USD',
    revenue_lifetime DECIMAL(15, 2) DEFAULT 0.00,
    revenue_last_30d DECIMAL(15, 2) DEFAULT 0.00,
    expense_lifetime DECIMAL(15, 2) DEFAULT 0.00,
    profit_lifetime DECIMAL(15, 2) GENERATED ALWAYS AS (revenue_lifetime - expense_lifetime) STORED,
    
    -- Operational metrics
    customer_count INTEGER DEFAULT 0,
    orders_total INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5, 4),  -- 0.0000 to 1.0000
    
    -- Risk profile
    risk_profile VARCHAR(1) DEFAULT 'B' CHECK (risk_profile IN ('A', 'B', 'C')),
    monthly_budget_cap DECIMAL(15, 2) DEFAULT 5000.00,
    
    -- Metadata
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_business_units_stage ON business_units(current_stage);
CREATE INDEX idx_business_units_category ON business_units(category);
CREATE INDEX idx_business_units_risk ON business_units(risk_profile);
```

**Example Record:**

| Field | Value |
|-------|-------|
| id | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| name | "Organic Home Goods" |
| slug | `organic-home-goods-2026` |
| category | `dropshipping` |
| current_stage | `growth` |
| revenue_lifetime | `$45,230.00` |
| customer_count | `892` |
| risk_profile | `B` |

---

### 2. tasks

Represents work items assigned to agents.

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    subtask_id UUID,
    
    -- Task definition
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending'
      CHECK (status IN ('pending', 'in_progress', 'completed', 'blocked', 'failed')),
    priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    
    -- Assignment
    assigned_to VARCHAR(50),  -- agent identifier
    business_unit_id UUID REFERENCES business_units(id),
    
    -- Execution
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,  -- actual execution time
    estimated_duration_ms INTEGER,  -- prediction
    
    -- Inputs/Outputs
    context JSONB DEFAULT '{}',
    result JSONB,
    
    -- Quality
    quality_score DECIMAL(3, 2),  -- 0.00 to 1.00
    human_review_required BOOLEAN DEFAULT FALSE,
    review_status VARCHAR(50) DEFAULT NULL,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX idx_tasks_business ON tasks(business_unit_id);
CREATE INDEX idx_tasks_workflow ON tasks(workflow_id);
```

**Example Task:**

| Field | Value |
|-------|-------|
| id | `b2c3d4e5-f6a7-8901-bcde-f23456789012` |
| title | "Create TikTok Ad Campaign" |
| status | `completed` |
| priority | `2` |
| assigned_to | `agent:main:alpha-manager` |
| started_at | `2026-03-09 10:00:00` |
| completed_at | `2026-03-09 10:05:32` |
| quality_score | `0.89` |

---

### 3. evolution_proposals

Tracks self-improvement proposals from the evolution engine.

```sql
CREATE TABLE evolution_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Proposal content
    type VARCHAR(50) NOT NULL,  -- 'model_switch', 'prompt_opt', 'workflow_change'
    target VARCHAR(100) NOT NULL,  -- affected component
    
    -- Change details
    current_state JSONB NOT NULL,
    proposed_state JSONB NOT NULL,
    rationale TEXT NOT NULL,
    evidence JSONB,
    
    -- Risk assessment
    estimated_risk DECIMAL(3, 2),
    financial_impact DECIMAL(15, 2),
    rollback_time_ms INTEGER,
    blast_radius VARCHAR(50),  -- 'single_agent', 'agent_pool', 'system'
    
    -- Approval
    status VARCHAR(50) DEFAULT 'pending'
      CHECK (status IN ('pending', 'approved', 'rejected', 'deployed', 'rolled_back')),
    approver_id VARCHAR(100),
    approved_at TIMESTAMP,
    
    -- Experiment
    experiment_enabled BOOLEAN DEFAULT FALSE,
    traffic_split DECIMAL(3, 2) DEFAULT 0.0,
    experiment_started_at TIMESTAMP,
    experiment_results JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_evo_status ON evolution_proposals(status);
CREATE INDEX idx_evo_type ON evolution_proposals(type);
```

---

### 4. logs (Audit Trail)

Immutable record of all system activities for compliance and debugging.

```sql
CREATE TABLE logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Event identification
    event_type VARCHAR(100) NOT NULL,
    event_subtype VARCHAR(100),
    
    -- Context
    business_unit_id UUID,
    agent_id VARCHAR(100),
    user_id VARCHAR(100),
    workflow_id UUID,
    task_id UUID,
    
    -- Details
    message TEXT,
    payload JSONB,
    
    -- Severity
    level VARCHAR(20) DEFAULT 'info'
      CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
    
    -- Traceability
    trace_id VARCHAR(100),
    
    -- Timestamp (UTC)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Partitioned by month (example)
CREATE INDEX idx_logs_created ON logs(created_at DESC);
CREATE INDEX idx_logs_event ON logs(event_type);
CREATE INDEX idx_logs_business ON logs(business_unit_id);
CREATE INDEX idx_logs_trace ON logs(trace_id);
```

**Log Categories:**

| Event Type | Description | Retention |
|------------|-------------|-----------|
| `business.created` | New business unit | 7 years |
| `business.stage_changed` | Lifecycle transition | 7 years |
