# Godot render architecture

This document is the canonical implementation note for the `render/` Godot project. The framework
architecture lives in `SUMO_RENDER_BRIDGE_FRAMEWORK.md`; this file explains how the Godot reference
renderer implements that framework.

## Role

Godot is the visual authoring, replay, and synthetic sensor-render layer.

It is not the traffic simulator. SUMO/SUMO-RL remains responsible for traffic dynamics, route
movement, queues, traffic-light policies, RL training, and metrics.

Godot is the first render adapter behind the SUMO render bridge, not the center of the whole
simulation system.

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

The intended bridge-level flow is:

```text
render_run_manifest.v1
  -> SumoRenderBridge
  -> geometry / vehicle trace / traffic lights / semantic overlay / sensors
```

The current scene keeps legacy direct wiring while `SumoRenderBridge` is introduced as the central
coordination layer for the next refactor.

SUMO lane rendering is width-aware. `SumoNetGeometryData` reads each lane shape and lane width from
the SUMO `.net.xml`; `DistrictReplayWorld` renders each visible lane as a continuous mesh strip
instead of many detached boxes. This is still a lightweight preview renderer, but the road surface is
now tied to SUMO lane geometry rather than hand-drawn visual guesses.

Large real maps should use preview LOD in Godot: keep the full parsed SUMO geometry for coordinate
mapping, zone anchors, and off-lane checks, but render only a capped subset of lane/junction meshes
for interactive preview. Rendering every Quận 7 lane and junction as a separate MeshInstance can
freeze or close the game window on normal laptops.

For real OSM/SUMO maps such as Quận 7, Godot should not render roads from a hand-authored
`district_spec`. The replay layer must read the same SUMO `.net.xml` used by SUMO simulation, then
map FCD vehicle positions through the same bounds/scale. This is the guardrail that prevents the
visual bug where cars appear to drive through residential/background areas.

## Map source intake

The team does not have to hand-author an entire city inside Godot from zero. A larger map may first
arrive from OSM, SUMO, GeoJSON, a synthetic generator, or manual planning notes.

Pre-Godot map sources belong in:

```text
simulation_projects/map_intake/
```

That folder is the staging area for:

- raw map sources;
- cleaned/prepared map sources;
- seed specs before Godot editing;
- review notes about connectivity, zones, traffic lights, and economic logic.

After a map source is selected or generated, Godot is used to refine the semantic/visual layer:

```text
map_intake source
  -> Godot authoring scene
  -> district_spec.generated.json
  -> SUMO run
  -> Godot replay/render
```

Large or license-sensitive map files stay out of Git and should be recorded through a map intake
manifest and Google Drive link.

## Project map

```text
render/
├── scenes/
│   ├── main/        # app entry scene
│   ├── authoring/   # drag-and-drop map markers
│   │   └── presets/ # reusable zone/intersection presets for no-code editing
│   ├── world/       # replay world and future world objects
│   ├── vehicles/    # editable vehicle scenes
│   ├── zones/       # editable zone visual scenes
│   ├── sensors/     # future camera/sensor scenes
│   └── ui/          # future replay/demo UI
├── scripts/
│   ├── assets/      # visual catalogs, factories, vehicle pool
│   ├── authoring/   # Godot scene -> district_spec export
│   ├── bridge/      # SumoRenderBridge orchestration layer
│   ├── contracts/   # schema/version constants
│   ├── replay/      # trace loading, clock, interpolation, replay controller
│   ├── traffic/     # traffic-light trace/state visual layer
│   ├── world/       # SUMO net geometry parsing/rendering
│   ├── zones/       # semantic overlay renderer and zone visuals
│   └── dataset_export/
├── resources/
│   ├── catalogs/    # Godot .tres visual asset catalogs
│   ├── configs/     # legacy JSON examples and future non-visual configs
│   └── materials/   # Godot visual materials
├── imported_assets/ # Godot-ready art assets
└── outputs/         # ignored local render outputs
```

