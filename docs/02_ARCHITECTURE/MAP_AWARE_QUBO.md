# Map-aware public-investment QUBO v1

## Accepted measurement protocol (2026-09-19; not implemented experiments)

[System delivery plan](SYSTEM_DELIVERY_PLAN.md) starts with 8 eligible candidates on the unchanged
full network. Non-upgraded signals retain the same fixed-time baseline. The shared mask-conditioned
RL checkpoint, observation contract, demand, routing assumptions and cost evaluator are frozen
before coefficient measurement. Training a different amount for each mask is not this protocol.

For each scenario/seed measure the empty mask, 8 singleton masks and all 28 pairs: **37 configurations**.
Use the same intended demand in each paired comparison, including adverse outcomes outside each
candidate's own approaches. Candidate selection uses development baseline results, never final test.
If the validated pilot has fewer than 8 candidates, use `1 + n + n*(n-1)/2` and report actual scope.

Planned default seed allocation: RL train 11/23/37; RL validation 53/71; coefficient fit 211/223/237;
surrogate validation 251/263; final test 101/131/167. Hold out day/profile/incident configurations as
well as seeds. Generate and freeze a deterministic list of up to 16 budget-feasible masks with at
least 3 upgrades for surrogate validation; none enters singleton/pair coefficient fitting. Report
when fewer distinct masks are feasible rather than filling the set with duplicates.

Use the same network cost `F` as the RL evaluator, annualized only with explicit calendar weights:

```text
B_i = F(0) - F(i)
I_ij = F(i) + F(j) - F(i,j) - F(0)
```

Every term carries run IDs, hashes, checkpoint, valuation and scenario/seed provenance. Preserve
negative effects and compare predicted versus measured held-out portfolio benefit. Parameter bounds
are not statistical confidence intervals; report paired-run variation separately.

Verify the 8-node pilot by exact solve, compare greedy and a seeded CPU QUBO heuristic, and report
feasibility/energy. Beyond the exact solver's cap, use bounded heuristic runs without optimality or
quantum-advantage claims. Missing unmeasured pair coefficients in larger pilots remain a documented
model limitation, not evidence of zero interaction.

Re-evaluate selected portfolios on final test scenarios after validation and tuning are frozen.
Budget feasibility alone does not imply fairness: apply service/access acceptance checks after
SUMO re-evaluation; do not label a failing or under-evidenced portfolio recommended. If the surrogate
is inaccurate, report that failure and retain directly measured classical comparisons rather than
publishing an unsupported full-map rank. Larger candidate sets follow pilot validation, not exhaustive
RL retraining over all masks.

Capex/opex, price year, calendar and discount/horizon inputs require evidence or explicitly labelled
research assumptions. Their absence does not authorize a hidden default. No actual recommendation,
measured investment effect or trained policy is created by saving this protocol.

## Decision boundary

This QUBO chooses a portfolio of intersections or corridors under a capital budget. It consumes
map-specific, building/zone-to-building/zone OD evidence from `map_economic_profile.v1` and emits a
deterministic `map_aware_qubo_run.v1` decision-support artifact.

It is **not trained RL**, a traffic controller, a quantum advantage claim, or a source of economic
assumptions. SUMO/SUMO-RL measures traffic outcomes; the economic profile converts reviewed
marginal outcomes into values; the QUBO chooses an investment mask.

```text
mapped building/zone OD routes + sourced valuation records
                         + SUMO marginal impact by candidate/mask
                         + reviewed capex/opex and capital envelope
                         -> map-aware QUBO -> candidate portfolio
                         -> unseen-scenario SUMO re-evaluation
```

The QUBO never assigns value merely because a trip is an ambulance, bus, truck, or trip between two
high-value buildings. A route contributes only when the profile supplies a **marginal** delay,
reliability, vehicle-operating-cost, emission, or explicitly aggregated economic-benefit change
caused by the candidate.

## Canonical input join

The loader in `ai_quantum_hvtc.public_finance.map_qubo` accepts a JSON path, a generic mapping, or a
typed model exposing `to_dict()`. It joins:

```text
investment_candidates[].od_impacts[].od_pair_id
    -> od_pairs[].od_pair_id
    -> od_pairs[].valuation_id
    -> valuations[].valuation_id
```

