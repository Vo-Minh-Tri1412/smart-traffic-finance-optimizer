# Godot render architecture

This document is the canonical architecture note for the `render/` Godot project. The local
`render/README.md` is intentionally short and should only point here plus list quick commands.

## Role

Godot is the visual authoring, replay, and synthetic sensor-render layer.

It is not the traffic simulator. SUMO/SUMO-RL remains responsible for traffic dynamics, route
movement, queues, traffic-light policies, RL training, and metrics.

## Current flow

```text
Godot authored map scene
  -> district_spec.generated.json
  -> Python/SUMO validate and run
  -> district.net.xml + simulation_trace.jsonl
  -> Godot renders SUMO geometry and replays vehicle traces
  -> future cameras export frames/labels/video
```

Godot should prefer SUMO `district.net.xml` for road/lane geometry during replay so vehicles and
roads share the same coordinate source.

## Project map

```text
render/
├── scenes/
│   ├── main/        # app entry scene
│   ├── authoring/   # drag-and-drop map markers
│   │   └── presets/ # reusable zone/intersection presets for no-code editing
│   ├── world/       # replay world and future world objects
│   ├── vehicles/    # editable vehicle scenes
│   ├── sensors/     # future camera/sensor scenes
│   └── ui/          # future replay/demo UI
├── scripts/
│   ├── assets/      # VehicleAssetRegistry, VehicleFactory, VehiclePool
│   ├── authoring/   # Godot scene -> district_spec export
│   ├── contracts/   # schema/version constants
│   ├── replay/      # trace loading, clock, interpolation, replay controller
│   ├── world/       # SUMO net geometry parsing/rendering
│   └── dataset_export/
├── resources/
│   └── configs/     # manifest examples and future render/camera presets
├── imported_assets/ # local imported art assets
└── outputs/         # ignored local render outputs
```

## Authoring layer

The authoring scene is:

```text
res://scenes/authoring/DistrictAuthoringMap.tscn
```

Authoring markers are component-style scene nodes:

- `IntersectionMarker`;
- `RoadSegment`;
- `ZoneArea`;
- `DemandFlow` (`SpawnPoint` remains only as a compatibility alias);
- `DestinationPoint`;
- `TrafficLightMarker`;
- `InvestmentCandidateMarker`.

Each marker owns its exported properties and serializes itself. The exporter should not become a
large list of marker-specific special cases.

Authoring UX v2 rules:

- Road endpoints should be selected through `from_intersection_path` and `to_intersection_path`
  NodePath fields, not by manually typing intersection IDs.
- `RoadSegment` stores actual geometry knobs: `shape_points`, `lanes`, `lane_width_m`,
  `sidewalk_width_m`, and `median_width_m`. It computes length from the scene geometry and exports
  optional SUMO edge shape points.
- Zones can connect to intersections through `intersection_paths`; text IDs are fallback only.
- Traffic lights and investment candidates can point to an intersection node through
  `intersection_path`. VND cost fields belong to `InvestmentCandidateMarker`, not to the traffic
  light itself.
- Demand is modeled as OD flow (`DemandFlow`) from origin zone to destination zone. It is not a
  physical game-style spawn point.
- The exporter validates duplicate IDs and broken references before writing `district_spec`.

Current no-code authoring presets:

- `res://scenes/authoring/presets/ResidentialZone.tscn`
- `res://scenes/authoring/presets/HospitalZone.tscn`
- `res://scenes/authoring/presets/SchoolZone.tscn`
- `res://scenes/authoring/presets/IndustrialZone.tscn`
- `res://scenes/authoring/presets/NightlifeZone.tscn`
- `res://scenes/authoring/presets/GatewayZone.tscn`
- `res://scenes/authoring/presets/SignalizedIntersection.tscn`
- `res://scenes/authoring/presets/UnsignalizedIntersection.tscn`

## Replay layer

The replay path is offline for now:

```text
SUMO runs first
  -> writes trace/net artifacts
  -> Godot reads and replays them
```

It is not realtime SUMO ↔ Godot synchronization.

Main pieces:

- `TraceReplayData`: loads vehicle-level trace JSONL.
- `TraceFrameData` / `TraceVehicleState`: typed runtime objects created after JSON parse.
- `schema_versions.gd`: central Godot constants for supported cross-system schema versions.
- `TracePlaybackClock`: owns play/pause/restart, loop, speed, and current trace time.
- `TraceInterpolator`: samples vehicle positions between neighboring trace frames.
- `CoordinateMapper`: maps SUMO meters into Godot world coordinates.
- `SumoNetGeometryData` / `SumoLaneGeometry` / `SumoJunctionGeometry`: typed SUMO net geometry.
- `DistrictReplayWorld`: renders SUMO lanes/junctions or spec fallback geometry.
- `TraceReplayController`: asks the clock/interpolator for a frame, then updates vehicles.

## Vehicle asset layer

Vehicle selection must go through:

```text
VehicleAssetRegistry -> VehicleFactory -> VehiclePool
```

- `VehicleAssetRegistry` maps vehicle type to scene path.
- `VehicleFactory` instantiates the right scene.
- `VehiclePool` reuses hidden nodes rather than constantly instancing/freeing vehicles.

`TraceReplayController` should not contain `if vehicle_type == "BUS"` style scene selection.

## Config and schema rule

Cross-system/generated data stays JSON/XML:

- `district_spec.json`;
- `simulation_trace.jsonl`;
- `district.net.xml`;
- metrics/finance summaries;
- CV dataset manifests used by Python tooling.

Godot-only visual configuration can become `.tres` / Resource files later when designers need
Inspector-friendly editing:

- visual render presets;
- camera rig presets if Godot-only;
- material/theme resources;
- asset configuration that no Python tool needs to read.

Current version labels:

- `simulation_trace_frame.v1`;
- `vehicle_asset_manifest.v1`;
- `sumo_net_xml.v1` as an internal parsed-data label.

Loaders should reject unsupported versions clearly.

## CV/sensor boundary

YOLO/CV must not read hidden SUMO state at inference time.

Correct synthetic CV path:

```text
SUMO trace
  -> Godot camera render
  -> image frame + labels
  -> YOLO train/evaluate
  -> detected observations
```

SUMO/Godot ground truth may generate labels and measure sensor error. The model input must still be
rendered images/video if the work is presented as CV.

## Current gaps

Before this becomes a polished demo renderer, the project still needs:

- better district/map design after the team chooses what to simulate;
- real vehicle/building/road assets;
- camera rigs and render presets;
- synthetic CV dataset exporter beyond smoke output;
- optional UI/HUD for demo;
- optional native Godot tests if GDScript grows much further.
