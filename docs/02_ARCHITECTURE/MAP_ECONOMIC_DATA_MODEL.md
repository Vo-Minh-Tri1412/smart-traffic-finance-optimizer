# Map Economic Data Model v1

M0 TASK-095, 2026-09-20: project loader đã đọc/validate roi_semantic_overlay.v2 và giữ provenance.
Inventory/materializer vẫn đọc polygon theo đường riêng; inventory hợp lệ không chứng minh run được.
Descriptor thật có 2.588 polygon chưa có anchor và không có demand_flows; generator dừng rõ ràng.
Parent grouping và nearest-edge chỉ là ứng viên, chưa là cổng/capacity đã xác minh.

## Map preparation: công cụ, không phải kế hoạch đổi map

scripts/maps/prepare_roi.py hỗ trợ polygon ROI, zoning tags, neutral fill và road-review flags;
--clip-sumo-net có thể tạo net khác. Không dùng để cắt lại map giữ nguyên trong pilot.
POI point buffers là xấp xỉ vị trí, không phải footprint, capacity hoặc entrance thật.
Neutral demand_enabled=false; không sinh demand từ vùng thiếu nhãn.
Road flags phải review, không tự xoá đường. Taxonomy/IDs theo dữ liệu đã version, không tạo
micro-zone rồi nhân population/job totals lên mọi mảnh.

Dry-run utility: `uv run python scripts/maps/prepare_roi.py --config simulation_projects/map_intake/templates/roi_config.template.json --output-root artifacts/tmp/roi_template_smoke --dry-run`.
Outputs: semantic_overlay.generated.json, road_review.generated.json, render_preview.generated.json,
qa_report.json/md; net mới chỉ khi yêu cầu clipping. Không coi schemas utility là loader-compatible.

## Accepted extension, not a calibration update (2026-09-19)

[System delivery plan](SYSTEM_DELIVERY_PLAN.md) permits explicitly labelled synthetic research
while source collection continues. It does not approve existing numeric placeholders, change
profile status, raise calibration coverage or relax the production gate.

The planned demand dataset supplies explicit trip/OD/purpose/time/occupancy joins; the network
ledger and QUBO must share the same versioned valuations. Remove the existing-net parser's fixed
20-person bus assumption in a later implementation task. Do not count both occupancy-weighted
vehicle time and the same passenger records. Keep physical vehicle labels separate from economic
purpose: a camera cannot establish a trip's destination, commodity value or work purpose by class.

The full-network evaluator and shared RL objective will follow the accepted extension in
[objective rationale](RL_QUBO_OBJECTIVE_RATIONALE.md); the incremental API described below remains
the current implementation. Reliability/cargo/emissions/deadline channels remain disabled until
their definitions, evidence and non-double-counting rules are supplied. Disabled means unmodelled,
not a measured zero impact. Baseline service/flow multipliers remain 1.

Annualization requires an explicit representative calendar and scenario weights; present-value
factors, capex and opex require provenance or declared research assumptions. No default 365-day
conversion or current-price claim may be inferred from a short simulation or historical source.

## Decision

`map_economic_profile.v1` is the renderer-independent, SUMO-compatible contract that connects
prepared map entities and routes to public-value calculations. It supports building/zone/corridor
and OD-specific values without pretending that a vehicle class alone explains economic benefit.

The current artifact is deliberately **draft-only**. The prepared overlay contains 2,588 polygons,
but those polygons are not all confirmed physical buildings. Its approximate bounding box also
contains names that may fall outside District 7. Consequently, the code calls them prepared-map
entities, preserves `entity_kind` and source tags, and blocks District 7-specific production claims
until the boundary and economic calibration are reviewed. On 2026-09-16 the user explicitly
confirmed keeping the existing prepared ROI unchanged. The example now records `reviewed_roi`,
not `verified_district`: no geometry, entities or geographic extent are changed. This resolves the
scope choice only; economic assumptions remain draft and reviewed OD remains unavailable.

The 2026-09-17 example baseline sets every essential-service and economic-flow multiplier to
exactly 1.0. These are neutral modelling choices, not calibrated evidence. This avoids giving RL
unsupported building-tag premiums that the QUBO adapter does not apply. Distinct OD value-of-time,
occupancy and measured marginal time loss may still differentiate trips after calibration.

## Authority boundaries

```text
SUMO net + semantic overlay       reviewed economic sources / assumptions
              \                     /
               map_economic_profile.v1
                    |             \
      incremental delay reward    QUBO candidate/OD input
                    |
          raw VND ledger + scaled PPO reward
```

- SUMO remains authoritative for routes, traffic states, delay and time loss.
- The profile supplies economic interpretation and provenance; it does not alter SUMO geometry.
- The raw monetary ledger is separate from RL normalization and clipping.
- QUBO may consume `profile.to_dict()` and join on `candidate_id` plus `od_pair_id`.
- Unreal render state is not an economic source of truth.

## Profile structure

