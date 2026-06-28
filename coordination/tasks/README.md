# Task Manifests

Every write-capable agent task needs one TOML manifest in this directory.

Use `TASK-000-template.toml` as the starting point. The integrator should copy it, assign a unique
id, set `base_commit`, narrow `allowed_paths`, and list acceptance commands before work starts.

Validate a task with:

```powershell
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

Current active project direction is recorded in
`006_reset_to_sumo_rl_traffic_finance.toml`. Earlier task manifests are historical setup records and
must not be used to infer the current product direction.
