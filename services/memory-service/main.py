"""
OpenClaw Army — Memory Service
3-Tier Memory + Diary/Reflect + Provenance

Port: 18820
Tier 1: Redis (recent messages, sliding window)
Tier 2: PostgreSQL (session summaries, LLM-generated)
Tier 3: ChromaDB + PostgreSQL (semantic long-term memory with decay)
"""

import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
import redis.asyncio as aioredis
try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    CHROMADB_AVAILABLE = True
except Exception:
    chromadb = None  # type: ignore
    SentenceTransformerEmbeddingFunction = None # type: ignore
    CHROMADB_AVAILABLE = False
    logging.getLogger("memory-service").warning("ChromaDB or sentence-transformers unavailable — Tier 3 disabled")
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ── Config ────────────────────────────────────────────────────────────────────
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://openclaw:openclaw@localhost:5432/openclaw_army")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
SESSION_TTL_HOURS = int(os.getenv("MEMORY_SESSION_TTL_HOURS", "72"))
COMPACTION_THRESHOLD = int(os.getenv("MEMORY_COMPACTION_THRESHOLD_TOKENS", "8000"))
TIER3_DECAY_DAYS = int(os.getenv("MEMORY_TIER3_DECAY_DAYS", "90"))
MAX_TIER1_MESSAGES = 10
MAX_TIER2_SUMMARIES = 20

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("memory-service")

# ── PII Redaction ─────────────────────────────────────────────────────────────
PII_ENABLED = os.getenv("PII_REDACTION_ENABLED", "true").lower() in ("true", "1", "yes")

_PII_PATTERNS = [
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    # Phone numbers (US formats)
    (re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE_REDACTED]'),
    # SSN
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
    # Credit card numbers (basic)
    (re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'), '[CC_REDACTED]'),
    # IP addresses (v4)
    (re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'), '[IP_REDACTED]'),
    # API keys / tokens (long hex or base64 strings that look like secrets)
    (re.compile(r'\b(?:nvapi-|sk-|key-|token-)[A-Za-z0-9_-]{20,}\b'), '[API_KEY_REDACTED]'),
]


def redact_pii(text: str) -> str:
    """Remove PII patterns from text before storage."""
    if not PII_ENABLED or not text:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ── Token Budget Tracker ──────────────────────────────────────────────────────
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "10.00"))
MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", "100.00"))
DAILY_WARN = float(os.getenv("DAILY_WARN", "8.00"))
MONTHLY_WARN = float(os.getenv("MONTHLY_WARN", "80.00"))

_token_usage: Dict[str, Dict[str, float]] = {}  # date -> {agent: cost}