The committed template is
`data/catalog/map_economic_profile.v1.template.json`. The main sections are:

| Section | Grain | Purpose |
|---|---|---|
| `metadata` | profile | Currency, price year, map hashes, scope status and caveats |
| `sources` | evidence source | Title, publisher, URI, date, geographic scope and notes |
| `valuations` | reusable value bundle | VOT, reliability, occupancy and policy multipliers |
| `buildings` | prepared-map entity | Entity kind, zone, nearest/exact SUMO edges and optional valuation |
| `zones` | semantic group | Member entities, mapped edges and zone-level valuation |
| `edges` | SUMO edge | Entity, zone and corridor reverse mappings |
| `corridors` | reviewed edge group | Route-level valuation and semantic grouping |
| `od_pairs` | directed origin-destination pair | Building/zone endpoints, route exposure and OD valuation |
| `investment_candidates` | intervention | Capex/Opex, footprint, OD impacts and annualization evidence |
| `reward_policy` | profile | Explicit VND normalization and clipping policy |
| `coverage_policy` | profile | Structural, calibration and demand-weighted production gates |

### Numeric evidence record

Every economic number is a `ValueRecord`:

```json
{
  "estimate": 50000,
  "lower": 30000,
  "upper": 80000,
  "unit": "VND/person_hour",
  "price_year": 2025,
  "evidence_grade": "D",
  "source_ids": ["ASSUMPTION_REGISTER_V1"],
  "is_assumption": true,
  "notes": "Placeholder prior; not a measured District 7 value."
}
```

Monetary units are `VND` or `VND/person_hour`; `price_year` is a separate mandatory field and must
match profile metadata. This avoids silently mixing old and current prices. Other accepted units are
`persons/trip`, `ratio`, `seconds/trip`, `trips/year`, `hours/year`, and
`person_hours/year`.

Evidence grades are:

- `A`: authoritative and directly applicable source;
- `B`: authoritative but requiring limited transfer or transformation;
- `C`: derived or secondary evidence;
- `D`: explicit modelling/expert assumption;
- `U`: unresolved.

An assumption must use `D` or `U`. A candidate source listed in the registry does not make a number
source-backed; the `ValueRecord` must cite a reviewed source and set `is_assumption=false`.

## Route/building-aware resolution

`resolve_trip_valuation()` uses this deterministic order:

1. explicit `od_pair_id` or the most specific matching OD selectors;
2. destination building, then origin building;
3. destination zone, then origin zone;
4. the corridor with the greatest route-edge overlap;
5. the profile's global fallback.

The result includes `resolution_level`, `matched_id`, `valuation_id`, matched corridors, evidence
grades, source IDs and whether assumptions remain. An OD such as residential building A to a
hospital entity can therefore use a different valuation from A to a market, even when both trips use
the same vehicle type. Vehicle class may still provide observed occupancy, but it is not the primary
economic key.

A declared `route_edge_ids` selector matches the complete ordered route, including direction.
Sharing a single edge is insufficient; partial-route exposure belongs in `corridor_ids`.
An explicitly supplied `od_pair_id` is authoritative and bypasses selector inference.

## Incremental reward formula

The API is:

```python
profile = load_map_economic_profile(path)
reward = build_map_economic_reward(profile)
result = reward.evaluate_trip_delay_delta(
    delay_delta_seconds=delta_time_loss,
    reliability_delta_seconds=measured_schedule_variability_delta,
    context=TripEconomicContext(
        od_pair_id=flow_id,
        origin_building_id=origin_id,
        destination_building_id=destination_id,
        route_edge_ids=tuple(route_edges),
    ),
)
```

For valuation `v`, the central monetary cost is:

```text
raw_public_cost_vnd
  = delay_delta_seconds / 3600
  * persons_per_trip
  * value_of_time_vnd_per_person_hour
  * essential_service_multiplier
  * economic_flow_multiplier

  + reliability_delta_seconds / 3600
  * persons_per_trip
  * reliability_value_vnd_per_person_hour
  * essential_service_multiplier
  * economic_flow_multiplier
```

The lower and upper bounds use the corresponding parameter bounds. A positive delay delta is a
cost; a negative delta is a saving. The PPO value is calculated separately:

```text
normalized_unclipped = -raw_public_cost_vnd / normalization_vnd_per_step
reward = clip(normalized_unclipped, clip_min, clip_max)
```

Only an incremental delay/time-loss delta may enter this formula. SUMO's accumulated waiting time
or `getTimeLoss()` must be cached by vehicle and differenced between decisions. Feeding cumulative
values at every step double-counts prior cost and destroys the VND interpretation.
Reliability value is applied only when the caller supplies a measured schedule-variability delta;
it defaults to zero and is never added as an automatic premium on ordinary time loss.

## Candidate annualization for QUBO

Each candidate has `capital_cost_vnd`, `annual_operating_cost_vnd`, junction/edge/corridor footprint,
and optional `od_impacts`. An OD impact may provide:

