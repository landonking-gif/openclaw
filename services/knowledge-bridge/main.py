"""
Knowledge Bridge — Obsidian Vault API for OpenClaw Army
Port: 18850

REST API that lets agents create, search, read, and tag notes
in the shared Obsidian vault at ../vault/
"""

import os
import re
import json
import glob
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

# ── Configuration ─────────────────────────────────────────────────────────────

ARMY_HOME = os.environ.get("ARMY_HOME", str(Path(__file__).resolve().parent.parent.parent))
VAULT_PATH = Path(os.environ.get("VAULT_PATH", os.path.join(ARMY_HOME, "data", "obsidian database")))
TEMPLATES_PATH = VAULT_PATH / "templates"

VALID_FOLDERS = [
    "agents", "research", "code-patterns", "decisions",
    "daily-logs", "projects", "inbox",
]

VALID_AGENTS = [
    "king-ai", "alpha-manager", "beta-manager", "gamma-manager",
    "coding-1", "coding-2", "coding-3", "coding-4",
    "agentic-1", "agentic-2", "agentic-3", "agentic-4",
    "general-1", "general-2", "general-3", "general-4",
]

app = FastAPI(
    title="Knowledge Bridge",
    description="Obsidian vault API for the OpenClaw Army",
    version="1.0.0",
)


# ── Models ────────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str = Field(..., max_length=200)
    folder: str = Field(default="inbox")
    content: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    agent: str = Field(default="unknown")
    template: Optional[str] = Field(default=None)


class NoteUpdate(BaseModel):
    path: str
    content: str
    agent: str = Field(default="unknown")


class NoteAppend(BaseModel):
    path: str
    section: str = Field(default="")
    content: str
    agent: str = Field(default="unknown")


