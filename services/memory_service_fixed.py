"""
Memory Service - 3-Tier Memory System (FIXED VERSION)
Redis (recent) → PostgreSQL (session) → ChromaDB (long-term)
FIXES APPLIED:
1. Added close() method for proper connection cleanup
2. Added Redis retry logic with exponential backoff
3. Added context managers for safe resource handling
4. Added error handling for tier failures
5. Added comprehensive conversation logging with full context
"""
import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import redis.asyncio as redis
import chromadb
from chromadb.config import Settings

# PII patterns for redaction
PII_PATTERNS = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'phone': r'\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
    'ssn': r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b',
    'credit_card': r'\b(?:\d{4}[-.]?){3}\d{4}\b',
    'api_key': r'[a-zA-Z0-9]{32,}',
    'password': r'(?i)(password|passwd|pwd)\s*[=:]\s*\S+'
}


class MemoryEntry(BaseModel):
    content: str
    category: str = "general"
    importance: int = 5
    tags: List[str] = []
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class MemorySearchResult(BaseModel):
    content: str
    category: str
    importance: int
    tags: List[str]
    timestamp: datetime
    source_tier: str
    relevance_score: float


class ConversationEntry(BaseModel):
    """Full conversation context including reasoning and tool calls"""
    session_id: str
    prompt: str
    response: str
    reasoning: Optional[str] = None
    tools_used: List[Dict[str, Any]] = []
    delegations: List[Dict[str, Any]] = []
    timestamp: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = {}