- `annual_economic_benefit_vnd`; or
- `annual_person_delay_saved_hours`; or
- `delay_reduction_seconds_per_trip` together with **both** `annual_trips` and
  `persons_per_trip`.

The validator rejects implicit `365 days/year` or any other hidden annualization.
Marginal savings may be negative when an intervention worsens outcomes. Each impact selects exactly
one of the three benefit representations above; overlapping annual and per-trip totals are rejected.
Optional `route_exposure_fraction` is constrained to `[0, 1]`. `derivation_method` distinguishes
`explicit_od_impact` from `derived_route_overlap`. Interaction/synergy coefficients remain a QUBO
experiment artifact and must come from SUMO evaluations rather than this economic profile.

## Coverage and claim gates

Coverage has three separate denominators:

1. **Structural edge mapping**: share of demand-eligible prepared entities linked to a SUMO edge.
   `exact_anchor` and `derived_nearest_edge` are counted separately.
2. **Economic calibration**: share resolved above global fallback, and share whose complete
   valuation is source-backed.
3. **Demand-weighted coverage**: same economic coverage weighted by reviewed OD volumes.

Demand-weighted status is one of:

- `available_reviewed`: positive reviewed OD weights are present;
- `assumption_only`: weights exist but at least one is an assumption;
- `unavailable`: there is no positive OD denominator.

Assumption-only demand cannot satisfy the production gate. An explicit empty demand mapping also
remains unavailable; it never falls back silently to example weights.
Unknown OD IDs in externally supplied observed demand remain in the denominator and contribute
zero covered demand. NaN, infinity, and negative demand weights are rejected. Grade D/U records
must remain explicitly marked as assumptions and cannot count as source-backed calibration.

`assert_production_ready(profile)` checks all configured thresholds plus:

- profile status must be `approved`;
- map scope cannot be `unverified_boundary`;
- reviewed demand coverage must exist when required.

### Current prepared-map audit (rerun 2026-09-16)

The materializer was run against `district7_osm_seed_20260702` and the current semantic overlay:

| Check | Current result |
|---|---:|
| Prepared-map entities | 2,588 |
| Demand-eligible entities | 1,354 |
| Background/neutral entities | 1,234 |
| Exact edge anchors | 0 |
| Derived nearest-edge mappings | 1,354 |
| Structural mapping | 100% derived |
| Non-global valuation resolution | 100% zone fallback |
| Source-backed calibration | 0% |
| Reviewed OD demand coverage | unavailable |
| Production gate | failed as intended |

The nearest-edge distance across all 2,588 prepared polygons ranged from approximately `0.009 m`
to `199.91 m` (median `16.83 m`) in the current artifact. These are structural geometry diagnostics,
not evidence of economic accuracy.

## Materialization

Run:

```powershell
uv run python scripts/data/prepare_map_economic_profile.py `
  --project simulation_projects/map_intake/district7.project.json `
  --assumptions configs/economics/district7_map_economic_assumptions.v1.example.json `
  --output <artifact-dir>/map_economic_profile.v1.json `
  --coverage-output <artifact-dir>/map_economic_coverage.v1.json
```

Add `--fail-on-production-gate` in a production pipeline. The materializer:

- hashes the SUMO net and semantic overlay;
- preserves all prepared-map entities and source tags;
- uses valid existing anchors as `exact_anchor`;
- otherwise maps centroids to the nearest SUMO edge as `derived_nearest_edge`;
- creates reverse edge/zone/entity mappings;
- imports only explicitly configured corridors, OD pairs and candidates;
- embeds and exports a deterministic coverage report.

It does not invent OD demand, corridors, candidate costs or intervention effects.

## Evidence backlog

The example source registry lists authoritative candidates, but does not attribute any numeric value
to them before table-level review:

- Ho Chi Minh City Statistical Yearbook 2024 and GSO statistical datasets for official local
  socioeconomic denominators;
- JICA's HCMC Line 3A appraisal for transport cost-benefit methodology;
- the World Bank HCMC Green Transport appraisal for travel-time, vehicle-operating-cost and
  environmental benefit structure.

The World Bank appraisal is from 2015 and explicitly reports its contemporary exchange rate and
VOT/VOC framework. It is method evidence, not a current District 7 price table. Any old monetary
value needs an explicit escalation index, formula, target price year, geographic transfer rationale,
and uncertainty range.

## Required next data work

Before map-specific policy claims:

1. preserve the user-approved existing ROI; validate an administrative boundary only if making district-specific claims;
2. verify which polygons represent buildings, campuses, land use, or split geometry;
3. review building-to-edge anchors and define named corridors;
4. create measured or reviewed synthetic OD volumes with route IDs and time windows;
5. calibrate VOT, occupancy, reliability and freight/service values by source and price year;
6. define investment candidates and measure their singleton/pair effects in SUMO;
7. approve sensitivity ranges and run the production gate.

Until then, the profile is valid for pipeline development and sensitivity experiments only.
