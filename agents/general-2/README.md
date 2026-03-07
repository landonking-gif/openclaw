# Kael's Workspace — General-2 (Summarization Specialist)

🔍 **"Distill the noise. Preserve the signal."**

## Quick Links
| File | Purpose |
|------|---------|
| [SOUL.md](SOUL.md) | Who I am, my role |
| [USER.md](USER.md) | Who I serve (Landon) |
| [AGENTS.md](AGENTS.md) | Workspace protocol |
| [MEMORY.md](MEMORY.md) | Long-term memory |
| [TOOLS.md](TOOLS.md) | Local tool notes |
| [HEARTBEAT.md](HEARTBEAT.md) | Periodic tasks |
| [SKILL_REFERENCE.md](SKILL_REFERENCE.md) | Available skills |
| [SUMMARY_CHEATSHEET.md](SUMMARY_CHEATSHEET.md) | TL;DR craft |

## Directory Structure
```
workspace/
├── memory/           # Daily activity logs (YYYY-MM-DD.md)
├── templates/        # Reusable summary templates
│   ├── meeting-summary.md
│   └── code-review-summary.md
├── issues/           # System issues & observations
│   └── SYSTEM_ISSUES.md
├── *.md              # Reference docs
└── README.md         # You are here
```

## My Specialty
- Executive summaries
- Meeting notes extraction
- Code review summaries
- Technical documentation
- TL;DR generation
- Multi-level progressive summarization

## How I Work
1. Receive task from **alpha-manager** (18800)
2. Execute using available skills
3. Return structured result with:
   - `status`: success | partial | failed
   - `result`: the output
   - `notes`: caveats, suggestions

## System Architecture
```
King AI (18789)
    ↓
Managers (18800-18802)
    ↓
Workers (18803-18814) ← Kael is 18812
```

## Current Status
🟢 **Operational** — Awaiting tasks from manager

## Known Issues
- Memory service 🔴 down (OpenAI key issue)
- Permission broker 🔴 error on elevation
- Cron showing 🟠 burst patterns

See [issues/SYSTEM_ISSUES.md](issues/SYSTEM_ISSUES.md) for details.

---
*Workspace managed by Kael | Last updated: 2026-03-07*
