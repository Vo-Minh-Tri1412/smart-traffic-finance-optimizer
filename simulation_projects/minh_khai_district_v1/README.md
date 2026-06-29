# Minh Khai District v1

Spec-driven simulation workspace for the Smart Traffic Public Finance Optimizer.

This folder is intentionally small and reproducible:

- `specs/district_spec.json` is the source of truth for the district, flows, scenarios, controllers,
  finance assumptions, and investment candidates.
- `specs/` stores versioned district specs.
- `outputs/` is for generated JSON run outputs.
- `reports/` is for generated CSV/Markdown handoffs.
- `sumo_generated/` is for local SUMO XML/network artifacts and is ignored by Git except `.gitkeep`.

Generated outputs are ignored by Git except `.gitkeep` placeholders.

Example:

```powershell
uv run python -m ai_quantum_hvtc simulate validate --spec simulation_projects/minh_khai_district_v1/specs/district_spec.json
uv run python -m ai_quantum_hvtc simulate run --spec simulation_projects/minh_khai_district_v1/specs/district_spec.json --scenario industrial_shift_in --controller rule_based --engine reference --out simulation_projects/minh_khai_district_v1/outputs/run_industrial_rule_based.json --trace-out simulation_projects/minh_khai_district_v1/outputs/run_industrial_rule_based.trace.jsonl
```
