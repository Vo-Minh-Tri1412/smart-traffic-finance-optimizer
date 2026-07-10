# Simulation backend architecture

This document is the canonical map for the Python simulation package. It explains what the
simulation folders do, where SUMO actually runs, and which pieces are only validation helpers.

## Status

- SUMO is the official traffic simulation backend.
- SUMO-RL is the intended RL environment path.
- The reference backend is validation-only. It is not a simulator for final claims or demos.
- `tests/fixtures/specs/toy_public_district_v1.json` is a synthetic fixture/test project, not the final
  district choice.
- The current direction is OSM/SUMO-first for the full Quận 7 map or a reviewed ROI of roughly 100
  signalized intersections: SUMO `.net.xml` owns road/lane/junction geometry, while a semantic
  overlay owns zones, flows, investment candidates, camera anchors and finance labels.

## Main flow

```text
district_spec.json or OSM/SUMO map source
  -> specs/domain validation or OSM/SUMO intake profile
  -> routing and route-policy checks / external SUMO route generation
  -> SUMO XML export or existing SUMO .net.xml
  -> SUMO/netconvert runtime
  -> tripinfo / edge_data / fcd outputs
  -> SimulationResult metrics
  -> simulation_trace.jsonl
  -> Godot replay / React dashboard / public-finance scoring
```

Python does not replace SUMO. Python prepares or accepts SUMO inputs, calls SUMO, parses SUMO
outputs, and normalizes results for the rest of the project.

For render integration, Python is the producer of bridge artifacts. It should normalize SUMO outputs
into versioned contracts such as vehicle traces, traffic-light traces, event traces, semantic
overlays, and render run manifests. Renderers consume those contracts; they should not call into
private Python internals.

For OSM-based maps, do not manually redraw the entire road network in Godot. Use SUMO geometry as
the road/lane source of truth and use Godot for rendering, semantic annotation, assets, cameras, and
dataset generation.

## Quận 7 OSM/SUMO-first path

Large real maps use a different source shape from the toy `district_spec` fixture:

```text
district7.project.json
  -> SUMO .net.xml source
  -> semantic_overlay.v1
  -> synthetic demand/routes
  -> SUMO run-sumo-net
  -> FCD trace
  -> Godot replay from the same .net.xml
```

The committed project descriptor and overlay are small metadata files. The actual OSM/SUMO artifacts
stay in DVC/Drive. The semantic overlay is intentionally separate from geometry: zones, public-value
tags, demand anchors, and candidate traffic lights reference SUMO IDs instead of copying every road
into JSON.

Use `simulate validate-sumo-net` to check a descriptor or `.net.xml`, and `simulate run-sumo-net` to
run an existing net with a route file.

## Package map

```text
ai_quantum_hvtc/simulation/
├── domain/       # typed objects for district specs
├── specs/        # load and validate district_spec JSON
├── routing/      # route policies and route constraints
├── controllers/  # controller identities/contracts
├── engines/      # execution backends
│   ├── sumo/     # official SUMO adapter/export/run/parse path
│   └── reference/# lightweight validation backend/test double only
├── metrics/      # SimulationResult and normalized metrics
├── traces/       # replay/dashboard trace contract
└── cli.py        # simulate validate/run/compare command entrypoint
```

## What each layer owns

### `domain/`

Defines the Python representation of the district spec:

- zones;
- intersections;
- roads;
- vehicle types;
- OD flows;
- scenarios;
- controllers;
- investment candidates;
- finance assumptions.

This layer does not run traffic. It is the typed vocabulary that lets the rest of the package reason
about the spec safely.

### `specs/`

Loads and validates `district_spec.json`.

It should fail early when:

- a road points to an unknown intersection;
- a flow references an unknown zone;
- a vehicle mix references an unknown vehicle type;
- an investment candidate points to a missing intersection;
- truck restrictions or route policies cannot be checked.

### `routing/`

Builds route choices for flows before SUMO receives routes.

Examples:

- shortest-time route;
- congestion-aware placeholder route;
- truck-legal route;
- priority-fastest route for emergency vehicles.

