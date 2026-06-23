---
name: audit-reproducibility
description: Audit whether repository work can be reproduced from a fresh clone. Use for read-only verification of setup, lockfiles, commands, manifests, tests, CI assumptions, and handoff evidence.
---

# Audit Reproducibility

Use this skill for read-only reproducibility checks.

1. Start from the documented commands in `README.md` and `AGENTS.md`.
2. Verify lockfile use with `uv sync --frozen`.
3. Run the doctor, format check, lint, type check, tests, and any task acceptance commands.
4. Confirm task manifests validate and changed files stay inside ownership boundaries.
5. Report exact commands, observed outputs, environment details, and blockers.
6. Do not edit files during the audit.

