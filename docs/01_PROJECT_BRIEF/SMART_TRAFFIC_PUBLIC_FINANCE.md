# Smart Traffic Public Finance Optimizer

## One-sentence idea

Use SUMO-RL to optimize traffic signal timing in simulated urban networks, then convert traffic
outcomes into a public-value and budget-allocation decision layer for public infrastructure
spending.

## Competition fit

Primary track: **AI for Public Policy and Public Finance**.

This is not a generic smart-traffic demo with an economics slide at the end. The project must answer
a public-finance question inside the technical workflow:

> With limited budget, which traffic signal interventions produce the highest social return?

That means the economics work defines the objective the system is evaluated against, not just the
story used in the final presentation.

## Product promise

The demo should help a public-sector analyst compare traffic-control policies and investment
choices:

- fixed-time traffic lights
- simple rule-based adaptive control
- SUMO-RL traffic signal control
- budget-constrained rollout choices across intersections

The public-finance layer is a first-class technical layer. It should estimate:

- vehicle waiting time saved
- value of time saved
- fuel/emission proxy saved, when assumptions are available
- implementation and operating cost assumptions
- net public value under each scenario
- budget priority score by intersection or scenario

Core technical objective:

```text
public_value_score
  = monetized/social benefit from reduced delay and queues
  + optional fuel/emission benefit proxy
  - implementation and operating cost assumptions
  - fairness or service-level penalties
```

The RL policy may initially learn a traffic-safe reward such as reduced waiting time, but the product
decision is made by the public-value score and budget-allocation layer. This keeps the MVP stable
while ensuring the economic logic is part of the system, not decorative narration.

## Team split

CS owns:

- SUMO/SUMO-RL environment setup
- baseline controllers
- RL training/evaluation scripts
- reproducible metrics and reports
- public-value scoring implementation
- budget allocation/ranking implementation
- demo/dashboard implementation

Economics/Public Finance owns:

- value-of-time assumptions
- cost categories and caveats
- policy scenarios
- public-value formula and sensitivity ranges
- budget constraint logic
- budget-priority narrative
- judge-facing story and Q&A

## Non-goals for now

- No computer vision vehicle counting in MVP.
- No custom simulator as the main environment.
- No city-scale network until a 2x2/3x3 mini-city is reproducible and metrics are stable.
- No claim that simulation results are real-world causal proof.

## Success criteria

Week-1 success means:

- SUMO dependency status is explicit.
- A SUMO-RL sample or minimal environment path is defined.
- Fixed-time and rule-based baselines are specified.
- Economics can fill cost/scenario templates without coding.
- All active docs point to the traffic/public-finance direction.
