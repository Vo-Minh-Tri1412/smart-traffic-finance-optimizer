---
name: handoff-agent-work
description: Prepare clean multi-agent handoffs. Use when an agent has completed scoped work and needs to summarize changed files, validation commands, risks, open questions, and next integration steps.
---

# Handoff Agent Work

Use this skill at the end of scoped work.

1. Summarize the intent, branch, manifest id, and owner.
2. List changed files and confirm each is inside `allowed_paths`.
3. Include exact validation commands and observed outcomes.
4. Record risks, skipped checks, and decisions the integrator must make.
5. Update the manifest `handoff` table before requesting review.
6. Do not claim completion when acceptance commands were not run.

