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
Public-value scoring layer
        |
        v
Budget allocation/ranking layer
        |
        v
Dashboard/report for policy decision
```

## Core environment

The official environment is **SUMO-RL**. Do not use a custom simulator or an old OOP project as the
main environment unless the integrator explicitly changes this project decision.

SUMO-RL provides a Gymnasium/PettingZoo-compatible interface for traffic signal control. SUMO itself
must be installed as an external binary runtime.

## State, action, reward, and public-value objective

Initial state candidates:

- queue length by incoming lane
- waiting time by lane or approach
- current traffic phase
- elapsed time in current phase
- emergency or event-demand flag, if scenario needs it

Initial action space:

- keep current phase
- switch to next legal phase

Initial RL reward:

- negative total waiting time
- negative queue length
- penalty for unsafe or too-frequent switching

The initial RL reward can stay traffic-focused so training remains stable. However, the project
objective is not merely "reduce delay." The final product objective is a public-value score used to
rank policies and investments:

```text
public_value_score
  = delay_saved_minutes * value_of_time
  + optional fuel_or_emission_proxy
  - implementation_cost
  - operating_or_maintenance_cost
  - fairness_or_service_penalty
```

So there are two linked layers:

1. **Control layer**: fixed-time, rule-based, or RL controls traffic lights in SUMO.
2. **Public-finance layer**: converts the resulting metrics into benefit/cost and budget-priority
   decisions.

This avoids the weak pattern of building a smart-city demo and only adding economics in the slides.
The economics assumptions directly shape the scoring, scenario sensitivity, and investment
recommendation.

## Mini-city scope

The smoke test starts with a single intersection only to verify the runtime. The demo target should
be a 2x2 or 3x3 mini-city network:

- 2x2 = four signalized intersections connected as a small grid
- each signal can be a separate SUMO-RL/PettingZoo agent
- each intersection can receive a public-value score and budget priority
- city-scale OpenStreetMap import remains future work after the mini-city pipeline is stable

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
- `budget_priority`: intersection/scenario, benefit estimate, implementation cost assumption, net
  public value, priority rank
- `sensitivity_summary`: assumption set, changed parameter, decision change, caveat

## External runtime notes

Python dependencies are managed by `uv`.

SUMO is not a normal Python dependency. Local machines must install SUMO separately and expose:

- `sumo`
- `sumo-gui`
- `SUMO_HOME`

`uv run python -m ai_quantum_hvtc doctor` reports missing SUMO runtime as a warning so repository
checks can still run on machines that have not installed SUMO yet.
