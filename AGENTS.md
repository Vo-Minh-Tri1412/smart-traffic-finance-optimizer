# AI Quantum HVTC Agent Governance

This repository is a technical scaffold only. Product direction is pending, so do not add
domain-specific data, models, dashboards, feature folders, or named product assumptions until the
integrator records an approved direction.

## Non-negotiable write rules

- No task manifest, no file writes.
- Every write task must have one TOML manifest in `coordination/tasks/`.
- Each task manifest must declare `id`, `owner`, `branch`, `base_commit`, `allowed_paths`,
  `dependencies`, `acceptance_commands`, `status`, and `handoff`.
- A writer may only change files covered by that task's `allowed_paths`.
- Shared files are owned only by `integrator`: `AGENTS.md`, `README.md`, `pyproject.toml`,
  `uv.lock`, `.github/**`, `.codex/**`, `coordination/**`, and `scripts/**`.
- No two writer agents may own the same path range at the same time.
- Long-lived write tasks use separate worktrees after the bootstrap commit.
- Parallel subagents are read-only unless the integrator assigns a manifest and path ownership.

## Roles

- `integrator`: owns shared config, lockfiles, contracts, CI, governance, and merges.
- `evidence-researcher`: read-only source collection, evidence tables, citations, and caveats.
- `system-architect`: read-only design, interfaces, risks, and contracts.
- `implementation-worker`: writes only inside assigned paths from a task manifest.
- `verification-auditor`: read-only tests, reproducibility checks, review, and acceptance evidence.

## Required workflow for write tasks

1. Create or update a task manifest under `coordination/tasks/`.
2. Confirm `base_commit` equals the commit where ownership was assigned.
3. Declare narrow `allowed_paths`; avoid shared paths unless `owner = "integrator"`.
4. Make changes only on the declared branch/worktree.
5. Run every command in `acceptance_commands`.
6. Run `uv run python scripts/admin/validate_agent_tasks.py --task <manifest>`.
7. Fill `handoff` with summary, validation, risks, and follow-up before requesting integration.

## Git safety

- Do not run `git reset --hard`, `git clean`, or force-push.
- Ask the user before pushing or creating a PR, except for this initial bootstrap push that the user
  explicitly approved.
- Preserve unrelated changes. If the worktree is mixed, stage only files in the active task.

## Baseline validation

Run these before handoff when relevant:

```powershell
uv sync --frozen
uv run python -m ai_quantum_hvtc doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy ai_quantum_hvtc scripts
uv run pytest
```

