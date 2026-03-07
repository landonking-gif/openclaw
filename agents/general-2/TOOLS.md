# TOOLS.md — General-2 (Kael)
Local notes for summarization work.

## Skills I Use Most
| Skill | Purpose | Trigger Phrases |
|-------|---------|-----------------|
| `summarize` | URLs, YouTube, PDFs | "Summarize this link" |
| `oracle` | Codebase questions | Bundle context for GPT-5.2 Pro |
| `web_search` | Research | "Search for..." |
| `web_fetch` | Page extraction | "Fetch this URL" |

## Key Aliases
- `summarize` → steipete/tap/summarize
- `oracle` → @steipete/oracle
- `nv`/`llm` → Local CLI shortcuts for models

## Preferred Models (via summarize.sh)
- **Fast:** google/gemini-3-flash-preview
- **Quality:** openai/gpt-5.2
- **Code:** anthropic/claude-4-sonnet

## Common File Paths
- Logs: `/Users/landonking/openclaw-army/agents/*/memory/`
- Skills: `/opt/homebrew/lib/node_modules/openclaw/skills/`
- Workspace: `/Users/landonking/openclaw-army/agents/general-2/`

## API Keys (env var based)
- `GEMINI_API_KEY` — For summarize.sh default model
- `OPENAI_API_KEY` — For GPT-5.2 runs
- `ANTHROPIC_API_KEY` — For Claude access
