# QUBO and RL Joint Optimization

## Selected first protocol (2026-09-19)

The first delivery now selects **frozen shared mask-conditioned policy evaluation**, not retraining
per mask and not online alternating optimization. Begin with 8 eligible signals while all traffic
continues on the unchanged 169-TLS source network. The checkpoint and evaluator stay fixed throughout
singleton/pair fitting and held-out testing. See [measurement protocol](MAP_AWARE_QUBO.md) for the
37 configurations, seed separation and portfolio validation, and
[System delivery plan](SYSTEM_DELIVERY_PLAN.md) for dependency gates.

The broader alternating loop below remains future research, not a required first-delivery feature.
If later fine-tuning a selected mask, treat it as a separate experiment with a new checkpoint and
evaluation record; do not reuse old coefficient provenance as if the policy had not changed.

## Decision

QUBO and RL should be linked through a bilevel or alternating workflow, not collapsed into one
monolithic model from the beginning.

- QUBO chooses the long-horizon investment/control subset under budget.
- RL controls signal phases during each SUMO episode.
- The traffic network couples the two decisions, so QUBO coefficients must eventually include
  measured interaction benefits between corridors and intersections.

For 160 candidate signals, the investment space contains `2^160` subsets. Exhaustive RL retraining
for every subset is impossible. The practical target is a policy that can condition on an
`upgrade_mask` or share parameters across local signal agents, combined with a surrogate/QUBO that
is updated from a carefully sampled set of SUMO evaluations.

## Proposed loop

```text
candidate mask x and budget
  -> shared/conditional RL policy π_x
  -> SUMO evaluation over scenarios and seeds
  -> network metrics and public-value score
  -> singleton and pair/corridor interaction estimates
  -> QUBO update
  -> next investment mask
```

The conceptual objective is:

```text
maximize E_s[public_value(π_x, x, s)]
subject to investment_cost(x) <= budget
```

## Why not one continuously trained model?

QUBO is discrete and usually receives a noisy black-box objective from simulation. RL is stochastic,
non-stationary and expensive to retrain. A single end-to-end convergence claim would be difficult to
verify and would make it unclear whether an improvement came from signal control, investment choice,
or scenario sampling.

Alternating optimization is still allowed as future work, but every iteration must record the exact
mask, policy checkpoint, scenarios, seeds, reward profile and public-value assumptions.

## QUBO requirements

The current QUBO scaffold represents candidate value and a budget penalty. It does not yet learn
traffic interaction coefficients. A project-grade QUBO should distinguish:

- `b_i`: benefit of upgrading candidate `i`;
- `b_ij`: synergy or interference between candidates `i` and `j`;
- budget, fairness, coverage and safety penalties;
- scenario robustness or worst-case penalties.

The `b_ij` terms should come from SUMO experiments on connected corridors, not from arbitrary
assumptions. Higher-order effects may require auxiliary variables or a surrogate approximation.

## Recommended research sequence

1. Establish fixed-time, rule-based and shared recurrent RL baselines.
2. Evaluate a designed subset of masks: single candidates, neighboring pairs, corridors and random
   budget-feasible masks.
3. Fit interaction-aware QUBO/surrogate coefficients.
4. Solve the investment problem under budget.
5. Re-evaluate the selected masks across unseen scenarios and seeds.
6. Fine-tune or distill the policy for the selected investment configuration.
7. Stop when the investment decision and public-value ranking are stable under sensitivity tests.

This preserves the distinction between an operational policy and a public-finance investment
recommendation while allowing the two layers to influence one another.
