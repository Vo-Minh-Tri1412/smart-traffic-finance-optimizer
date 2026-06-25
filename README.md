# AI Quantum HVTC Challenge

Technical scaffold for Vietnam Inflation Radar 2026.

This repository is a private bootstrap for the AI Quantum HVTC challenge. It now contains automated Google Drive sync scripts for cross-team collaboration between Economics and CS.

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
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

The first scaffold commit is allowed on `main`. After that, long-running write work should use a
separate branch/worktree and a handoff manifest.

## Data & Drive Workflow

This project connects the CS (Computer Science) team and the Economics team via Google Drive.

1. **Google Drive Setup**: Both teams mount `AI Quantum HVTC — Team Workspace` using Google Drive Desktop.
2. **Economics Handoff**: The Economics team places finalized datasets in `03_Shared_Handoffs/From_Econ_To_CS/01_Final_Training_Data`.
3. **CS Pull Data**: The CS team runs the sync script locally to pull this data:
   ```powershell
   uv run python scripts/cloud/sync_drive.py --pull-data --apply
   ```
4. **CS Push Reports**: After training and generating CSV reports in the local `outputs/` folder, the CS team pushes them back to Economics:
   ```powershell
   uv run python scripts/cloud/sync_drive.py --push-reports --apply
   ```
5. **Colab Integration**: When using Google Colab for heavy training, the CS team can natively mount Drive (`drive.mount('/content/drive')`) and read/write directly to `02_CS_Workspace` and `03_Shared_Handoffs` without needing the sync script.