The OD record supplies its actual origin/destination building or zone, route edges and corridors.
The valuation supplies value of time, reliability value and persons per trip. Candidate records
supply junction/edge/corridor footprint, evidence-bearing capital and operating cost, and explicit
OD impacts. `coverage` passes through unchanged to the run manifest; low map/economic coverage does
not become high confidence merely because a solver returned a minimum.

Every `ValueRecord` contains:

- `estimate`, `lower`, `upper`;
- a strict `unit` and monetary `price_year` where applicable;
- `evidence_grade`, `source_ids`, and `is_assumption`.

The QUBO adapter rejects non-assumption records with no source IDs. It does not infer a yearly trip
count from a daily count, assume 365 operating days, select a universal discount rate, or monetize
gross economic flow.

## Candidate benefit

For candidate `i` and mapped OD pair `r`, the adapter accepts one of three mutually exclusive
evidence paths for delay:

1. explicit `annual_economic_benefit_vnd` for the marginal intervention effect;
2. `annual_person_delay_saved_hours` multiplied by the OD value of time;
3. `delay_reduction_seconds_per_trip * annual_trips * persons_per_trip / 3600`, multiplied by the OD
   value of time.

Reliability has separate saved-hour/per-trip fields and a separate rate. An optional
`route_exposure_fraction` in `[0, 1]` scales the marginal impact. If it is absent, the adapter only
uses a benefit already explicitly attached to that OD pair and records the exposure basis as
`explicit_od_impact`; it does not invent a numeric overlap benefit from a building label.

All marginal effects may be signed: a negative saving represents harm, such as delay displaced
onto a neighboring route. Aggregate monetary benefit cannot coexist with decomposed delay or
reliability effects. Annual saved hours and per-trip seconds for the same channel cannot coexist;
ambiguous inputs are rejected instead of counted twice or silently ignored.

Vehicle operating cost and emission savings are legitimate public-finance channels, but v1 does
not synthesize them from gross traffic. Until the profile gains reviewed decomposed records, the
producer may include them in `annual_economic_benefit_vnd` with its calculation and sources. The
same saving must not also appear in a delay-derived field.

The loader resolves rates through `valuation_id`. Consequently two trips sharing a road can carry
different reviewed marginal value because their origin/destination buildings or zones resolve to
different valuation records. Essential-service and economic-flow multipliers are retained by the
data layer but are not silently multiplied into QUBO value; Economics must first define a
non-double-counting marginal valuation rule.

## Interactions

The optional `candidate_interactions` block represents measured pair effects:

- `complementarity`: non-negative extra benefit when both upgrades work as a corridor;
- `overlap`: non-positive benefit preventing double-counting of the same saved delay;
- `bottleneck`: signed effect for a jointly relieved or displaced bottleneck.

Each pair requires an evidence-bearing signed annual marginal value. Missing pairs are zero, not an
estimated synergy. The canonical profile producer currently need not generate this optional block;
pair coefficients should be added after SUMO evaluations of single candidates, neighboring pairs,
corridors, and held-out masks. An arbitrary distance-based coefficient is not acceptable evidence.

## Objective and units

Let:

- `x_i` be the binary investment decision;
- `B_i` be annual marginal OD benefit in the profile price-year currency;
- `C_i` be capital cost and `O_i` annual operating cost;
- `I_ij` be the signed annual marginal interaction benefit;
- `p_b` and `p_o` be explicit present-value factors for benefits and operating costs;
- `alpha` be the explicit capital-cost weight;
- `S` be `objective_scale_vnd`.

The non-budget energy is:

```text
E0(x) = sum_i ((alpha*C_i + p_o*O_i - p_b*B_i) / S) * x_i
        - sum_(i,j) (p_b*I_ij / S) * x_i*x_j
```

`p_b` and `p_o` are required inputs. The module does not bake in a historical 8%, 10%, or 12%
discount rate. Economics should produce named horizon/discount-rate sensitivity cases and retain the
profile `price_year`. The example factor `1.0` is only a one-year undiscounted plumbing case.

