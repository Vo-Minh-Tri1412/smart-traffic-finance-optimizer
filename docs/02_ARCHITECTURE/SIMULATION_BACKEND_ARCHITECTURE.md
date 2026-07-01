# Simulation backend architecture

This document is the canonical map for the Python simulation package. It explains what the
simulation folders do, where SUMO actually runs, and which pieces are only validation helpers.

## Status

- SUMO is the official traffic simulation backend.
- SUMO-RL is the intended RL environment path.
- The reference backend is validation-only. It is not a simulator for final claims or demos.
- `tests/fixtures/specs/toy_public_district_v1.json` is a synthetic fixture/test project, not the final
  district choice.
- For real maps, the intended direction is OSM/SUMO-first: SUMO `.net.xml` owns road/lane/junction
  geometry, while a semantic overlay owns zones, flows, investment candidates, and finance labels.

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

For OSM-based maps, do not manually redraw the entire road network in Godot. Use SUMO geometry as
the road/lane source of truth and use Godot for rendering, semantic annotation, assets, cameras, and
dataset generation.

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

## Data meanings by model

The word "dataset" means different things in each model layer:

| Layer | Dataset/source | Notes |
|---|---|---|
| RL/control | SUMO/SUMO-RL rollouts | observation, action, reward, next observation, done, metrics, seed, scenario |
| CV/YOLO sensor | Godot-rendered camera frames driven by SUMO traces | image, label, camera config, render preset, frame id |
| Public finance/QUBO | scenario metrics + candidate costs/value assumptions | investment candidates, budget, public-value score, constraints |

Godot is not the RL simulator. Godot is required for synthetic CV if the CV model is meant to learn
from images. SUMO traces are the bridge between traffic dynamics and rendered camera frames.

## Synthetic fixture policy

`tests/fixtures/specs/toy_public_district_v1.json` is a synthetic fixture used to keep tests reproducible.
It is not the final demo district, not a real-world claim, and not a product direction.

Use it for:

- smoke tests;
- SUMO export/run/parse checks;
- replay contract tests;
- baseline/report fixture output.

Do not present it as the final city or district selected by the team.

## Current gaps

Before making strong simulation claims, the project still needs:

- SUMO backend review for exporter/parser correctness;
- stronger route/flow generation;
- clearer traffic-light program design;
- stronger fixed-time/rule-based baselines;
- SUMO-RL training wrapper and reward contract;
- Economics-approved public-value assumptions.
