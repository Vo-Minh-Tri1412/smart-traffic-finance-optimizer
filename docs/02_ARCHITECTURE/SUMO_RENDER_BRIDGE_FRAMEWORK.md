# SUMO-backed Render Bridge Framework

This is the canonical architecture for connecting SUMO/SUMO-RL traffic simulation to visual
renderers, synthetic sensors, and demo surfaces.

The project is not trying to replace SUMO. The project is building a bridge framework around SUMO:
traffic simulation, public-finance scoring, and visual/sensor replay all share one normalized set of
contracts.

## Why this framework exists

Traffic-simulation render projects tend to repeat the same problem: SUMO knows the traffic, while a
game engine knows how to show a city. Strong open-source patterns point in the same direction:

- [SUMO2Unity](https://github.com/SimuTraffX-Lab/SUMO2Unity) imports SUMO networks into Unity and
  exchanges vehicle trajectory and signal timing data.
- [Sumonity](https://github.com/TUM-VT/Sumonity) uses a Unity bridge/prefab pattern and keeps SUMO
  as the microscopic traffic model.
- [CARLA SUMO co-simulation](https://carla.readthedocs.io/en/latest/adv_sumo/) explicitly decides
  which simulator owns traffic lights and synchronized state.
- [SumoUE4](https://github.com/iwer/SumoUE4) highlights the need to separate SUMO data from visual
  representation.

The local framework follows those patterns without copying their code. Godot is the current
reference renderer, but the contracts should be renderer-independent.

## Authority ownership

Only one layer owns each kind of truth.

| Layer | Owns | Must not own |
|---|---|---|
| SUMO/SUMO-RL | routes, vehicle motion, queues, traffic-light phases, traffic-event effects | visual assets, camera framing, finance decisions |
| Python bridge | scenario config, SUMO execution, output parsing, normalized traces, metrics, finance scoring | hand-authored visual choices |
| Semantic overlay | zone meaning, public-finance labels, demand anchors, candidate investment metadata | road/lane geometry truth |
| Godot renderer | assets, materials, camera rigs, replay UI, visual zones, synthetic frame export | traffic physics or RL state |
| Future Unity/Unreal/CARLA adapters | alternate visual/sensor implementation | changing bridge contracts ad hoc |

If ownership is ambiguous, prefer SUMO for traffic state and Godot for visual state.

## End-to-end flow

```text
SUMO/SUMO-RL
  -> net.xml / routes / tripinfo / edge data / FCD / TLS / events
  -> Python bridge contracts
  -> render adapter contract
  -> Godot reference renderer
  -> visual replay / camera frames / labels / demo UI
```

For real maps:

```text
OSM/SUMO map
  -> ROI selection
  -> road classification
  -> auto micro-zoning
  -> semantic overlay
  -> prepared SUMO net
  -> Godot visual overlay and replay
```

Manual Godot authoring is for tiny previews, visual tuning, and overrides. It is not the source of
truth for large real road networks.

## Render bridge layers

The bridge is a conceptual module even when the first implementation is split across existing
scripts.

```text
SumoRenderBridge
├── GeometryProvider          # SUMO net geometry, bounds, lane widths, junction polygons
├── VehicleTraceProvider      # vehicle-level trace frames from FCD
├── TrafficLightStateProvider # TLS phase/state trace
├── SemanticOverlayProvider   # zones, demand anchors, candidate investment metadata
├── EventProvider             # crashes, closures, road works, temporary speed changes
├── RoadVisualProvider        # road style catalog and LOD choices
├── AssetProvider             # vehicle/zone/road visual catalogs
└── SensorExportProvider      # camera frames, labels, masks, manifests
```

The bridge should expose one run summary so smoke tests and demo scripts can decide whether the
visual integration is trustworthy.

## Current implementation mapping

| Framework role | Current Godot/Python implementation |
|---|---|
| Geometry provider | `SumoNetGeometryData`, `DistrictReplayWorld` |
| Vehicle trace provider | `TraceReplayData`, `TraceFrameData`, `TraceVehicleState` |
| Replay timing | `TracePlaybackClock`, `TraceInterpolator` |
| Vehicle visuals | `VehicleAssetCatalog.tres`, registry, factory, pool |
| Zone visuals | `semantic_overlay.json`, `ZoneAssetCatalog.tres`, `SemanticOverlayRenderer` |
| Road visuals | width-aware SUMO lane mesh strips; road style catalog planned as first-class |
| Sensors | `DetectionCamera3D`, camera/label catalogs, smoke dataset writer |
| Quality report | replay summary today; render bridge QA report is the canonical next layer |

## Integration quality report

Every meaningful SUMO-to-render smoke should produce a report with at least:

- loaded lane/junction counts;
- rendered lane/junction counts;
- loaded frames and spawned vehicles;
- dropped or fallback vehicle counts;
- zone rendered and fallback counts;
- `off_lane_vehicle_count` and max off-lane distance;
- traffic-light sync count when TLS trace is present;
- schema versions and unsupported-version warnings;
- average replay FPS when visual runtime can measure it.

The report matters because visual correctness must be testable, not only inspected by eye.

## What should be replaced or downgraded

- Do not let `Main.tscn` become a pile of hard-coded paths and manually wired nodes. It should
  configure a bridge object or a render run manifest.
- Do not render large real maps by instantiating every lane, building, and node as a separate
  editable object. Use SUMO geometry for truth, semantic overlay for meaning, and LOD/batching for
  preview.
- Do not put traffic logic inside Godot. Events may be visualized in Godot, but their traffic effect
  belongs in SUMO/Python.
- Do not treat tiny preview scenes as product maps. They are sandbox fixtures.

## Extension strategy

Godot remains the reference renderer. Future Unity/Unreal/CARLA work should consume the same bridge
contracts rather than forking the backend.

Recommended adapter boundary:

```text
render_run_manifest.v1
  -> geometry_manifest.v1
  -> vehicle_trace.v2
  -> traffic_light_trace.v1
  -> semantic_overlay.v2
  -> event_trace.v1
  -> sensor_dataset_manifest.v1
```

If a future engine cannot consume those artifacts, fix the adapter, not the SUMO backend.
