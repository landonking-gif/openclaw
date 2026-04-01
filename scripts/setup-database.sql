-- ═══════════════════════════════════════════════════════════════════════════════
-- OpenClaw Army — Database Schema
-- PostgreSQL migrations for memory-service, cost-tracker, and audit
-- ═══════════════════════════════════════════════════════════════════════════════

-- Diary entries from agent task attempts
CREATE TABLE IF NOT EXISTS diary_entries (
    id              SERIAL PRIMARY KEY,
    entry_id        TEXT UNIQUE NOT NULL,
    agent_name      TEXT NOT NULL,
    story_id        TEXT,
    story_title     TEXT,
    attempt_number  INTEGER DEFAULT 1,
    success         BOOLEAN NOT NULL,
    code_generated  TEXT,
    error           TEXT,
    quality_checks  JSONB DEFAULT '[]'::jsonb,
    files_modified  JSONB DEFAULT '[]'::jsonb,
    tags            JSONB DEFAULT '[]'::jsonb,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Reflections extracted from diary entries
CREATE TABLE IF NOT EXISTS reflections (
    id                  SERIAL PRIMARY KEY,
    reflection_id       TEXT UNIQUE NOT NULL,
    agent_name          TEXT NOT NULL,
    story_id            TEXT,
    story_title         TEXT,
    total_attempts      INTEGER DEFAULT 1,
    final_success       BOOLEAN NOT NULL,
    failure_patterns    JSONB DEFAULT '[]'::jsonb,
    success_factors     JSONB DEFAULT '[]'::jsonb,
    insights            JSONB DEFAULT '[]'::jsonb,
    recommendations     JSONB DEFAULT '[]'::jsonb,
    commit_sha          TEXT,
    metadata            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Long-term memory artifacts (tier 3 metadata — vectors in ChromaDB)
CREATE TABLE IF NOT EXISTS memory_artifacts (
    id              SERIAL PRIMARY KEY,
    artifact_id     TEXT UNIQUE NOT NULL,
    agent_name      TEXT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    category        TEXT DEFAULT 'other',  -- decision, finding, preference, process, entity, other
    importance      REAL DEFAULT 0.5,
    access_count    INTEGER DEFAULT 0,
    tags            JSONB DEFAULT '[]'::jsonb,
    metadata        JSONB DEFAULT '{}'::jsonb,
    session_id      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_accessed   TIMESTAMPTZ DEFAULT NOW()
);

-- Provenance chain for audit
CREATE TABLE IF NOT EXISTS provenance_logs (
    id              SERIAL PRIMARY KEY,
    provenance_id   TEXT UNIQUE NOT NULL,
    actor_id        TEXT NOT NULL,
    actor_type      TEXT NOT NULL,  -- king, manager, worker, service
    action          TEXT NOT NULL,
    inputs_hash     TEXT,
    outputs_hash    TEXT,
    tool_ids        JSONB DEFAULT '[]'::jsonb,
    parent_id       TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Cost tracking records
CREATE TABLE IF NOT EXISTS cost_records (
    id              SERIAL PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    session_id      TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Workflow runs (for orchestrator-api)
CREATE TABLE IF NOT EXISTS workflow_runs (
    id              SERIAL PRIMARY KEY,
    workflow_id     TEXT UNIQUE NOT NULL,
    name            TEXT,
    status          TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    plan            JSONB DEFAULT '{}'::jsonb,
    results         JSONB DEFAULT '{}'::jsonb,
    error           TEXT,
    created_by      TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Approval requests (for permission-broker persistence)
CREATE TABLE IF NOT EXISTS approval_requests (
    id              SERIAL PRIMARY KEY,
    request_id      TEXT UNIQUE NOT NULL,
    requester       TEXT NOT NULL,
    approver        TEXT,
    action          TEXT NOT NULL,
    risk_level      TEXT DEFAULT 'low',
    risk_factors    JSONB DEFAULT '[]'::jsonb,
    status          TEXT DEFAULT 'pending',  -- pending, approved, denied, expired
    granted_at      TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Tier 2 session summaries
CREATE TABLE IF NOT EXISTS session_summaries (
    id              SERIAL PRIMARY KEY,
    summary_id      TEXT UNIQUE NOT NULL,
    agent_name      TEXT NOT NULL,
    project_id      TEXT,
    goal            TEXT,
    agents_used     JSONB DEFAULT '[]'::jsonb,
    key_results     JSONB DEFAULT '[]'::jsonb,
    summary_text    TEXT NOT NULL,
    task_id         TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_diary_agent ON diary_entries(agent_name);
CREATE INDEX IF NOT EXISTS idx_diary_story ON diary_entries(story_id);
CREATE INDEX IF NOT EXISTS idx_diary_created ON diary_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_reflections_agent ON reflections(agent_name);
CREATE INDEX IF NOT EXISTS idx_reflections_story ON reflections(story_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_artifacts(agent_name);
CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_artifacts(category);
CREATE INDEX IF NOT EXISTS idx_memory_hash ON memory_artifacts(content_hash);
CREATE INDEX IF NOT EXISTS idx_provenance_actor ON provenance_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_records(agent_name);
CREATE INDEX IF NOT EXISTS idx_cost_created ON cost_records(created_at);
CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_records(model);
CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requester ON approval_requests(requester);
CREATE INDEX IF NOT EXISTS idx_summary_agent ON session_summaries(agent_name);
CREATE INDEX IF NOT EXISTS idx_summary_project ON session_summaries(project_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- New tables for agent-registry, notification, and token budget
-- ═══════════════════════════════════════════════════════════════════════════════

-- Agent registry snapshots (for persistence across restarts)
CREATE TABLE IF NOT EXISTS agent_registry (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    port            INTEGER NOT NULL,
    role            TEXT NOT NULL,         -- king, manager, worker
    model           TEXT DEFAULT '',
    capabilities    JSONB DEFAULT '[]'::jsonb,
    manager         TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    registered_at   TIMESTAMPTZ DEFAULT NOW(),
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW(),
    status          TEXT DEFAULT 'online'
);

-- Notification log
CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    notif_id        TEXT UNIQUE NOT NULL,
    recipient       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    source          TEXT DEFAULT 'system',
    priority        TEXT DEFAULT 'normal',
    success         BOOLEAN NOT NULL,
    error           TEXT,
    sent_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Token / cost budget tracking (daily granularity)
CREATE TABLE IF NOT EXISTS token_budget (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    agent_name      TEXT NOT NULL,
    model           TEXT DEFAULT '',
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, agent_name, model)
);

CREATE INDEX IF NOT EXISTS idx_registry_role ON agent_registry(role);
CREATE INDEX IF NOT EXISTS idx_registry_status ON agent_registry(status);
CREATE INDEX IF NOT EXISTS idx_notif_source ON notifications(source);
CREATE INDEX IF NOT EXISTS idx_notif_sent ON notifications(sent_at);
CREATE INDEX IF NOT EXISTS idx_budget_date ON token_budget(date);
CREATE INDEX IF NOT EXISTS idx_budget_agent ON token_budget(agent_name);
