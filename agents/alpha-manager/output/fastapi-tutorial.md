# Complete FastAPI REST API Tutorial
## A Production-Ready Guide from Scratch

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Setup](#1-project-setup)
3. [Database Integration](#2-database-integration)
4. [Core API Development](#3-core-api-development)
5. [Authentication & Security](#4-authentication--security)
6. [Testing](#5-testing)
7. [Deployment](#6-deployment)
8. [Bonus Features](#7-bonus-features)
9. [Common Pitfalls](#common-pitfalls--solutions)
10. [Final Project Structure](#final-project-structure-summary)

---

## Prerequisites

**Required Knowledge:**
- Basic Python (functions, classes, decorators)
- HTTP concepts (GET, POST, PUT, DELETE, status codes)
- Familiarity with databases (SQL basics)
- Command line basics

**Required Software:**
- Python 3.9+ 🐍
- PostgreSQL 14+ 🐘
- Docker (for deployment section) 🐳

---

## 1. Project Setup

### Why FastAPI?

FastAPI provides:
- **Automatic validation** via Pydantic (no more manual parsing)
- **Auto-generated docs** (Swagger UI at `/docs`)
- **Async support** out of the box
- **Type hints** for IDE autocomplete and fewer bugs
- **Performance** on par with Node.js and Go frameworks

### Step 1.1: Create Project Structure

```bash
# Create project directory
mkdir fastapi-complete-api
cd fastapi-complete-api

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
# venv\Scripts\activate
```

### Step 1.2: Install Dependencies with Poetry

**Why Poetry?** Poetry manages dependencies AND virtual environments in one file with deterministic resolution (no more `requirements.txt` hell).

```bash
# Install Poetry if not present
pip install poetry

# Initialize Poetry project
curl -sSL https://install.python-poetry.org | python3 -
poetry init --name fastapi-api --dependency fastapi --dependency uvicorn --dependency sqlalchemy --dependency alembic --dependency psycopg2-binary --dependency pydantic --dependency pydantic-settings --dependency python-jose --dependency passlib --dependency bcrypt --dependency python-multipart --dependency pytest --dependency pytest-asyncio --dependency httpx --dependency pytest-cov
```

**Generated `pyproject.toml`:**

```toml
[tool.poetry]
name = "fastapi-api"
version = "0.1.0"
description = "Complete FastAPI REST API Tutorial"
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
sqlalchemy = "^2.0.23"
alembic = "^1.12.1"
psycopg2-binary = "^2.9.9"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.6"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
pytest-asyncio = "^0.21.1"
httpx = "^0.25.2"
pytest-cov = "^4.1.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

Install all dependencies:
```bash
poetry install
```

### Step 1.3: Project Directory Structure

Create this file tree:

```
fastapi-complete-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings and configuration
│   ├── database.py          # Database connection
│   ├── deps.py              # Dependencies (DB session, auth)
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py          # SQLAlchemy models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py          # Pydantic schemas
│   │   └── token.py         # JWT token schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── users.py         # User CRUD endpoints
│   │   └── auth.py          # Authentication endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── user_service.py  # Business logic
│   └── utils/
│       ├── __init__.py
│       ├── security.py      # Password hashing, JWT
│       └── exceptions.py    # Custom exceptions
├── alembic/                 # Migrations folder (auto-generated)
│   ├── versions/
│   └── env.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── test_users.py
│   └── test_auth.py
├── .env.example             # Template for env vars
├── .env                     # Actual environment (gitignored!)
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

**Create directories:**
```bash
mkdir -p app/models app/schemas app/routers app/services app/utils tests
```

### Step 1.4: Environment Configuration

**`app/config.py`** - Centralized configuration using Pydantic Settings:

```python
"""
Configuration management using Pydantic Settings.
Why: Environment-based config beats hardcoded values.
Safety: Secrets are loaded from .env, never committed.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    app_name: str = "FastAPI Complete API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://user:password@localhost/fastapi_db"
    # Alternative: Construct from components
    # db_host: str = "localhost"
    # db_port: int = 5432
    # db_name: str = "fastapi_db"
    # db_user: str = "postgres"
    # db_password: str = "password"
    
    # Security
    secret_key: str = "change-me-in-production-32-characters"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        # Allows CORS_ORIGINS=http://localhost:3000,http://localhost:5173
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Why cache: Prevents reloading .env on every request.
    """
    return Settings()
```

**`.env.example`** (committed to git):

```bash
# App Settings
DEBUG=false
APP_NAME="FastAPI Complete API"

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/fastapi_db

# Security - CHANGE IN PRODUCTION!
SECRET_KEY=your-super-secret-key-change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**`.env`** (NEVER commit this!):

```bash
DEBUG=true
DATABASE_URL=postgresql://postgres:mysecretpassword@localhost:5432/fastapi_db
SECRET_KEY=dev-only-key-not-for-production-32chars
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**`.gitignore`:**

```gitignore
.env
venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
*.db
.DS_Store
```

---

## 2. Database Integration

### Step 2.1: Database Connection

**`app/database.py`:**

```python
"""
Database configuration with SQLAlchemy 2.0.
Why SQLAlchemy 2.0: Async support, type hints, modern Pythonic API.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

# For SQLite in-memory (testing only)
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL with connection pooling
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,  # Verify connections before use
        pool_size=10,        # Default connections
        max_overflow=20,     # Extra connections under load
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """Dependency to get database session.
    
    Yields a session that's automatically closed after the request.
    Why: Ensures connections are returned to pool, prevents leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
