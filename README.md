# AI Quantum HVTC Challenge

Technical scaffold; product direction pending.

This repository is a private, neutral bootstrap for the AI Quantum HVTC challenge. It does not yet
contain data, models, dashboards, notebooks, or a committed product idea.

## Current scope

- Python 3.12 project managed by `uv`.
- Minimal package: `ai_quantum_hvtc`.
- Multi-agent governance for safe parallel work.
- CI on Ubuntu and Windows.

## Quick start

```powershell
uv sync --frozen
uv run python -m ai_quantum_hvtc doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy ai_quantum_hvtc scripts
uv run pytest
```

## Agent workflow

Read `AGENTS.md` before changing files. Future write tasks must have a manifest in
`coordination/tasks/` and must pass:

```powershell
uv run python scripts/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

The first scaffold commit is allowed on `main`. After that, long-running write work should use a
separate branch/worktree and a handoff manifest.

