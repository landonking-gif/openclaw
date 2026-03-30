"""
GitHub Copilot Service with Rate Limiting and Model Fallback
Uses Raptor Preview as primary, reserves GPT Codex 5.3 for hard tasks
"""
import asyncio
import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class TaskDifficulty(Enum):
    EASY = "easy"           # Simple explanations, docs, comments
    MEDIUM = "medium"       # Standard code generation, refactoring
    HARD = "hard"           # Complex algorithms, architecture, debugging


class CopilotRequest(BaseModel):
    prompt: str
    command: str = "suggest"  # suggest or explain
    language: Optional[str] = None
    context: Optional[str] = None
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    timeout: int = 60


class CopilotResponse(BaseModel):
    result: str
    model_used: str
    tokens_used: Optional[int] = None
    execution_time: float
    from_cache: bool = False


class RateLimitTracker:
    """Track rate limits and manage fallback logic"""
    
    def __init__(self):
        self.copilot_requests = []
        self.raptor_requests = []
        self.codex_requests = []
        self.window_minutes = 60
        
        # Rate limits (adjust based on actual limits)
        self.COPILOT_LIMIT = 100  # requests per hour
        self.RAPTOR_LIMIT = 500
        self.CODEX_LIMIT = 50     # Reserve for hard tasks
    
    def _clean_old(self, request_list: List[datetime]):
        """Remove requests older than window"""
        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        return [t for t in request_list if t > cutoff]
    
    def check_copilot_available(self) -> bool:
        """Check if Copilot CLI is within rate limits"""
        self.copilot_requests = self._clean_old(self.copilot_requests)
        return len(self.copilot_requests) < self.COPILOT_LIMIT
    
    def check_raptor_available(self) -> bool:
        """Check if Raptor Preview is within rate limits"""
        self.raptor_requests = self._clean_old(self.raptor_requests)
        return len(self.raptor_requests) < self.RAPTOR_LIMIT
    
    def check_codex_available(self) -> bool:
        """Check if GPT Codex 5.3 is within rate limits (reserved for hard tasks)"""
        self.codex_requests = self._clean_old(self.codex_requests)
        return len(self.codex_requests) < self.CODEX_LIMIT
    
    def record_request(self, model: str):
        """Record a request to rate limit tracker"""
        now = datetime.utcnow()
        if model == "copilot":
            self.copilot_requests.append(now)
        elif model == "raptor":
            self.raptor_requests.append(now)
        elif model == "codex":
            self.codex_requests.append(now)