## Visual asset library

Godot scenes can directly instance assets from:

```text
render/imported_assets/
```

The current asset scaffold separates:

- vehicles;
- buildings by semantic zone type;
- roads and road materials;
- intersections;
- traffic lights;
- street furniture;
- cameras;
- weather/render visuals;
- materials/textures;
- UI assets.

Visual selection now uses Godot-native `.tres` catalogs when designers need Inspector-friendly
editing:

```text
res://resources/catalogs/VehicleAssetCatalog.tres
res://resources/catalogs/ZoneAssetCatalog.tres
```

`VehicleAssetCatalog.tres` maps SUMO vehicle types to editable vehicle scenes.
`ZoneAssetCatalog.tres` maps semantic zone types to zone scenes, ground materials, and building
cluster assets. The semantic overlay remains JSON because Python/SUMO and Godot both read it; the
catalog only controls how those zones look in Godot.
`RoadStyleCatalog.tres` maps SUMO road/lane rendering to Godot materials and road visual knobs.

The current imported art uses Kenney CC0 low-poly assets. Credit Kenney / kenney.nl in public demo
materials even though attribution is not required by the license.

## Authoring layer

The authoring scene is:

```text
res://scenes/authoring/DistrictAuthoringMap.tscn
```

This scene is a small sample/sandbox with hand-authored intersections. It is not Quận 7 and should
not be presented as the main map. New manual authoring work should start from:

```text
res://scenes/authoring/BlankAuthoringMap.tscn
```

For Quận 7 and other real maps, the main replay path is SUMO `.net.xml` + semantic overlay + trace
inside `res://scenes/main/Main.tscn`.

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

- `SumoRenderBridge`: central orchestration layer for render run manifests and module wiring.
- `TraceReplayData`: loads vehicle-level trace JSONL.
- `TraceFrameData` / `TraceVehicleState`: typed runtime objects created after JSON parse.
- `schema_versions.gd`: central Godot constants for supported cross-system schema versions.
- `TracePlaybackClock`: owns play/pause/restart, loop, speed, and current trace time.
- `TraceInterpolator`: samples vehicle positions between neighboring trace frames.
- `CoordinateMapper`: maps SUMO meters into Godot world coordinates.
- `SumoNetGeometryData` / `SumoLaneGeometry` / `SumoJunctionGeometry`: typed SUMO net geometry.
- `DistrictReplayWorld`: renders SUMO lane-width mesh strips/junction polygons or spec fallback
  geometry.
- `TraceReplayController`: asks the clock/interpolator for a frame, then updates vehicles.
- `TrafficLightStateLayer`: loads first-class traffic-light trace state for visual synchronization.

Replay smoke tests should fail when a SUMO net is supplied and vehicles are far from lane geometry.
The current `off_lane_vehicle_count` check is intentionally strict for backend/render alignment; if a
future visual asset is wider than the lane, fix rendering scale/assets rather than hiding the
geometry mismatch.

Scenario events such as crashes, lane closures, road works, or temporary speed reductions are not
part of the render layer. SUMO can support those later through a scenario-event layer, but this
document intentionally treats render as a geometry/replay consumer, not as the source of traffic
events.

Traffic-light state is different from scenario events: SUMO owns the phase/state, but Godot should
render the state as a first-class visual layer when a `traffic_light_trace.v1` artifact is provided.

## Vehicle asset layer

Vehicle selection must go through:

```text
VehicleAssetCatalog.tres -> VehicleAssetRegistry -> VehicleFactory -> VehiclePool
```

- `VehicleAssetCatalog.tres` maps vehicle type to editable Godot scenes.
- `VehicleAssetRegistry` loads the `.tres` catalog first and keeps legacy JSON manifest support for
  compatibility.
- `VehicleFactory` instantiates the right scene.
- `VehiclePool` reuses hidden nodes rather than constantly instancing/freeing vehicles.

`TraceReplayController` should not contain `if vehicle_type == "BUS"` style scene selection.