def track_token_cost(agent_name: str, cost: float):
    """Track token cost for budget enforcement."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today not in _token_usage:
        _token_usage[today] = {}
    _token_usage[today][agent_name] = _token_usage[today].get(agent_name, 0.0) + cost


def get_daily_spend() -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(_token_usage.get(today, {}).values())


def get_monthly_spend() -> float:
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    total = 0.0
    for date, agents in _token_usage.items():
        if date.startswith(month_prefix):
            total += sum(agents.values())
    return total


def check_budget() -> Dict[str, Any]:
    daily = get_daily_spend()
    monthly = get_monthly_spend()
    return {
        "daily_spend": daily,
        "daily_budget": DAILY_BUDGET,
        "daily_remaining": DAILY_BUDGET - daily,
        "daily_warning": daily >= DAILY_WARN,
        "daily_exceeded": daily >= DAILY_BUDGET,
        "monthly_spend": monthly,
        "monthly_budget": MONTHLY_BUDGET,
        "monthly_remaining": MONTHLY_BUDGET - monthly,
        "monthly_warning": monthly >= MONTHLY_WARN,
        "monthly_exceeded": monthly >= MONTHLY_BUDGET,
    }


# ── Models ────────────────────────────────────────────────────────────────────
class MemoryCommitRequest(BaseModel):
    agent_name: str
    content: str
    category: str = "other"  # decision, finding, preference, process, entity, other
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MemoryQueryRequest(BaseModel):
    query: str
    agent_name: Optional[str] = None
    category: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)

class DiaryRequest(BaseModel):
    agent_name: str
    story_id: Optional[str] = None
    story_title: Optional[str] = None
    attempt_number: int = 1
    success: bool
    code_generated: Optional[str] = None
    error: Optional[str] = None
    quality_checks: List[Dict] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ReflectRequest(BaseModel):
    agent_name: str
    story_id: Optional[str] = None
    story_title: Optional[str] = None
    total_attempts: int = 1
    final_success: bool
    all_attempts: List[Dict] = Field(default_factory=list)
    commit_sha: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Tier1Message(BaseModel):
    agent_name: str
    role: str  # user, assistant, system
    content: str
    session_id: Optional[str] = None

class Tier2SummaryRequest(BaseModel):
    agent_name: str
    project_id: Optional[str] = None
    goal: str
    agents_used: List[str] = Field(default_factory=list)
    key_results: List[str] = Field(default_factory=list)
    summary_text: str
    task_id: Optional[str] = None

class CompactRequest(BaseModel):
    agent_name: str
    strategy: str = "summarize"  # summarize, truncate
    session_id: Optional[str] = None

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="OpenClaw Army Memory Service", version="1.0.0")

try:
    from shared.logging_middleware import StructuredLoggingMiddleware
    app.add_middleware(StructuredLoggingMiddleware, service_name="memory-service")
except ImportError:
    pass

# Globals (initialized in lifespan)
pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
chroma_client: Optional[Any] = None
chroma_collection: Optional[Any] = None


@app.on_event("startup")
async def startup():
    global pg_pool, redis_client, chroma_client, chroma_collection

    # PostgreSQL
    try:
        pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")

    # Redis
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    # ChromaDB
    if CHROMADB_AVAILABLE:
        try:
            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # Use local embeddings instead of defaulting to OpenAI
            embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            
            chroma_collection = chroma_client.get_or_create_collection(
                name="openclaw_memory",
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function
            )
            logger.info(f"ChromaDB initialized at {CHROMA_PATH} ({chroma_collection.count()} vectors) using local embeddings")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
    else:
        logger.warning("ChromaDB or sentence-transformers not available — Tier 3 vector search disabled")


@app.on_event("shutdown")
async def shutdown():
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/health")
async def health():
    deps = {}
    try:
        if pg_pool:
            await pg_pool.fetchval("SELECT 1")
            deps["postgres"] = "healthy"
        else:
            deps["postgres"] = "unhealthy"
    except Exception:
        deps["postgres"] = "unhealthy"
    try:
        if redis_client:
            await redis_client.ping()
            deps["redis"] = "healthy"
        else:
            deps["redis"] = "unhealthy"
    except Exception:
        deps["redis"] = "unhealthy"
    try:
        deps["chromadb"] = "healthy" if chroma_collection else "unavailable"
        deps["chromadb_count"] = chroma_collection.count() if chroma_collection else 0
    except Exception:
        deps["chromadb"] = "unhealthy"

    all_healthy = all(v == "healthy" for k, v in deps.items() if not k.endswith("_count") and k != "chromadb")
    chromadb_ok = deps.get("chromadb") in ("healthy", "unavailable")
    return {
        "status": "healthy" if (all_healthy and chromadb_ok) else "degraded",
        "service": "memory-service",
        "dependencies": deps,
        "pii_redaction": PII_ENABLED,
        "budget": check_budget(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BUDGET
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/budget")
async def budget_status():
    """Get current token budget status."""
    return check_budget()


@app.post("/budget/track")
async def budget_track(agent_name: str, cost: float):
    """Track token cost for an agent."""
    track_token_cost(agent_name, cost)
    return {"tracked": True, "agent": agent_name, "cost": cost, "budget": check_budget()}


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1 — Recent Messages (Redis)
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/memory/tier1/add")
async def tier1_add(msg: Tier1Message):
    """Add a message to Tier 1 recent memory (Redis sliding window)."""
    if not redis_client:
        raise HTTPException(503, "Redis not available")
    msg.content = redact_pii(msg.content)
    key = f"tier1:{msg.agent_name}:{msg.session_id or 'default'}"
    import json
    entry = json.dumps({
        "id": f"msg-{uuid4().hex[:12]}",
        "role": msg.role,
        "content": msg.content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    await redis_client.rpush(key, entry)
    await redis_client.ltrim(key, -MAX_TIER1_MESSAGES, -1)
    await redis_client.expire(key, SESSION_TTL_HOURS * 3600)
    return {"stored": True, "tier": 1}


@app.get("/memory/tier1/{agent_name}")
async def tier1_get(agent_name: str, session_id: str = "default"):
    """Get recent messages for an agent."""
    if not redis_client:
        raise HTTPException(503, "Redis not available")
    key = f"tier1:{agent_name}:{session_id}"
    import json
    raw = await redis_client.lrange(key, 0, -1)
    messages = [json.loads(r) for r in raw]
    return {"agent": agent_name, "session_id": session_id, "messages": messages, "count": len(messages)}


@app.get("/memory/tier1/{agent_name}/context")
async def tier1_context(agent_name: str, session_id: str = "default"):
    """Get Tier 1 as formatted context string for prompt injection."""
    result = await tier1_get(agent_name, session_id)
    if not result["messages"]:
        return {"context": "No previous context available."}
    lines = []
    for m in result["messages"]:
        role = m["role"].upper()
        lines.append(f"[{role}]: {m['content']}")
    return {"context": "\n\n".join(lines)}


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2 — Session Summaries (PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/memory/tier2/summary")
async def tier2_create_summary(req: Tier2SummaryRequest):
    """Create a session summary in Tier 2."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    summary_id = f"sum-{uuid4().hex[:12]}"
    import json
    await pg_pool.execute(
        """INSERT INTO session_summaries
           (summary_id, agent_name, project_id, goal, agents_used, key_results, summary_text, task_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        summary_id, req.agent_name, req.project_id, req.goal,
        json.dumps(req.agents_used), json.dumps(req.key_results),
        req.summary_text, req.task_id
    )
    # Prune old summaries (keep MAX_TIER2_SUMMARIES per agent)
    await pg_pool.execute(
        """DELETE FROM session_summaries WHERE id IN (
            SELECT id FROM session_summaries WHERE agent_name = $1
            ORDER BY created_at DESC OFFSET $2
        )""", req.agent_name, MAX_TIER2_SUMMARIES
    )
    return {"summary_id": summary_id, "tier": 2}


@app.get("/memory/tier2/{agent_name}")
async def tier2_get(agent_name: str, limit: int = 10):
    """Get session summaries for an agent."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    rows = await pg_pool.fetch(
        """SELECT summary_id, goal, summary_text, agents_used, key_results, task_id, created_at
           FROM session_summaries WHERE agent_name = $1
           ORDER BY created_at DESC LIMIT $2""",
        agent_name, limit
    )
    return {"agent": agent_name, "summaries": [dict(r) for r in rows], "count": len(rows)}


