# Smart Traffic Public Finance Optimizer

## One-sentence idea

Use SUMO-RL to optimize traffic signal timing in simulated intersections, then translate reduced
delay and congestion into public-finance evidence for prioritizing traffic infrastructure spending.

## Competition fit

Primary track: **AI for Public Policy and Public Finance**.

This is not a generic smart-traffic demo. The project must answer a public-finance question:

> With limited budget, which traffic signal interventions produce the highest social return?

## Product promise

The demo should help a public-sector analyst compare:

- fixed-time traffic lights
- simple rule-based adaptive control
- SUMO-RL traffic signal control

The public-finance layer should estimate:

- vehicle waiting time saved
- value of time saved
- fuel/emission proxy saved, when assumptions are available
- budget priority score by intersection or scenario

## Team split

CS owns:

- SUMO/SUMO-RL environment setup
- baseline controllers
- RL training/evaluation scripts
- reproducible metrics and reports
- demo/dashboard implementation

Economics/Public Finance owns:

- value-of-time assumptions
- cost categories and caveats
- policy scenarios
- budget-priority narrative
- judge-facing story and Q&A

## Non-goals for now

- No computer vision vehicle counting in MVP.
- No custom simulator as the main environment.
- No city-scale network until one SUMO-RL intersection is reproducible.
- No claim that simulation results are real-world causal proof.

## Success criteria

Week-1 success means:

- SUMO dependency status is explicit.
- A SUMO-RL sample or minimal environment path is defined.
- Fixed-time and rule-based baselines are specified.
- Economics can fill cost/scenario templates without coding.
- All active docs point to the traffic/public-finance direction.
