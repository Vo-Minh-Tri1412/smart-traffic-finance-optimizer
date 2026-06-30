# Godot Render Workspace

`render/` is the Godot app for map authoring, visual replay, demo rendering, and future synthetic CV
dataset generation.

It is **not** the traffic simulator. SUMO/SUMO-RL remains the official backend for traffic dynamics,
routes, queues, traffic-light policies, RL training, and metrics. Godot designs the district map,
exports a backend `district_spec`, then consumes SUMO network geometry and vehicle traces for replay.

## Current status

- Godot project created with Godot 4.6.
- Godot AI MCP plugin installed under `addons/godot_ai`.
- Codex is configured through the Godot AI MCP server.
- Tiny headless smoke exporter exists under `scripts/dataset_export/`.
- SUMO vehicle-level trace replay v1 exists with placeholder 3D vehicles and roads.
- Godot map authoring v1 exists: a sample authoring scene can be exported to backend
  `district_spec.generated.json`.
- SUMO net geometry replay v1 exists: Godot can render lanes/junctions from `district.net.xml`, so
  vehicles and roads share SUMO coordinates.
- Final polished assets and camera export pipeline are not implemented yet.

## Scene-first architecture

Godot prefers scenes as reusable objects. This project follows that style:

```text
render/
├── project.godot
├── scenes/
│   ├── main/       # Main.tscn, app entry scene
│   ├── authoring/  # Drag-and-drop map markers and sample authored district
│   ├── world/      # DistrictWorld, roads, intersections, traffic lights
│   ├── vehicles/   # VehicleBase, car, motorbike, bus, ambulance, truck
│   ├── sensors/    # DetectionCamera, CameraRig
│   └── ui/         # Replay HUD, finance panel, scenario controls
├── scripts/
│   ├── replay/         # SUMO trace replay and coordinate mapping
│   ├── authoring/      # Godot scene -> district_spec export scripts
│   ├── world/          # District scene builders and traffic-light state appliers
│   ├── sensors/        # camera capture and label export logic
│   ├── dataset_export/ # headless synthetic CV export scripts
│   └── ui/             # HUD/controller scripts
├── resources/
│   ├── configs/    # asset manifest, camera rigs, label mapping, render presets
│   ├── materials/  # Godot material resources
│   └── prefabs/    # reusable Godot resources/prefabs
├── imported_assets/
│   ├── vehicles/
│   ├── roads/
│   ├── buildings/
│   └── props/
└── outputs/        # local render outputs, ignored by Git
```

The intended authoring and runtime flow is:

```text
Godot Editor authored map
  -> district_spec.generated.json
  -> SUMO/SUMO-RL run
  -> district.net.xml + simulation_trace.jsonl / FCD-derived vehicle trace
  -> Godot TraceReplayController + SUMO net geometry renderer
  -> scene instances from asset_manifest later
  -> camera frames, video, YOLO labels, and demo visuals later
```

## Godot map authoring v1

Open this scene in the Godot editor:

```text
res://scenes/authoring/DistrictAuthoringMap.tscn
```

It is a real drag-and-drop Godot scene containing:

- `IntersectionMarker` for signalized and unsignalized nodes.
- `RoadSegment` for lanes, speed, capacity, truck access, and bidirectional roads.
- `ZoneArea` for residential, hospital, school, industry, market, nightlife, and gateway zones.
- `SpawnPoint` / `DestinationPoint` for default OD flows.
- `TrafficLightMarker` and `InvestmentCandidateMarker` for public-finance decisions.

Export it to a backend spec:

```powershell
uv run python scripts/render/godot_authoring_export.py `
  --out <tmp>/district_spec.generated.json
```

Run the full roundtrip:

```powershell
uv run python scripts/render/godot_authoring_roundtrip_smoke.py `
  --output-root <tmp>/roundtrip `
  --max-frames 60
```

Generated specs, SUMO outputs, traces, screenshots, and replay summaries should stay outside Git.

## Contracts

The important bridge files are:

- `resources/configs/asset_manifest.example.json`: maps simulation object types to Godot scenes.
- `resources/configs/camera_rigs.example.json`: describes camera placement and intended purpose.
- `resources/configs/label_mapping.example.json`: defines YOLO class names and the no-hidden-state
  inference rule.
- `resources/configs/render_presets.example.json`: stores day/night/weather/noise presets.

These files are examples for the future app. The final renderer should load project-specific copies
or generated configs, not silently depend on hand-edited examples.

## Existing smoke exporter

The current smoke exporter is deliberately tiny. It only checks that Godot can write PNG/YOLO-label
files into the repository dataset contract.

Python wrapper:

```powershell
uv run python scripts/render/godot_synthetic_cv_smoke.py --help
```

Godot script:

```text
res://scripts/dataset_export/export_synthetic_cv_smoke.gd
```

## SUMO trace replay v1

The replay scene is intentionally 3D-lite. It proves the SUMO-to-Godot bridge before the team spends
time on nice assets. Prefer replaying with `district.net.xml`; this renders lanes and junctions from
SUMO geometry so vehicles do not drift away from roads.

Main scene:

```text
res://scenes/main/Main.tscn
```

Headless smoke wrapper:

```powershell
uv run python scripts/render/godot_sumo_trace_replay_smoke.py `
  --trace path/to/trace.jsonl `
  --net path/to/district.net.xml `
  --spec ../tests/fixtures/specs/minh_khai_district_v1.json `
  --output-root outputs/godot_replay `
  --max-frames 60
```

If `--trace` is omitted, the wrapper generates a fixture SUMO trace and SUMO net geometry first. The
output is `replay_summary.json`; generated outputs remain ignored by Git.

Implemented v1 pieces:

- `TraceReplayData`: loads vehicle-level JSONL trace frames.
- `CoordinateMapper`: maps SUMO meter coordinates into Godot `x/z` world coordinates.
- `TraceReplayController`: spawns, updates, and despawns placeholder vehicles.
- `DistrictReplayWorld`: builds simple placeholders from specs for fallback, or SUMO lane/junction
  geometry from `district.net.xml` for aligned replay.

This is not realtime SUMO ↔ Godot sync. SUMO still runs first; Godot replays exported trace frames.

## Do not commit generated outputs

Generated outputs must stay out of Git:

- `.godot/`
- `generated/`
- `exports/`
- `screenshots/`
- `datasets/`
- `videos/`
- `captures/`
- `outputs/`

Put generated frames, labels, videos, model outputs, and render logs in the Google Drive Data Hub or
a DVC-managed artifact store later.

## Guardrails

- Godot renders and replays; it does not replace SUMO/SUMO-RL.
- Godot authoring scenes are the source of truth for hand-designed demo maps.
- SUMO `district.net.xml` is the source of truth for replay road/lane geometry.
- Do not hand-edit generated specs if the map has a Godot authoring scene.
- YOLO inference may only read rendered frames, not hidden SUMO state.
- Labels may be generated from SUMO/Godot ground truth during dataset generation.
- Scene names and config keys should remain stable so Python, Godot, and future React tooling can
  talk through explicit contracts.