@app.get("/memory/tier2/{agent_name}/context")
async def tier2_context(agent_name: str, limit: int = 5):
    """Get Tier 2 as formatted context string."""
    result = await tier2_get(agent_name, limit)
    if not result["summaries"]:
        return {"context": "No session summaries available."}
    lines = ["## Previous Session Summaries"]
    for s in result["summaries"]:
        lines.append(f"\n### {s['goal']}")
        lines.append(s["summary_text"])
    return {"context": "\n".join(lines)}


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3 — Long-Term Semantic Memory (ChromaDB + PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════════
def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@app.post("/memory/commit")
async def memory_commit(req: MemoryCommitRequest):
    """Commit an artifact to long-term memory (Tier 3)."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    req.content = redact_pii(req.content)
    artifact_id = f"art-{uuid4().hex[:12]}"
    content_hash = _hash(req.content)

    # Check for duplicate
    existing = await pg_pool.fetchval(
        "SELECT artifact_id FROM memory_artifacts WHERE content_hash = $1 AND agent_name = $2",
        content_hash, req.agent_name
    )
    if existing:
        # Update access count instead
        await pg_pool.execute(
            "UPDATE memory_artifacts SET access_count = access_count + 1, last_accessed = NOW() WHERE artifact_id = $1",
            existing
        )
        return {"artifact_id": existing, "deduplicated": True}

    # Store in PostgreSQL
    import json
    await pg_pool.execute(
        """INSERT INTO memory_artifacts
           (artifact_id, agent_name, content, content_hash, category, importance, tags, session_id, metadata)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
        artifact_id, req.agent_name, req.content, content_hash,
        req.category, req.importance, json.dumps(req.tags),
        req.session_id, json.dumps(req.metadata)
    )

    # Store in ChromaDB for vector search
    if chroma_collection is not None:
      try:
        chroma_collection.add(
            ids=[artifact_id],
            documents=[req.content],
            metadatas=[{
                "agent_name": req.agent_name,
                "category": req.category,
                "importance": req.importance,
                "tags": ",".join(req.tags),
                "created_at": datetime.now(timezone.utc).isoformat()
            }]
        )
      except Exception as e:
        logger.error(f"ChromaDB add failed: {e}")

    return {"artifact_id": artifact_id, "content_hash": content_hash, "tier": 3}


