---
name: coordinate-agent-task
description: Coordinate repo-local multi-agent work for this challenge. Use when assigning, reviewing, or updating task manifests, ownership, allowed paths, dependencies, and acceptance commands before any agent writes files.
---

# Coordinate Agent Task

Use this skill before any write-capable agent changes repository files.

1. Read `AGENTS.md` and the relevant manifest in `coordination/tasks/`.
2. Reject write work when no manifest exists.
3. Confirm `id`, `owner`, `branch`, `base_commit`, `allowed_paths`, `dependencies`,
   `acceptance_commands`, `status`, and `handoff` are present.
4. Keep `allowed_paths` narrow. Assign shared files only to `owner = "integrator"`.
5. Ensure no other active writer owns overlapping paths.
6. Prefer read-only subagents for research, design, and audit.
7. Before handoff, run:

```powershell
uv run python scripts/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

