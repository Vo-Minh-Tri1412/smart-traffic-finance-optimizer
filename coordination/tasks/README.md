# Task Manifests

Every write-capable agent task needs one TOML manifest in this directory.

Use `TASK-000-template.toml` as the starting point. The integrator should copy it, assign a unique
id, set `base_commit`, narrow `allowed_paths`, and list acceptance commands before work starts.

Validate a task with:

```powershell
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

## Current direction

The current product direction is **Smart Traffic Public Finance Optimization with SUMO-RL**.

Active/reader-relevant manifests:

- `006_reset_to_sumo_rl_traffic_finance.toml`: reset repo, docs, dependency stack, Drive
  workspace, deadlines, and contract to the current direction.
- `007_cleanup_coordination_history.toml`: cleanup record for removing pre-reset task noise.

Do not infer the current product direction from archived or deleted pre-reset task manifests.
The custom agent role files in `.codex/agents/` are still current role definitions, not old task
records.
