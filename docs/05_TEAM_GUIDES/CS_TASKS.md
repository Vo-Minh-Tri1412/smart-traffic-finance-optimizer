# CS Team Guide

## Main responsibilities

- Set up Python and SUMO/SUMO-RL.
- Build reproducible experiments.
- Compare fixed-time, rule-based, and RL controllers.
- Export readable reports for the Economics team.

## Week-1 tasks

1. Run:

   ```powershell
   uv sync --frozen
   uv run python -m ai_quantum_hvtc doctor
   ```

2. Install SUMO if `doctor` reports missing external runtime.
3. Confirm a SUMO-RL sample target and document required network/demand files.
4. Define output schema before training:
   - scenario
   - controller
   - total waiting time
   - average waiting time
   - throughput
   - max queue
   - public-finance assumptions used

## Engineering rules

- Do not add a custom simulator as the main environment.
- Do not claim RL is better without fixed-time and rule-based baselines.
- Keep all reports understandable to non-CS teammates.
- Store large generated outputs outside Git and share through Drive.
