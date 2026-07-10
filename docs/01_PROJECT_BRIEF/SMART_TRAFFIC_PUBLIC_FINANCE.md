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
- shared multi-agent RL with optional frame-stack/LSTM memory for the large Quận 7/ROI network
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

Lead/CS owns:

- SUMO/SUMO-RL environment setup
- fixed-time and rule-based baseline controllers
- SUMO metric, trace, and report export
- Godot/render technical pipeline
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

Reward and public-value are shared. Economics defines the policy meaning and assumptions; CS turns
those definitions into executable config, formulas, tests, and reports.

## Non-goals for now

- YOLO is not a prerequisite for the first camera-partial-observation RL experiment; calibrated
  geometry-based optical visibility may be used first.
- No custom simulator as the main environment.
- The package fixture is only a test input; the target is the full Quận 7 SUMO network or a reviewed
  large ROI.
- No claim that simulation results are real-world causal proof.

## Success criteria

Near-term success means:

- SUMO backend can run fixed-time and rule-based baselines on the district spec.
- Baseline reports are readable by Economics without opening code.
- Godot can replay a SUMO trace with placeholder scenes.
- Economics can fill cost/scenario templates without coding.
- CS and Economics agree on reward/public-value v0 before RL claims.
