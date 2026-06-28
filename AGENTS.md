# AI Quantum HVTC Agent Governance

This repository now targets **Smart Traffic Public Finance Optimization**:

- SUMO-RL is the official simulation/RL environment.
- The project belongs to AI for Public Policy and Public Finance.
- The demo must connect traffic signal optimization to public-finance decisions.

Do not reintroduce the previous macro-warning stack or a custom traffic simulator as the main
environment unless the integrator records a new approved direction.

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
- `evidence-researcher`: read-only source collection, competition facts, public-finance evidence,
  citations, and caveats.
- `system-architect`: read-only SUMO-RL architecture, interfaces, risks, and contracts.
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

## Project guardrails

- Use SUMO-RL as the main environment.
- Keep computer vision as future work unless explicitly approved.
- Compare RL with fixed-time and rule-based controllers.
- Public-finance assumptions must be sourced, estimated, or clearly marked as placeholders.
- Large simulation outputs, model checkpoints, and local SUMO artifacts stay out of Git.
- Google Drive is the handoff surface for non-code teammates.

## Git safety

- Do not run `git reset --hard`, `git clean`, or force-push.
- Ask the user before pushing or creating a PR.
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