class CopilotService:
    def __init__(self):
        self.rate_tracker = RateLimitTracker()
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour
        
        # Model priorities
        self.PRIMARY_MODEL = "raptor"      # Raptor Preview - default
        self.FALLBACK_MODEL = "copilot"    # Copilot CLI - fallback
        self.PREMIUM_MODEL = "codex"       # GPT Codex 5.3 - hard tasks only
    
    def _estimate_difficulty(self, prompt: str) -> TaskDifficulty:
        """Estimate task difficulty from prompt"""
        prompt_lower = prompt.lower()
        
        # Hard task indicators
        hard_indicators = [
            "architecture", "design pattern", "complex algorithm",
            "performance optimization", "concurrent", "distributed",
            "security vulnerability", "race condition", "memory leak",
            "refactor entire", "rewrite", "migrate", "port from"
        ]
        
        # Easy task indicators
        easy_indicators = [
            "explain", "document", "comment", "what is",
            "how to", "simple", "basic", "hello world",
            "print", "format", "convert"
        ]
        
        # Check for hard indicators
        for indicator in hard_indicators:
            if indicator in prompt_lower:
                return TaskDifficulty.HARD
        
        # Check for easy indicators
        for indicator in easy_indicators:
            if indicator in prompt_lower:
                return TaskDifficulty.EASY
        
        return TaskDifficulty.MEDIUM
    
    def _get_cache_key(self, prompt: str, command: str, language: Optional[str]) -> str:
        """Generate cache key for request"""
        key = f"{command}:{language or 'generic'}:{hash(prompt) % 10000000}"
        return key
    
    def _check_cache(self, key: str) -> Optional[str]:
        """Check if result is in cache"""
        if key in self.cache:
            result, timestamp = self.cache[key]
            if datetime.utcnow().timestamp() - timestamp < self.cache_ttl:
                return result
            else:
                del self.cache[key]
        return None
    
    def _store_cache(self, key: str, result: str):
        """Store result in cache"""
        self.cache[key] = (result, datetime.utcnow().timestamp())
    
    async def _call_copilot_cli(self, prompt: str, command: str, timeout: int) -> str:
        """Call GitHub Copilot CLI"""
        try:
            # Build command
            if command == "explain":
                full_prompt = f"explain: {prompt}"
            else:
                full_prompt = prompt
            
            cmd = ["~/.local/share/gh/copilot/copilot", "-p", full_prompt]
            
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=timeout
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                error = stderr.decode().strip()
                if "rate limit" in error.lower() or "429" in error:
                    raise RateLimitExceeded("Copilot CLI rate limit exceeded")
                raise Exception(f"Copilot CLI failed: {error}")
            
            result = stdout.decode().strip()
            
            # Check for permission denied (expected in non-interactive mode)
            if "permission denied" in result.lower():
                # This is expected - still return the code
                pass
            
            return result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Copilot CLI timed out after {timeout}s")
        except FileNotFoundError:
            raise Exception("Copilot CLI not found at ~/.local/share/gh/copilot/copilot")
    
    async def _call_raptor(self, prompt: str, command: str, language: Optional[str]) -> str:
        """Call Raptor Preview model via orchestrator's LLM fallback"""
        # This would integrate with your existing llm_fallback system
        # For now, simulate with a call to the orchestrator
        
        from openclaw_core.orchestrator import llm_fallback
        
        full_prompt = f"[{command.upper()}] {language or ''}\n\n{prompt}"
        
        result = await llm_fallback.query(
            prompt=full_prompt,
            provider_name="raptor",
            temperature=0.3,
            max_tokens=2000
        )
        
        return result
    
    async def _call_codex(self, prompt: str, command: str, language: Optional[str]) -> str:
        """Call GPT Codex 5.3 for hard tasks"""
        # Premium model for complex tasks
        
        from openclaw_core.orchestrator import llm_fallback
        
        full_prompt = f"[{command.upper()} - COMPLEX TASK] {language or ''}\n\n{prompt}\n\nThink step by step and provide a thorough solution."
        
        result = await llm_fallback.query(
            prompt=full_prompt,
            provider_name="codex",
            temperature=0.2,
            max_tokens=4000
        )
        
        return result
    
    async def process(self, request: CopilotRequest) -> CopilotResponse:
        """Process a Copilot request with intelligent model selection"""
        import time
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(request.prompt, request.command, request.language)
        cached = self._check_cache(cache_key)
        if cached:
            return CopilotResponse(
                result=cached,
                model_used="cache",
                execution_time=time.time() - start_time,
                from_cache=True
            )
        
        # Determine actual difficulty
        actual_difficulty = self._estimate_difficulty(request.prompt)
        if request.difficulty == TaskDifficulty.HARD or actual_difficulty == TaskDifficulty.HARD:
            # Force hard task handling
            actual_difficulty = TaskDifficulty.HARD
        
        # Select model based on difficulty and availability
        model_used = None
        result = None
        
        if actual_difficulty == TaskDifficulty.HARD:
            # Hard tasks: Try Codex 5.3 first (if available), then fallback
            if self.rate_tracker.check_codex_available():
                try:
                    result = await self._call_codex(
                        request.prompt, request.command, request.language
                    )
                    model_used = "codex-5.3"
                    self.rate_tracker.record_request("codex")
                except Exception as e:
                    print(f"Codex failed, trying Raptor: {e}")
            
            if not result and self.rate_tracker.check_raptor_available():
                try:
                    result = await self._call_raptor(
                        request.prompt, request.command, request.language
                    )
                    model_used = "raptor-preview"
                    self.rate_tracker.record_request("raptor")
                except Exception as e:
                    print(f"Raptor failed, trying Copilot: {e}")
        
        else:
            # Easy/Medium tasks: Use Raptor Preview as primary
            if self.rate_tracker.check_raptor_available():
                try:
                    result = await self._call_raptor(
                        request.prompt, request.command, request.language
                    )
                    model_used = "raptor-preview"
                    self.rate_tracker.record_request("raptor")
                except Exception as e:
                    print(f"Raptor failed, trying Copilot: {e}")
        
        # Final fallback: Copilot CLI
        if not result:
            if self.rate_tracker.check_copilot_available():
                try:
                    result = await self._call_copilot_cli(
                        request.prompt, request.command, request.timeout
                    )
                    model_used = "copilot-cli"
                    self.rate_tracker.record_request("copilot")
                except RateLimitExceeded:
                    # Copilot rate limited - we've already tried Raptor
                    raise HTTPException(
                        status_code=429,
                        detail="All models rate limited. Please try again later."
                    )
            else:
                # Everything rate limited
                raise HTTPException(
                    status_code=429,
                    detail="All models rate limited. Please try again later."
                )
        
        # Store in cache
        self._store_cache(cache_key, result)
        
        execution_time = time.time() - start_time
        
        return CopilotResponse(
            result=result,
            model_used=model_used,
            execution_time=execution_time,
            from_cache=False
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return {
            "copilot": {
                "available": self.rate_tracker.check_copilot_available(),
                "used_last_hour": len(self.rate_tracker.copilot_requests),
                "limit": self.rate_tracker.COPILOT_LIMIT
            },
            "raptor": {
                "available": self.rate_tracker.check_raptor_available(),
                "used_last_hour": len(self.rate_tracker.raptor_requests),
                "limit": self.rate_tracker.RAPTOR_LIMIT
            },
            "codex": {
                "available": self.rate_tracker.check_codex_available(),
                "used_last_hour": len(self.rate_tracker.codex_requests),
                "limit": self.rate_tracker.CODEX_LIMIT,
                "note": "Reserved for hard tasks only"
            }
        }


class RateLimitExceeded(Exception):
    pass


# Global service instance
copilot_service = CopilotService()

app = FastAPI(title="Copilot Service", version="1.0.0")

@app.post("/suggest", response_model=CopilotResponse)
async def suggest(request: CopilotRequest):
    """Get code suggestions with automatic model selection"""
    request.command = "suggest"
    return await copilot_service.process(request)

@app.post("/explain", response_model=CopilotResponse)
async def explain(request: CopilotRequest):
    """Explain code with automatic model selection"""
    request.command = "explain"
    return await copilot_service.process(request)

@app.get("/status")
async def get_status():
    """Get rate limit status for all models"""
    return copilot_service.get_status()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "copilot"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18880)