Authoritative HCMC appraisal examples decompose benefits into travel-time, vehicle operating cost,
and emissions rather than treating all trip value as an intervention benefit: the
[JICA HCMC Urban Railway Line 3A report](https://openjicareport.jica.go.jp/pdf/12305124_03.pdf) and
[World Bank HCMC Green Transport appraisal](https://documents1.worldbank.org/curated/en/558961468179946764/pdf/PAD1305-PAD-P126507-IDA-R2015-0120-1-Box391444B-OUO-9.pdf)
are starting references for the Economics team, not hard-coded coefficients.

## Capital-budget encoding and penalty proof

`budget_unit_vnd = U` turns capital costs into conservative integer units:

```text
c_i = ceil(C_i / U)
b   = floor(capital_budget / U)
```

Binary slack variables exactly represent unused units from `0` through `b`. The complete QUBO is:

```text
E(x, s) = E0(x) + lambda * (sum_i c_i*x_i + sum_k w_k*s_k - b)^2
```

This is a true upper-budget constraint: feasible portfolios can set slack for zero penalty, while
an overspending portfolio differs by at least one integer unit. It does not incorrectly force the
portfolio to spend the entire budget.

Define the maximum favorable non-budget reduction bound:

```text
M = sum_i max(-linear_i, 0) + sum_(i,j) max(-quadratic_ij, 0)
```

The adapter requires `lambda > M`. If the caller supplies a smaller penalty it raises an error. If
the caller leaves it null, the adapter selects `max(1, penalty_margin*M + epsilon)` and records both
the selected penalty and `minimum_safe_budget_penalty` in the manifest. This bound is conservative;
it protects feasibility, but coefficient scaling and hardware embedding remain solver-specific QA.

## Uncertainty modes

- `estimate`: use every central estimate;
- `conservative`: lower benefits/exposure/interactions and upper costs;
- `optimistic`: upper benefits/exposure/interactions and lower costs.

For signed effects, interval products evaluate all endpoint combinations. A negative delay saving
combined with a higher positive value of time or exposure is more adverse, so simply multiplying
all lower endpoints would be incorrect. Multiple channel bounds are summed conservatively; they
are not a probabilistic confidence interval or a claim about correlation. `route_exposure_fraction`
in the contribution is the marginal exposure endpoint; inspect `input_values` for the full range
used in each signed product. Run and compare all three modes before making a ranking claim.

Budget rounding uses decimal representations of input values without epsilon offsets. The
discrete budget is conservative and can exclude a portfolio that fits in exact VND; select and
report the unit deliberately. The evaluator accepts only integer/bool binary assignments and
rejects fractional or string values before conversion.

## CLI

The CLI has no quantum or YAML-library dependency. Its optional YAML reader intentionally accepts
only top-level scalar fields from the checked-in template.

```powershell
uv run python scripts/finance/solve_map_qubo.py `
  --config configs/finance/map_qubo_district7.example.yaml `
  --profile data/processed/map_economics/DISTRICT7/map_economic_profile.v1.json `
  --budget-vnd <REVIEWED_CAPITAL_BUDGET_VND> `
  --benefit-present-value-factor <REVIEWED_FACTOR> `
  --operating-cost-present-value-factor <REVIEWED_FACTOR> `
  --output artifacts/runs/public_finance/DISTRICT7-QUBO-001/map_qubo_manifest.json
```

Command-line values override the config. The result contains the input hash, price year, coverage,
full coefficient provenance, linear biases, pair biases, upper-triangular Q matrix, constant,
budget encoding, exact solution and policy-claim caveat.

## Solver boundary and verification

`solve_map_qubo_exact` enumerates candidate subsets deterministically and fills optimal slack bits
analytically. Its default cap is 22 candidates. It is a small-instance reference solver for tests,
penalty validation, and cross-checking a production solver—not a proposed way to enumerate the full
District 7 candidate set.

Before a full-map recommendation:

1. freeze the map/profile/route and scenario hashes;
2. reject a profile whose coverage production gate fails;
3. measure singleton and designed pair/mask impacts across SUMO seeds;
4. run estimate/conservative/optimistic and budget/horizon sensitivities;
5. solve with a reviewed classical, hybrid, or QUBO backend;
6. compare the backend energy with this deterministic evaluator;
7. re-run selected and neighboring portfolios on unseen SUMO scenarios;
8. report instability, assumptions and uncovered OD demand alongside the rank.

The output is public-investment decision support. It must not be described as a trained RL policy,
verified economic benefit, or quantum superiority result without the corresponding evidence.
