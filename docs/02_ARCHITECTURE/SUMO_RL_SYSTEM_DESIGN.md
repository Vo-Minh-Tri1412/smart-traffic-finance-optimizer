# SUMO-RL System Design

## Architecture

```text
Traffic scenario inputs
        |
        v
SUMO network + demand files
        |
        v
SUMO-RL environment
        |
        +--> Fixed-time baseline
        +--> Rule-based adaptive baseline
        +--> RL agent
        |
        v
Simulation metrics
        |
        v
Public-finance evaluation
        |
        v
Dashboard/report for policy decision
```

## Core environment

The official environment is **SUMO-RL**. Do not use a custom simulator or an old OOP project as the
main environment unless the integrator explicitly changes this project decision.

SUMO-RL provides a Gymnasium/PettingZoo-compatible interface for traffic signal control. SUMO itself
must be installed as an external binary runtime.

## State, action, reward

Initial state candidates:

- queue length by incoming lane
- waiting time by lane or approach
- current traffic phase
- elapsed time in current phase
- emergency or event-demand flag, if scenario needs it

Initial action space:

- keep current phase
- switch to next legal phase

Initial reward:

- negative total waiting time
- negative queue length
- penalty for unsafe or too-frequent switching

Public-finance metrics are not the RL reward at first. They are evaluation metrics used after a
simulation run, so the team can explain budget implications without overfitting the RL objective.

## Baselines

Every RL result must be compared against:

- fixed-time controller
- simple rule-based adaptive controller

If the RL agent is unstable, the project can still demo the baselines and the public-finance layer,
but the final target remains SUMO-RL.

## Outputs

Required output tables:

- `simulation_summary`: scenario, controller, total waiting time, throughput, queue statistics
- `public_finance_summary`: scenario, controller, value-of-time saved, estimated benefit, caveats
- `budget_priority`: intersection/scenario, benefit estimate, implementation cost assumption, priority

## External runtime notes

Python dependencies are managed by `uv`.

SUMO is not a normal Python dependency. Local machines must install SUMO separately and expose:

- `sumo`
- `sumo-gui`
- `SUMO_HOME`

`uv run python -m ai_quantum_hvtc doctor` reports missing SUMO runtime as a warning so repository
checks can still run on machines that have not installed SUMO yet.
