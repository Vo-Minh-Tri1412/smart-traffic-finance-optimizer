# Smart Traffic Public Finance Optimizer

SUMO-RL traffic signal optimization for the AI Quantum HVTC challenge.

The project uses reinforcement learning to control traffic lights in SUMO simulations, then turns
simulation improvements into public-finance evidence: social cost saved, budget-priority reasoning,
and policy scenarios for public-sector decision makers.

Primary competition track: **AI for Public Policy and Public Finance**.

## Current direction

Read these first:

- `docs/01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md`
- `docs/02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md`
- `docs/03_COMPETITION/AI_QUANTUM_HVTC_FACTS.md`
- `docs/04_WEEKLY_PLANS/WEEK1_PLAN.md`

## Quick start

Ensure Python 3.12 and `uv` are installed.

```powershell
uv sync --frozen
uv run python -m ai_quantum_hvtc doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy ai_quantum_hvtc scripts
uv run pytest
```

`doctor` checks Python package readiness and reports SUMO binary readiness. SUMO itself is an
external runtime, so install it separately before running simulations:

- `sumo`
- `sumo-gui`
- `SUMO_HOME`

## Team workflow

Read `AGENTS.md` before changing files. Every repository write task needs a manifest in
`coordination/tasks/` and must pass:

```powershell
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

## Drive workflow

Google Drive workspace: `AI Quantum HVTC — Team Workspace`

Economics/Public Finance handoff to CS:

- `03_Shared_Handoffs/From_Econ_To_CS/01_Cost_Assumptions`
- `03_Shared_Handoffs/From_Econ_To_CS/02_Traffic_Scenarios`

CS handoff to Economics:

- `03_Shared_Handoffs/From_CS_To_Econ/01_Simulation_Results`
- `03_Shared_Handoffs/From_CS_To_Econ/02_Public_Finance_Summary`

Useful sync commands:

```powershell
uv run python scripts/cloud/sync_drive.py --status
uv run python scripts/cloud/sync_drive.py --pull-econ --apply
uv run python scripts/cloud/sync_drive.py --push-results --apply
uv run python scripts/cloud/sync_drive.py --push-finance-reports --apply
```

## Scope guardrails

- SUMO-RL is the official traffic environment.
- Do not add a custom simulator as the main environment.
- Do not add computer vision to the MVP unless the integrator records a new decision.
- Do not claim real-world causal savings from simulation alone.
- Compare RL against fixed-time and rule-based baselines.