@app.post("/memory/query")
async def memory_query(req: MemoryQueryRequest):
    """Semantic search across long-term memory."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    results = []

    # ChromaDB vector search
    if chroma_collection is not None:
     try:
        where_filter = {}
        if req.agent_name:
            where_filter["agent_name"] = req.agent_name
        if req.category:
            where_filter["category"] = req.category

        chroma_results = chroma_collection.query(
            query_texts=[req.query],
            n_results=req.limit * 2,  # Over-fetch for filtering
            where=where_filter if where_filter else None
        )

        if chroma_results and chroma_results["ids"]:
            for i, doc_id in enumerate(chroma_results["ids"][0]):
                distance = chroma_results["distances"][0][i] if chroma_results.get("distances") else 0
                similarity = 1 - distance  # cosine distance to similarity
                meta = chroma_results["metadatas"][0][i] if chroma_results.get("metadatas") else {}
                importance = float(meta.get("importance", 0.5))

                # Boost by importance
                score = similarity * 0.7 + importance * 0.3

                if score >= req.min_importance:
                    results.append({
                        "artifact_id": doc_id,
                        "content": chroma_results["documents"][0][i],
                        "score": round(score, 4),
                        "similarity": round(similarity, 4),
                        "importance": importance,
                        "category": meta.get("category", "other"),
                        "agent_name": meta.get("agent_name", ""),
                    })

                    # Record access
                    await pg_pool.execute(
                        "UPDATE memory_artifacts SET access_count = access_count + 1, last_accessed = NOW() WHERE artifact_id = $1",
                        doc_id
                    )
     except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")

    # Sort by score and limit
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:req.limit]

    return {"query": req.query, "results": results, "count": len(results)}


@app.get("/memory/provenance/{artifact_id}")
async def get_provenance(artifact_id: str):
    """Get full provenance chain for an artifact."""
    rows = await pg_pool.fetch(
        """SELECT provenance_id, actor_id, actor_type, action, inputs_hash, outputs_hash,
                  tool_ids, parent_id, metadata, created_at
           FROM provenance_logs WHERE actor_id = $1 OR provenance_id = $1
           ORDER BY created_at""",
        artifact_id
    )
    return {"artifact_id": artifact_id, "chain": [dict(r) for r in rows]}


# ═══════════════════════════════════════════════════════════════════════════════
# DIARY / REFLECT
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/memory/diary")
async def diary(req: DiaryRequest):
    """Log a task attempt to the diary."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    entry_id = f"diary-{uuid4().hex[:12]}"
    import json
    await pg_pool.execute(
        """INSERT INTO diary_entries
           (entry_id, agent_name, story_id, story_title, attempt_number, success,
            code_generated, error, quality_checks, files_modified, tags, metadata)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
        entry_id, req.agent_name, req.story_id, req.story_title,
        req.attempt_number, req.success, req.code_generated, req.error,
        json.dumps(req.quality_checks), json.dumps(req.files_modified),
        json.dumps(req.tags), json.dumps(req.metadata)
    )

    # Also commit to Tier 3 for semantic search
    summary = f"{'Success' if req.success else 'Failed'}: {req.story_title or 'task'} (attempt {req.attempt_number})"
    if req.error:
        summary += f" — Error: {req.error[:200]}"
    await memory_commit(MemoryCommitRequest(
        agent_name=req.agent_name,
        content=summary,
        category="finding",
        importance=0.7 if req.success else 0.5,
        tags=["diary", "attempt"] + req.tags,
        metadata={"entry_id": entry_id, "story_id": req.story_id}
    ))

    return {"entry_id": entry_id, "success": req.success}


@app.post("/memory/reflect")
async def reflect(req: ReflectRequest):
    """Analyze attempts and extract learnings."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    reflection_id = f"ref-{uuid4().hex[:12]}"

    # Analyze patterns from attempts
    failure_patterns = []
    success_factors = []
    insights = []
    recommendations = []

    for attempt in req.all_attempts:
        if attempt.get("success"):
            success_factors.append(f"Attempt {attempt.get('attempt', '?')} succeeded with {attempt.get('changes_made', 0)} changes")
        else:
            err = attempt.get("error", "unknown")
            failure_patterns.append(f"Attempt {attempt.get('attempt', '?')} failed: {err[:150]}")

    if failure_patterns and success_factors:
        insights.append("Task required multiple iterations — early failures informed later success")
    if req.total_attempts == 1 and req.final_success:
        insights.append("First-attempt success — approach was sound")
    if req.total_attempts > 2:
        recommendations.append("Consider breaking similar tasks into smaller sub-stories")

    import json
    await pg_pool.execute(
        """INSERT INTO reflections
           (reflection_id, agent_name, story_id, story_title, total_attempts, final_success,
            failure_patterns, success_factors, insights, recommendations, commit_sha, metadata)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
        reflection_id, req.agent_name, req.story_id, req.story_title,
        req.total_attempts, req.final_success,
        json.dumps(failure_patterns), json.dumps(success_factors),
        json.dumps(insights), json.dumps(recommendations),
        req.commit_sha, json.dumps(req.metadata)
    )

    # Commit learnings to Tier 3
    learning_text = f"Reflection on {req.story_title or 'task'}: "
    learning_text += "; ".join(insights) if insights else "No insights extracted"
    if recommendations:
        learning_text += " | Recommendations: " + "; ".join(recommendations)

    await memory_commit(MemoryCommitRequest(
        agent_name=req.agent_name,
        content=learning_text,
        category="finding",
        importance=0.8,
        tags=["reflection", "learning"],
        metadata={"reflection_id": reflection_id, "story_id": req.story_id}
    ))

    return {
        "reflection_id": reflection_id,
        "failure_patterns": failure_patterns,
        "success_factors": success_factors,
        "insights": insights,
        "recommendations": recommendations
    }


@app.post("/memory/query_learnings")
async def query_learnings(req: MemoryQueryRequest):
    """Query past learnings — combines diary + reflections + Tier 3 search."""
    results = []

    # 1. Semantic search in Tier 3
    tier3_results = await memory_query(MemoryQueryRequest(
        query=req.query, agent_name=req.agent_name, limit=req.limit,
        tags=["reflection", "learning", "diary"]
    ))
    results.extend(tier3_results["results"])

    # 2. Recent reflections from PostgreSQL
    rows = await pg_pool.fetch(
        """SELECT reflection_id, story_title, insights, recommendations, created_at
           FROM reflections
           WHERE ($1::text IS NULL OR agent_name = $1)
           ORDER BY created_at DESC LIMIT $2""",
        req.agent_name, req.limit
    )
    for r in rows:
        import json
        insights = json.loads(r["insights"]) if isinstance(r["insights"], str) else r["insights"]
        results.append({
            "artifact_id": r["reflection_id"],
            "content": f"{r['story_title']}: {'; '.join(insights) if insights else 'No insights'}",
            "score": 0.6,
            "category": "reflection",
            "agent_name": req.agent_name or ""
        })

    # Deduplicate and sort
    seen = set()
    unique = []
    for r in results:
        if r["artifact_id"] not in seen:
            seen.add(r["artifact_id"])
            unique.append(r)
    unique.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {"query": req.query, "results": unique[:req.limit], "count": len(unique[:req.limit])}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPACTION
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/memory/compact")
async def compact(req: CompactRequest):
    """Compact memory to save space — TRUNCATE or SUMMARIZE strategy."""
    if not redis_client:
        raise HTTPException(503, "Redis not available")
    if req.strategy == "truncate":
        # Delete old Tier 1 data
        pattern = f"tier1:{req.agent_name}:*"
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)
        for key in keys:
            await redis_client.ltrim(key, -5, -1)  # Keep last 5

        # Delete old low-importance Tier 3
        cutoff = datetime.now(timezone.utc) - timedelta(days=TIER3_DECAY_DAYS)
        deleted = await pg_pool.fetchval(
            """DELETE FROM memory_artifacts
               WHERE agent_name = $1 AND importance < 0.3
               AND last_accessed < $2
               RETURNING count(*)""",
            req.agent_name, cutoff
        )
        return {"strategy": "truncate", "tier1_compacted": len(keys), "tier3_deleted": deleted or 0}

    elif req.strategy == "summarize":
        # Get all Tier 1 messages and create a Tier 2 summary
        result = await tier1_get(req.agent_name, req.session_id or "default")
        if result["messages"]:
            combined = " ".join(m["content"][:200] for m in result["messages"])
            summary = f"Session summary ({len(result['messages'])} messages): {combined[:500]}"
            await tier2_create_summary(Tier2SummaryRequest(
                agent_name=req.agent_name,
                goal="Auto-compaction summary",
                summary_text=summary
            ))
            # Clear Tier 1
            key = f"tier1:{req.agent_name}:{req.session_id or 'default'}"
            await redis_client.delete(key)
        return {"strategy": "summarize", "messages_summarized": result.get("count", 0)}

    raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")


# ═══════════════════════════════════════════════════════════════════════════════
# DECAY (maintenance endpoint)
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/memory/decay")
async def decay_old_memories():
    """Decay old, low-importance, low-access memories."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    cutoff = datetime.now(timezone.utc) - timedelta(days=TIER3_DECAY_DAYS)

    # Find candidates
    rows = await pg_pool.fetch(
        """SELECT artifact_id, importance, access_count
           FROM memory_artifacts
           WHERE last_accessed < $1 AND importance < 0.4 AND access_count < 3""",
        cutoff
    )

    deleted_ids = []
    for r in rows:
        aid = r["artifact_id"]
        await pg_pool.execute("DELETE FROM memory_artifacts WHERE artifact_id = $1", aid)
        try:
            if chroma_collection is not None:
                chroma_collection.delete(ids=[aid])
        except Exception:
            pass
        deleted_ids.append(aid)

    logger.info(f"Decayed {len(deleted_ids)} old memories")
    return {"decayed": len(deleted_ids), "ids": deleted_ids}


# ═══════════════════════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/memory/stats")
async def stats():
    """Get memory usage statistics."""
    if not pg_pool:
        raise HTTPException(503, "PostgreSQL not available")
    tier3_count = await pg_pool.fetchval("SELECT count(*) FROM memory_artifacts")
    diary_count = await pg_pool.fetchval("SELECT count(*) FROM diary_entries")
    reflection_count = await pg_pool.fetchval("SELECT count(*) FROM reflections")
    summary_count = await pg_pool.fetchval("SELECT count(*) FROM session_summaries")
    chroma_count = chroma_collection.count() if chroma_collection else 0

    return {
        "tier1": "redis (sliding window)",
        "tier2_summaries": summary_count,
        "tier3_artifacts": tier3_count,
        "tier3_vectors": chroma_count,
        "diary_entries": diary_count,
        "reflections": reflection_count
    }