## Zone visual asset layer

Zone visuals mirror the vehicle pattern but use Godot resources from the start:

```text
semantic_overlay.json -> SemanticOverlayRenderer -> ZoneAssetCatalog.tres -> ZoneVisualBase
```

- The overlay says what a zone means: hospital, residential, industrial, school, nightlife.
- The catalog says how that zone looks: zone scene, material, building scenes, density, and seed.
- `SemanticOverlayRenderer` anchors zone visuals to SUMO edge IDs when geometry is available.
- Zone building clusters are visual placeholders for demo readability; they are not official OSM
  building imports.

The Godot zone scene taxonomy follows traffic behavior, not every small OSM tag. Tags such as
`school`, `university`, and `college` should map to one `education` visual because the traffic
story is mainly drop-off/pick-up peaks. The current visual taxonomy is:

```text
residential
commercial
market_retail
education
healthcare
industrial
port_logistics
transport_hub
public_service
nightlife
gateway
mixed
```

Bulk zone design should be data-first:

```text
OSM tags -> auto-zoning taxonomy -> semantic overlay -> ZoneAssetCatalog.tres -> Godot preview
```

Designers should tune zone profiles in batches by taxonomy, density, scale, material, and traffic
meaning, then manually override only unusual zones. Do not hand-edit every generated zone unless the
ROI is already tiny; the auto-zoning output should carry the repetitive work.

## Road visual asset layer

Road geometry comes from SUMO `.net.xml`; road appearance comes from Godot style resources:

```text
SUMO lane geometry -> DistrictReplayWorld -> RoadStyleCatalog.tres -> lane/junction materials
```

The road style catalog is deliberately separate from `SumoNetGeometryData`. SUMO data says where a
lane is and how wide it is; the catalog says how Godot should draw it. Later road roles can include
arterial, collector, service, bus-priority, truck-priority, bridge, tunnel, and render-only detail.

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
- vehicle/zone/building asset catalogs that no Python tool needs to read.

Current version labels:

- `simulation_trace_frame.v1`;
- `geometry_manifest.v1`;
- `vehicle_trace.v2`;
- `traffic_light_trace.v1`;
- `semantic_overlay.v2`;
- `event_trace.v1`;
- `render_run_manifest.v1`;
- `sensor_dataset_manifest.v1`;
- `vehicle_asset_manifest.v1`;
- `vehicle_asset_catalog.v1`;
- `zone_asset_catalog.v1`;
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

The sensor architecture is V2-ready even before training:

- `DetectionCamera3D` is a real Godot camera rig, not a fake 2D drawing script.
- `CameraRigCatalog.tres` stores editable multi-camera positions, roles, splits, FOV, and image size.
- `LabelMappingCatalog.tres` maps simulation vehicle types to CV class ids/names.
- `ObjectIdRegistry` and the mask-pass interface create object-id mask artifacts for labels.
- `SensorDatasetWriter` writes RGB frames, YOLO labels, object-id masks, and frame manifests.

The first smoke implementation may use projected replay vehicle bounds to populate the object-id
mask artifact, but the public interface is intentionally compatible with a later true
material/object-id render pass. Do not train or claim real CV quality until the dataset is generated
from reviewed assets, camera rigs, scenarios, and render presets.

## Current gaps

Before this becomes a polished demo renderer, the project still needs:

- better district/map design after the team chooses what to simulate;
- better vehicle/building/road art assets and materials;
- ROI-specific visual LOD/camera presets for the selected demo map;
- bridge manifest wiring to replace hard-coded scene paths in `Main.tscn`;
- road style catalog expansion for road categories and markings;
- traffic-light visual models synced from `traffic_light_trace.v1`;
- a later SUMO scenario-event layer for incidents, closures, and temporary speed changes;
- camera rigs and render presets;
- synthetic CV dataset exporter beyond smoke output;
- optional UI/HUD for demo;
- optional native Godot tests if GDScript grows much further.
