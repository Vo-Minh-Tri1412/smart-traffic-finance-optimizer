# Godot render architecture

This document is the canonical implementation note for the `render/` Godot project. The framework
architecture lives in `SUMO_RENDER_BRIDGE_FRAMEWORK.md`; this file explains how the Godot reference
renderer implements that framework.

## Role

Godot is the visual replay, real-map overlay editing, asset-preview, and synthetic sensor-render
layer.

It is not the traffic simulator. SUMO/SUMO-RL remains responsible for traffic dynamics, route
movement, queues, traffic-light policies, RL training, and metrics.

Godot is the first render adapter behind the SUMO render bridge, not the center of the whole
simulation system.

## Intended flow

```text
OSM/SUMO prepared map
  -> SUMO district.net.xml + semantic_overlay.json + simulation_trace.jsonl
  -> Godot renders SUMO geometry, semantic overlay visuals, and vehicle traces
  -> calibrated optical visibility features for RL
  -> optional RGB/depth/instance frames and labels
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

The team should not hand-author an entire city inside a separate Godot toy scene. A larger map must
arrive from OSM/SUMO, GeoJSON, a controlled generator, or explicit map-intake artifacts.

Pre-Godot map sources belong in:

```text
simulation_projects/map_intake/
```

That folder is the staging area for:

- raw map sources;
- cleaned/prepared map sources;
- semantic overlays and review notes before Godot visual editing;
- review notes about connectivity, zones, traffic lights, and economic logic.

After a map source is selected or generated, Godot is used to inspect and refine the semantic/visual
layer on top of the prepared real map:

```text
map_intake source
  -> ROI/prepared SUMO net
  -> semantic overlay
  -> Godot replay/render/overlay inspection
```

Large or license-sensitive map files stay out of Git and should be recorded through a map intake
manifest and Google Drive link.

## Project map

```text
render/
├── scenes/
│   ├── main/        # app entry scene
│   ├── world/       # replay world and future world objects
│   ├── vehicles/    # editable vehicle scenes
│   ├── zones/       # editable zone visual scenes
│   ├── sensors/     # future camera/sensor scenes
│   └── ui/          # future replay/demo UI
├── scripts/
│   ├── assets/      # visual catalogs, factories, vehicle pool
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

`VehicleAssetCatalog.tres` maps SUMO vehicle types to editable vehicle wrapper scenes and imported
visual assets.
`ZoneAssetCatalog.tres` maps semantic zone types to zone scenes, ground materials, and building
cluster assets. The semantic overlay remains JSON because Python/SUMO and Godot both read it; the
catalog only controls how those zones look in Godot.
`RoadStyleCatalog.tres` maps SUMO road/lane rendering to Godot road/lane scenes, materials, and
visual knobs.

The current imported art uses Kenney CC0 low-poly assets. Credit Kenney / kenney.nl in public demo
materials even though attribution is not required by the license.

## Real-map overlay editing policy

There is no separate toy authoring scene in the production path. Real editing work should happen
against the same data used by replay:

```text
prepared SUMO net + semantic overlay + render run manifest
  -> Main.tscn / SumoRenderBridge
  -> visual inspection and overlay refinement
```

The road network is not redrawn by hand in Godot. Godot can provide editor tools later for selecting
zones, investment candidates, camera rigs, and asset presets, but those tools must edit the real
semantic overlay or render manifest associated with a prepared SUMO map.

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
- `DistrictReplayWorld`: renders SUMO road edges through a lane-scene builder, plus junction
  polygons or spec fallback geometry.
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

- `VehicleAssetCatalog.tres` maps vehicle type to editable Godot wrapper scenes and optional
  imported `.glb` visual assets.
- `VehicleAssetRegistry` loads the `.tres` catalog first and keeps legacy JSON manifest support for
  compatibility.
- `VehicleFactory` instantiates the right wrapper scene and injects the catalog-selected visual
  asset as a runtime `VisualAsset` child.
- `VehiclePool` reuses hidden nodes rather than constantly instancing/freeing vehicles.
- Concrete vehicle scenes should not hardcode imported `.glb` paths. They are lightweight
  logic/fallback presets; designers replace visible art by editing `VehicleAssetCatalog.tres`.
- The base `Body` cube is a script-compatible fallback. `VehicleFactory` hides it when a catalog
  visual asset exists, so it should not be the visible demo vehicle in normal replay.

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
SUMO lane geometry -> DistrictReplayWorld -> RoadSceneBuilder -> RoadVisualRoot/LaneVisualBase scenes
  -> RoadStyleCatalog.tres materials/knobs
```

The road style catalog is deliberately separate from `SumoNetGeometryData`. SUMO data says where a
lane is and how wide it is; the catalog says which Godot scene/material/style should draw it.

The default road model is scene-composed:

- one SUMO edge becomes one `RoadVisualRoot.tscn`;
- each SUMO lane under that edge becomes one `LaneVisualBase.tscn`;
- road attachments such as traffic lights, signs, barriers, medians, bus-lane markings, or
  road-work props should attach to `RoadVisualRoot/Attachments`, not to SUMO data.

Later road roles can include arterial, collector, service, bus-priority, truck-priority, bridge,
tunnel, and render-only detail.

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

## Optical sensor boundary

YOLO/CV must not read hidden SUMO state at inference time. RL may be trained before YOLO by using a
geometry-based visibility adapter driven by the same SUMO trace.

Correct synthetic CV path:

```text
SUMO trace
  -> camera pose/FOV + vehicle dimensions + lane geometry
  -> depth/instance visibility approximation
  -> lane features + uncertainty for RL
  -> optional RGB/depth/instance frame
  -> optional YOLO train/evaluate
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

Camera rigs must be calibrated against the same world units as the selected Quận 7/ROI SUMO net.
Vehicle assets need a canonical length/width/height mapping; `body_height` alone is only a render
placement value. Occlusion labels should be produced from depth/instance visibility or an equivalent
geometry algorithm, not from projected rectangles alone.

The first smoke implementation may use projected replay vehicle bounds to populate the object-id
mask artifact, but it is not depth-correct and must not be treated as a production occlusion labeler.
The public interface remains compatible with a later true material/object-id/depth render pass.

## Implementation status

Read [Implementation Status](../04_STATUS/IMPLEMENTATION_STATUS.md) for verified renderer and
sensor capability, current gaps and dependency order. This document owns the intended Godot
architecture and must not be read as a progress report.
