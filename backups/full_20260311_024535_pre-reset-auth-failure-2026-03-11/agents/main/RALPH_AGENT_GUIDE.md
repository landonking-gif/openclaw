# Ralph Coding Agent - Quick Reference

## What is Ralph?
Ralph is the autonomous coding agent within the OpenClaw Army system. It implements PRD-driven development with self-improving capabilities.

## Architecture
```
PRD → Ralph → Code → Tests → Review → Merge
```

## Key Capabilities
- Reads Product Requirements Documents (PRDs)
- Generates implementation code
- Creates tests automatically
- Self-corrects based on CI/CD feedback
- Integrates with memory service for learning

## Workflow
1. **Input**: PRD file or PR description
2. **Planning**: Breaks down requirements into tasks
3. **Implementation**: Writes code with tests
4. **Validation**: Runs tests, checks CI
5. **Refinement**: Iterates based on feedback
6. **Output**: PR with passing CI

## Configuration
- **Workspace**: `~/openclaw-army/agents/ralph/`
- **Model**: Claude Code / Codex CLI integration
- **Memory**: Connected to 18820 memory service
- **Triggers**: PR creation, manual assignment

## Usage
```bash
# Trigger via orchestrator
curl http://localhost:18830/tasks \
  -H "Content-Type: application/json" \
  -d '{"agent": "ralph", "task": "implement", "pr": "<url>"}'
```

## Integration Points
- GitHub API for PR operations
- Memory service for context persistence
- Cost tracker for usage monitoring
- Notification service for status updates

---
*Version: 2026.03.07*
