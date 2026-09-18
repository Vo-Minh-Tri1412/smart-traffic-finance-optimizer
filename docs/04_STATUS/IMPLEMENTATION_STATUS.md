# Implementation Status

This is the repository-level status record. It summarizes verified capability and important gaps;
individual task evidence remains in `coordination/tasks/` and generated run artifacts remain outside
Git.

## Confirmed foundations

- SUMO is the traffic simulator and the bridge/replay path consumes prepared net and trace artifacts.
- The Godot project has scene-native road, vehicle, zone, traffic-light and camera scaffolding.
- The training scaffold supports shared multi-agent mode, a frame-stack baseline and optional
  RecurrentPPO mode. This is scaffolding, not a validated Quận 7 policy claim.
- Synthetic dataset layout, camera and label catalogs, a sensor dataset writer and smoke export path
  exist.
- Canonical vehicle height/ground-clearance profiles, `vehicle_geometry_catalog.v1`, and a SUMO
  `geometry_sensor` profile now exist. The profile uses a 0.2-second simulation step, one-second FCD
  capture and 0.4m Sublane resolution without changing demand, reward or economics.
- A deterministic Python geometry camera consumes `vehicle_trace.v2`, camera calibration and vehicle
  cuboids to emit `visibility_trace.v1` plus compact geometry-visibility observations. Golden tests
  cover bus/truck-style occlusion, tie ordering, frustum bounds and legacy-trace rejection.

## Not yet a production claim

- Reward profile, demand/flow calibration, scenario set and evaluation economics remain subject to
  project-owner approval.
- Full-ROI multi-agent training, baseline comparison and cloud-scale validation are unfinished.
- The current sensor smoke path is not a calibrated depth/instance visibility pass. It must not be
  used as proof of physical occlusion or a final YOLO dataset.
- Road elevation is explicitly propagated when present; the current District 7 flat-map fallback is
  labelled `flat_assumption`. Bridges/ramps still need elevation-calibrated map data before physical
  elevation claims.
- Godot imports the shared camera calibration and receives hidden physical vehicle proxies, but it
  does not yet perform a depth/instance visibility pass.
- No trained RL policy, trained YOLO detector or final public-finance result should be claimed.

## Unreal and map-economic implementation (2026-09-16)

The active renderer migration is implemented as a UE 5.8 C++ project in `render_unreal/`, with
manifest/trace loaders, coordinate conversion, replay proxies, lane geometry, camera calibration,
and editor automation scaffolding. Godot remains the legacy parity reference. On 2026-09-17 native
UE compilation succeeded after NetFxSDK became available; four native automation tests passed.
The unchanged real SUMO net built 88,163 lanes in a geometry-only test using a clearly labelled
synthetic two-frame trace, not observed demand. MCP initialize and tool discovery succeeded at
127.0.0.1:8001 during that test session; the editor then exited normally. These checks do not
establish rendered-image parity. On 2026-09-18, `vswhere` confirmed both .NET 4.8 SDK and Targeting
Pack components, and the v4.8 reference assemblies are present. Depth/instance
capture, traffic-light and semantic visual layers, and bounded ROI streaming remain incomplete.
See [Unreal migration](../02_ARCHITECTURE/UNREAL_RENDER_MIGRATION_PLAN.md).

`map_economic_profile.v1` now links prepared map entities, SUMO edges, zones, corridors, OD pairs and
economic evidence. The materializer preserves the current map and distinguishes derived nearest-edge
coverage from sourced economic calibration. The supplied numeric configuration is an assumption
register; reviewed OD demand and measured investment effects are still missing. See
[map-economic model](../02_ARCHITECTURE/MAP_ECONOMIC_DATA_MODEL.md).

The existing ROI is explicitly user-approved, not an administratively verified district. The
2026-09-17 baseline sets both service/flow multipliers to 1 to avoid unsourced RL-only premiums.
[Objective rationale](../02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md) distinguishes the implemented
local reward from the proposed complete network-cost evaluator and QUBO marginal-benefit protocol.

[Demand dataset design](../02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md) preserves the original
purpose/time priors and separates II/IE/EI/EE boundary trips. The runnable inventory groups 2,588
geometry entities into 340 candidate source parents (252 multi-piece), without inventing facility
capacity, gates or OD counts. A downloaded, hashed WorldPop 2020 population grid supplies a historical
spatial prior only. This is not yet a calibrated SUMO trip dataset. Economic and travel source
registries retain table/year/unit, reuse and transfer limitations; source discovery has not increased
the profile's 0% source-backed calibration coverage.

The opt-in SUMO-RL economic callback uses incremental time loss and the profile's OD valuation and
occupancy. It exposes sampled local cost independently of learning normalization. These samples omit
first sightings and vehicles leaving between observations and are not a complete network-cost
estimate. Training checks map identity and economic coverage in addition to existing safety gates.
The existing-net map needs explicit training OD/spec integration before a full-map run.

The map-aware QUBO consumes explicit marginal OD impacts and pair interactions, produces an
evidence-bearing matrix/manifest, and includes a deterministic small-instance exact solver. It
supports signed adverse effects and conservative uncertainty cases. No calibrated full-map investment
ranking is claimed. See [map-aware QUBO](../02_ARCHITECTURE/MAP_AWARE_QUBO.md) and tasks 082–085.

## Active dependency order

```text
map and physical render alignment
  -> camera calibration + vehicle dimensions
  -> geometry visibility and sensor observation adapter
  -> approved reward/flow scenarios
  -> RL baselines and partial-observation evaluation
  -> YOLO calibration and robust detector-noise experiments
```

Sensor geometry work may advance before reward/flow approval. RL performance claims may not.

## Status update rule

Update this file when a repository-wide capability becomes verified, superseded or blocked. Do not
copy individual task narratives here. Link a task manifest, test report or artifact manifest when a
status statement needs evidence.
