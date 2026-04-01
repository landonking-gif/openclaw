# Skill Reference — Kael (general-2)
*Quick lookup for available summarization tools*

## Primary Skills

### summarize
**Use for:** URLs, PDFs, videos, YouTube, audio files
```bash
summarize <url>
summarize <file.pdf>
summarize <video.mp4>
```
**Models:** gemini-3-pro (default), gpt-5.2, kimi-k2.5

### oracle
**Use for:** Codebase questions, large context bundling
```bash
oracle "explain this codebase" --include "*.ts"
```
**Best for:** Technical deep-dives

### web_search
**Use for:** Research, fact-checking
```bash
web_search "latest AI developments"
```

### web_fetch
**Use for:** Page extraction, markdown conversion
```bash
web_fetch <url>
```

## Secondary Tools

| Tool | When | Notes |
|------|------|-------|
| `codex-cli` | Code tasks | Spawn Codex subagent |
| `github` | PRs, issues | `gh pr list` etc |
| `nano-pdf` | PDF editing | Natural language edits |
| `openai-whisper` | Audio transcription | Local, no API key |
| `video-frames` | Video analysis | Extract frames |
| `songsee` | Audio viz | Spectrograms |

## Model Selection Guide

```
Speed needed?     → gemini-3-flash
Quality needed?   → gpt-5.2 / claude-4-sonnet
Code heavy?       → claude-4-sonnet / cred opus
Cost sensitive?   → kimi-k2.5 (free via NVAPI)
```

## Common Patterns

### Summarize + Store
```bash
summarize <url> > output.md
cat output.md >> MEMORY.md
```

### Meeting → Action Items
```bash
# Use whispers/transcription, then:
summarize meeting.txt --focus "action items"
```

### Code Review Flow
```bash
oracle "review this PR" --include "changed_files/*"
# Then template → code-review-summary.md
```

---
*Keep this updated when adding new skills*