Routing is a helper for SUMO export and metrics attribution. It is not a traffic simulator.

### `controllers/`

Owns controller identities and contracts such as:

- `fixed_time`;
- `rule_based`;
- `rl_policy`.

The actual SUMO execution for these controllers belongs under `engines/sumo/`. For example, a
rule-based controller may be implemented through SUMO/TraCI behavior while still sharing the common
controller id.

### `engines/sumo/`

This is the official backend path.

```text
exporter.py  -> writes SUMO nodes/edges/routes/additional/config files
runner.py    -> calls SUMO/netconvert and handles runtime checks
parser.py    -> parses tripinfo, edge data, controller logs, and FCD trace
adapter.py   -> wraps export/run/parse into one SimulationEngine implementation
config.py    -> SUMO runtime configuration
errors.py    -> clear SUMO runtime errors
```

SUMO owns the traffic dynamics: movement, queues, departures, arrivals, FCD positions, and network
simulation. The Python adapter is deliberately small because it is a bridge to SUMO, not a custom
traffic engine.

### `engines/reference/`

The reference backend is a lightweight validation/test double.

It may be used for:

- CI tests that should not depend on external SUMO binaries;
- fast smoke checks of specs, metrics, and finance code;
- deterministic toy validation.

It must not be used for:

- final demo claims;
- traffic realism claims;
- RL training claims;
- public-finance conclusions.

If docs mention the reference backend, they should call it validation-only.

### `metrics/`

Normalizes backend output into `SimulationResult`.

Important metrics include:

- total and average waiting time;
- queue proxies;
- throughput;
- stopped vehicles;
- emergency delay;
- bus passenger delay;
- truck/logistics delay;
- per-intersection metrics;
- controller intervention counts.

### `traces/`

Exports versioned trace frames for replay/dashboard consumers.

Current trace schema:

```text
simulation_trace_frame.v1
```

Vehicle-level trace frames are produced from SUMO FCD output and consumed by Godot replay. Aggregate
frames are allowed for dashboard or validation backend views, but not for full vehicle replay.

Render bridge work should use the names in `RENDER_BRIDGE_SCHEMA_VERSIONS`:

```text
geometry_manifest.v1
vehicle_trace.v2
traffic_light_trace.v1
semantic_overlay.v2
event_trace.v1
render_run_manifest.v1
sensor_dataset_manifest.v1
```

## Data meanings by model

The word "dataset" means different things in each model layer:

| Layer | Dataset/source | Notes |
|---|---|---|
| RL/control | SUMO/SUMO-RL rollouts | observation, action, reward, next observation, done, metrics, seed, scenario |
| CV/YOLO sensor | Godot-rendered camera frames driven by SUMO traces | image, label, camera config, render preset, frame id |
| Public finance/QUBO | scenario metrics + candidate costs/value assumptions | investment candidates, budget, public-value score, constraints |

Godot is not the RL simulator. A learned CV model is optional for the first RL experiment: a
geometry-based optical visibility adapter can produce partial observations from SUMO traces before
YOLO exists. SUMO traces remain the bridge between traffic dynamics and rendered camera frames.

## Synthetic fixture policy

`tests/fixtures/specs/toy_public_district_v1.json` is a synthetic fixture used to keep tests reproducible.
It is not the final demo district, not a real-world claim, and not a product direction.

Use it only for:

- smoke tests;
- SUMO export/run/parse checks;
- replay contract tests;
- baseline/report fixture output;
- dependency and adapter smoke checks before the large ROI.

Do not present it as the final city or district selected by the team.

## Current gaps

Before making strong simulation claims on Quận 7 or a large ROI, the project still needs:

- SUMO backend review for exporter/parser correctness;
- stronger route/flow generation;
- clearer traffic-light program design;
- stronger fixed-time/rule-based baselines;
- SUMO-RL multi-agent training wrapper and approved reward contract;
- optical visibility/sensor observation adapter and vehicle height/elevation fields;
- structured occlusion and temporal-memory evaluation;
- large-ROI performance validation with shared policy parameters;
- interaction-aware QUBO coefficients estimated from SUMO experiments;
- Economics-approved public-value assumptions.