class SearchResult(BaseModel):
    path: str
    title: str
    snippet: str
    tags: list[str]
    modified: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Produce a safe filename from a title."""
    safe = re.sub(r'[^\w\s\-]', '', name)
    safe = re.sub(r'\s+', '-', safe.strip())
    return safe[:100].lower()


def _resolve_path(rel_path: str) -> Path:
    """Resolve a relative vault path safely — prevent directory traversal."""
    resolved = (VAULT_PATH / rel_path).resolve()
    if not str(resolved).startswith(str(VAULT_PATH.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            result[key] = val
    return result


def _build_frontmatter(title: str, agent: str, tags: list[str], extra: dict | None = None) -> str:
    """Build YAML frontmatter string."""
    tag_str = ", ".join(tags) if tags else ""
    lines = [
        "---",
        f'title: "{title}"',
        f'date: "{date.today().isoformat()}"',
        f'agent: "{agent}"',
        f"tags: [{tag_str}]",
    ]
    if extra:
        for k, v in extra.items():
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines)


def _apply_template(template_name: str, variables: dict) -> str:
    """Load a template and substitute {{variables}}."""
    tmpl_file = TEMPLATES_PATH / f"{template_name}.md"
    if not tmpl_file.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    text = tmpl_file.read_text()
    for key, val in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))
    return text


def _search_files(query: str, folder: str | None, agent: str | None, tags: list[str] | None) -> list[SearchResult]:
    """Full-text search across vault markdown files."""
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE) if query else None

    search_root = VAULT_PATH
    if folder:
        search_root = VAULT_PATH / folder

    for md_file in sorted(search_root.rglob("*.md")):
        # Skip hidden dirs and templates
        rel = md_file.relative_to(VAULT_PATH)
        parts = rel.parts
        if any(p.startswith(".") for p in parts):
            continue
        if parts[0] == "templates":
            continue

        try:
            text = md_file.read_text()
        except OSError:
            continue

        fm = _parse_frontmatter(text)

        # Filter by agent
        if agent and fm.get("agent", "") != agent:
            continue

        # Filter by tags
        if tags:
            note_tags = fm.get("tags", [])
            if isinstance(note_tags, str):
                note_tags = [note_tags]
            if not any(t in note_tags for t in tags):
                continue

        # Filter by query
        if pattern and not pattern.search(text):
            continue

        # Build snippet
        snippet = ""
        if pattern:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 80)
                end = min(len(text), match.end() + 80)
                snippet = text[start:end].replace("\n", " ").strip()
        else:
            # First 150 chars of body (skip frontmatter)
            body_start = text.find("---", 3)
            body = text[body_start + 3:].strip() if body_start > 0 else text
            snippet = body[:150].replace("\n", " ").strip()

        stat = md_file.stat()
        note_tags = fm.get("tags", [])
        if isinstance(note_tags, str):
            note_tags = [note_tags]

        results.append(SearchResult(
            path=str(rel),
            title=fm.get("title", md_file.stem),
            snippet=snippet,
            tags=note_tags,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        ))

    return results


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "knowledge-bridge",
        "vault": str(VAULT_PATH),
        "vault_exists": VAULT_PATH.exists(),
    }


@app.post("/notes", status_code=201)
async def create_note(note: NoteCreate):
    """Create a new note in the vault."""
    if note.agent not in VALID_AGENTS and note.agent != "unknown":
        raise HTTPException(status_code=400, detail=f"Unknown agent: {note.agent}")

    # Determine target folder
    folder = note.folder
    if folder.startswith("agents/") or folder == "agents":
        if note.agent in VALID_AGENTS:
            folder = f"agents/{note.agent}"
    
    # Validate folder is under vault
    target_dir = _resolve_path(folder)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = _sanitize_filename(note.title) + ".md"
    filepath = target_dir / filename

    # Don't overwrite — append number if exists
    counter = 1
    while filepath.exists():
        filepath = target_dir / f"{_sanitize_filename(note.title)}-{counter}.md"
        counter += 1

    # Build content
    if note.template:
        variables = {
            "title": note.title,
            "date": date.today().isoformat(),
            "agent": note.agent,
        }
        body = _apply_template(note.template, variables)
        # Replace content placeholder if template has one
        if note.content:
            body += f"\n\n{note.content}"
    else:
        agent_tag = f"agent/{note.agent}" if note.agent != "unknown" else ""
        all_tags = list(note.tags)
        if agent_tag and agent_tag not in all_tags:
            all_tags.append(agent_tag)

        frontmatter = _build_frontmatter(note.title, note.agent, all_tags)
        body = f"{frontmatter}\n\n# {note.title}\n\n{note.content}\n"

    filepath.write_text(body)
    rel_path = filepath.relative_to(VAULT_PATH)

    return {
        "status": "created",
        "path": str(rel_path),
        "vault_path": str(filepath),
    }


@app.get("/notes")
async def get_note(path: str = Query(...)):
    """Read a specific note by vault-relative path."""
    filepath = _resolve_path(path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    
    text = filepath.read_text()
    fm = _parse_frontmatter(text)

    return {
        "path": path,
        "frontmatter": fm,
        "content": text,
    }


@app.put("/notes")
async def update_note(note: NoteUpdate):
    """Overwrite a note's content entirely."""
    filepath = _resolve_path(note.path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Note not found: {note.path}")
    filepath.write_text(note.content)
    return {"status": "updated", "path": note.path}


@app.post("/notes/append")
async def append_to_note(note: NoteAppend):
    """Append content to a note, optionally under a specific section header."""
    filepath = _resolve_path(note.path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Note not found: {note.path}")

    text = filepath.read_text()

    if note.section:
        # Find the section header and append after it
        pattern = re.compile(rf"^(#{1,6}\s+{re.escape(note.section)}\s*$)", re.MULTILINE)
        match = pattern.search(text)
        if match:
            insert_pos = match.end()
            text = text[:insert_pos] + f"\n{note.content}" + text[insert_pos:]
        else:
            # Section not found — append at end with header
            text += f"\n\n## {note.section}\n{note.content}\n"
    else:
        text += f"\n{note.content}\n"

    filepath.write_text(text)
    return {"status": "appended", "path": note.path}


@app.get("/search")
async def search_notes(
    q: str = Query(default=""),
    folder: Optional[str] = Query(default=None),
    agent: Optional[str] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Full-text search across vault notes."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    results = _search_files(q, folder, agent, tag_list)
    return {"results": results[:limit], "total": len(results)}


@app.get("/recent")
async def recent_notes(
    agent: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get most recently modified notes."""
    results = _search_files("", folder, agent, None)
    # Sort by modified descending
    results.sort(key=lambda r: r.modified, reverse=True)
    return {"results": results[:limit]}


@app.get("/agents/{agent_name}/notes")
async def agent_notes(agent_name: str, limit: int = Query(default=20, ge=1, le=100)):
    """Get all notes written by a specific agent."""
    if agent_name not in VALID_AGENTS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
    results = _search_files("", None, agent_name, None)
    results.sort(key=lambda r: r.modified, reverse=True)
    return {"agent": agent_name, "results": results[:limit], "total": len(results)}


@app.get("/tags")
async def list_tags():
    """List all unique tags used across the vault."""
    all_tags: set[str] = set()
    for md_file in VAULT_PATH.rglob("*.md"):
        rel = md_file.relative_to(VAULT_PATH)
        if any(p.startswith(".") for p in rel.parts):
            continue
        try:
            text = md_file.read_text()
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        all_tags.update(tags)
    return {"tags": sorted(all_tags)}


@app.get("/stats")
async def vault_stats():
    """Get vault statistics."""
    total_notes = 0
    by_folder: dict[str, int] = {}
    by_agent: dict[str, int] = {}

    for md_file in VAULT_PATH.rglob("*.md"):
        rel = md_file.relative_to(VAULT_PATH)
        parts = rel.parts
        if any(p.startswith(".") for p in parts):
            continue
        if parts[0] == "templates":
            continue

        total_notes += 1
        top_folder = parts[0] if len(parts) > 1 else "root"
        by_folder[top_folder] = by_folder.get(top_folder, 0) + 1

        try:
            text = md_file.read_text()
            fm = _parse_frontmatter(text)
            agent = fm.get("agent", "unknown")
            if isinstance(agent, str) and agent:
                by_agent[agent] = by_agent.get(agent, 0) + 1
        except OSError:
            pass

    return {
        "total_notes": total_notes,
        "by_folder": by_folder,
        "by_agent": by_agent,
        "vault_path": str(VAULT_PATH),
    }


@app.post("/daily-log")
async def create_daily_log(agent: str = Query(...)):
    """Create or get today's daily log for an agent."""
    if agent not in VALID_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent}")

    today = date.today().isoformat()
    filename = f"{today}-{agent}.md"
    log_dir = VAULT_PATH / "daily-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / filename

    if filepath.exists():
        return {"status": "exists", "path": f"daily-logs/{filename}", "content": filepath.read_text()}

    variables = {"date": today, "agent": agent}
    content = _apply_template("daily-log", variables)
    filepath.write_text(content)

    return {"status": "created", "path": f"daily-logs/{filename}"}
