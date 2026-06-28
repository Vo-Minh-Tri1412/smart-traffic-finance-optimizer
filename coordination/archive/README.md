# Coordination Archive

This folder records cleanup decisions for old coordination artifacts.

On 2026-06-28, after the project direction changed to **Smart Traffic Public Finance Optimization
with SUMO-RL**, the old pre-reset task manifests were removed from `coordination/tasks/` to avoid
confusing future agents.

Removed pre-reset manifests:

- `001_setup_infrastructure.toml`
- `002_document_workflow.toml`
- `003_week1_plan.toml`
- `004_update_docs_mews.toml`
- `005_data_template_scaffold.toml`

Reason:

- They described earlier setup phases and/or a product direction superseded by
  `006_reset_to_sumo_rl_traffic_finance.toml`.
- Their useful outcomes were folded into the current docs, Drive workspace, data templates, and
  SUMO-RL project governance.

Current agents should read `coordination/tasks/README.md`, `AGENTS.md`, and
`docs/01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md` first.