class MemoryService:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.chroma_client: Optional[chromadb.Client] = None
        self.chroma_collection = None
        self._initialized = False
        self._connection_lock = asyncio.Lock()
        
        # Retry configuration
        self.redis_max_retries = 5
        self.redis_base_delay = 0.1
        self.redis_max_delay = 30.0
    
    async def initialize(self):
        """Initialize all three tiers with error isolation."""
        if self._initialized:
            return
        
        async with self._connection_lock:
            if self._initialized:
                return
            
            # Tier 1: Redis (with retry)
            try:
                await self._init_redis()
                print("✓ Redis tier initialized")
            except Exception as e:
                print(f"⚠ Redis tier unavailable: {e}")
                self.redis = None
            
            # Tier 2: PostgreSQL
            try:
                await self._init_postgres()
                print("✓ PostgreSQL tier initialized")
            except Exception as e:
                print(f"⚠ PostgreSQL tier unavailable: {e}")
                self.pg_pool = None
            
            # Tier 3: ChromaDB
            try:
                await self._init_chroma()
                print("✓ ChromaDB tier initialized")
            except Exception as e:
                print(f"⚠ ChromaDB tier unavailable: {e}")
                self.chroma_client = None
            
            self._initialized = True
    
    async def _init_redis(self):
        """Initialize Redis connection."""
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        await self.redis.ping()
    
    async def _init_postgres(self):
        """Initialize PostgreSQL connection pool."""
        self.pg_pool = await asyncpg.create_pool(
            'postgresql://localhost:5432/openclaw',
            min_size=5,
            max_size=20,
            command_timeout=60,
            server_settings={'jit': 'off'}
        )
        
        # Create tables if not exists - FIXED: sessions table created first
        async with self._pg_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    content_hash VARCHAR(64) UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(50) DEFAULT 'general',
                    importance INTEGER DEFAULT 5,
                    tags JSONB DEFAULT '[]',
                    session_id VARCHAR(100),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    accessed_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(accessed_at);
                
                -- FIXED: Create sessions table BEFORE conversations (foreign key dependency)
                CREATE TABLE IF NOT EXISTS sessions (
                    id VARCHAR(100) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_accessed TIMESTAMP DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    reasoning TEXT,
                    tools_used JSONB DEFAULT '[]',
                    delegations JSONB DEFAULT '[]',
                    metadata JSONB DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT NOW(),
                    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
            """)
    
    async def _init_chroma(self):
        """Initialize ChromaDB for long-term vector storage."""
        # Use modern ChromaDB client initialization
        import os
        persist_dir = "./data/chromadb"
        os.makedirs(persist_dir, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        try:
            self.chroma_collection = self.chroma_client.get_collection("long_term_memories")
        except Exception:
            self.chroma_collection = self.chroma_client.create_collection(
                name="long_term_memories",
                metadata={"hnsw:space": "cosine"}
            )
    
    async def _redis_with_retry(self, operation, *args, **kwargs):
        """Execute Redis operation with exponential backoff retry logic."""
        if not self.redis:
            raise ConnectionError("Redis not initialized")
        
        last_exception = None
        for attempt in range(self.redis_max_retries):
            try:
                return await operation(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError, ConnectionResetError) as e:
                last_exception = e
                delay = min(
                    self.redis_base_delay * (2 ** attempt) + random.uniform(0, 0.1),
                    self.redis_max_delay
                )
                print(f"Redis retry {attempt + 1}/{self.redis_max_retries} in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
                
                # Try to reconnect
                try:
                    await self._init_redis()
                except Exception:
                    pass
        
        raise last_exception or ConnectionError("Redis operation failed after max retries")
    
    @asynccontextmanager
    async def _pg_connection(self):
        """Context manager for safe PostgreSQL resource handling."""
        if not self.pg_pool:
            raise ConnectionError("PostgreSQL not initialized")
        
        conn = None
        try:
            conn = await self.pg_pool.acquire()
            yield conn
        finally:
            if conn:
                await self.pg_pool.release(conn)
    
    def _redact_pii(self, content: str) -> str:
        """Redact personally identifiable information."""
        redacted = content
        for pii_type, pattern in PII_PATTERNS.items():
            redacted = re.sub(pattern, f'[{pii_type}_REDACTED]', redacted)
        return redacted
    
    def _generate_hash(self, content: str) -> str:
        """Generate content hash for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def store(self, entry: MemoryEntry) -> Dict[str, Any]:
        """Store memory across all three tiers with error isolation."""
        await self.initialize()
        
        safe_content = self._redact_pii(entry.content)
        content_hash = self._generate_hash(safe_content)
        timestamp = datetime.utcnow()
        
        results = {"stored": [], "failed": [], "hash": content_hash}
        
        # Tier 1: Redis
        if self.redis:
            try:
                redis_key = f"memory:{content_hash}"
                redis_data = {
                    'content': safe_content,
                    'category': entry.category,
                    'importance': str(entry.importance),
                    'tags': json.dumps(entry.tags),
                    'timestamp': timestamp.isoformat(),
                }
                await self._redis_with_retry(self.redis.hset, redis_key, mapping=redis_data)
                await self._redis_with_retry(self.redis.expire, redis_key, 86400)
                results["stored"].append("redis")
            except Exception as e:
                results["failed"].append(("redis", str(e)))
        
        # Tier 2: PostgreSQL
        if self.pg_pool:
            try:
                async with self._pg_connection() as conn:
                    await conn.execute("""
                        INSERT INTO memories (content, content_hash, category, importance, tags, session_id, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (content_hash) DO UPDATE 
                        SET accessed_at = NOW(), importance = GREATEST(memories.importance, EXCLUDED.importance)
                    """, safe_content, content_hash, entry.category, entry.importance,
                        json.dumps(entry.tags), entry.session_id, json.dumps(entry.metadata))
                results["stored"].append("postgres")
            except Exception as e:
                results["failed"].append(("postgres", str(e)))
        
        # Tier 3: ChromaDB
        if self.chroma_collection and entry.importance >= 7:
            try:
                self.chroma_collection.add(
                    documents=[safe_content],
                    metadatas=[{
                        "category": entry.category,
                        "importance": entry.importance,
                        "tags": json.dumps(entry.tags),
                        "session_id": entry.session_id or "",
                        "timestamp": timestamp.isoformat()
                    }],
                    ids=[content_hash]
                )
                results["stored"].append("chromadb")
            except Exception as e:
                results["failed"].append(("chromadb", str(e)))
        
        return results
    
    async def store_conversation(self, entry: ConversationEntry) -> Dict[str, Any]:
        """Store full conversation context including reasoning and tool calls."""
        await self.initialize()
        
        results = {"stored": [], "failed": []}
        
        # Store in PostgreSQL
        if self.pg_pool:
            try:
                async with self._pg_connection() as conn:
                    # Ensure session exists
                    await conn.execute("""
                        INSERT INTO sessions (id, last_accessed)
                        VALUES ($1, NOW())
                        ON CONFLICT (id) DO UPDATE SET last_accessed = NOW()
                    """, entry.session_id)
                    
                    # Store conversation
                    await conn.execute("""
                        INSERT INTO conversations 
                        (session_id, prompt, response, reasoning, tools_used, delegations, metadata, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, entry.session_id, entry.prompt, entry.response,
                        entry.reasoning, json.dumps(entry.tools_used),
                        json.dumps(entry.delegations), json.dumps(entry.metadata), entry.timestamp)
                results["stored"].append("postgres")
            except Exception as e:
                results["failed"].append(("postgres", str(e)))
        
        # Store in Redis for quick access
        if self.redis:
            try:
                key = f"conversation:{entry.session_id}:{int(entry.timestamp.timestamp())}"
                await self._redis_with_retry(self.redis.set, key, json.dumps({
                    "prompt": entry.prompt,
                    "response": entry.response,
                    "reasoning": entry.reasoning,
                    "tools_used": entry.tools_used,
                    "timestamp": entry.timestamp.isoformat()
                }))
                await self._redis_with_retry(self.redis.expire, key, 604800)  # 7 days
                results["stored"].append("redis")
            except Exception as e:
                results["failed"].append(("redis", str(e)))
        
        return results
    
    async def close(self):
        """FIX #1: Proper connection cleanup."""
        print("Closing Memory Service connections...")
        
        if self.redis:
            try:
                await self.redis.close()
                print("✓ Redis connection closed")
            except Exception as e:
                print(f"Error closing Redis: {e}")
        
        if self.pg_pool:
            try:
                await self.pg_pool.close()
                print("✓ PostgreSQL pool closed")
            except Exception as e:
                print(f"Error closing PostgreSQL: {e}")
        
        if self.chroma_client:
            try:
                # ChromaDB PersistentClient doesn't need explicit close
                print("✓ ChromaDB client ready")
            except Exception as e:
                print(f"Error with ChromaDB: {e}")
        
        self._initialized = False
        print("Memory Service shutdown complete")


# Global service instance
memory_service = MemoryService()

app = FastAPI(title="Memory Service", version="2.0.0")

@app.on_event("startup")
async def startup():
    await memory_service.initialize()

@app.on_event("shutdown")
async def shutdown():
    await memory_service.close()

@app.post("/store")
async def store_memory(entry: MemoryEntry):
    result = await memory_service.store(entry)
    return result

@app.post("/store_conversation")
async def store_conversation(entry: ConversationEntry):
    result = await memory_service.store_conversation(entry)
    return result

@app.get("/health")
async def health_check():
    status = {
        "redis": memory_service.redis is not None,
        "postgres": memory_service.pg_pool is not None,
        "chromadb": memory_service.chroma_collection is not None
    }
    return {"status": "healthy" if any(status.values()) else "degraded", "tiers": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18820)
