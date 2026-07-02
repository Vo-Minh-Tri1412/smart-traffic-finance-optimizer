# Godot render workspace

`render/` is the Godot project for map authoring, SUMO trace replay, future demo rendering, and
future synthetic CV dataset generation.

Full architecture:

```text
../docs/02_ARCHITECTURE/GODOT_RENDER_ARCHITECTURE.md
../docs/02_ARCHITECTURE/SUMO_RENDER_BRIDGE_FRAMEWORK.md
../docs/02_ARCHITECTURE/RENDER_BRIDGE_CONTRACTS.md
```

Key rule:

- SUMO/SUMO-RL is the traffic simulator.
- Godot is the authoring/render/replay layer.
- YOLO/CV may only read rendered camera frames, not hidden SUMO state.

Useful scenes:

```text
res://scenes/main/Main.tscn
res://scenes/authoring/BlankAuthoringMap.tscn
res://scenes/authoring/DistrictAuthoringMap.tscn  # sample/sandbox, not Quận 7
res://scenes/authoring/presets/*.tscn
```

For large OSM/SUMO maps such as Quận 7, `DistrictReplayWorld` keeps full SUMO geometry for
alignment checks but renders a capped LOD subset by default. If the game window looks empty, wait
for the first load, then use the editor camera/game camera controls; do not disable LOD unless you
really want Godot to instantiate tens of thousands of lane/junction meshes.

Road rendering now reads lane shape and width from the SUMO `.net.xml` and draws visible lanes as
continuous mesh strips. If roads look like isolated dots or detached black dashes, treat that as a
render regression and run the replay smoke command below.

Visual assets live under:

```text
res://imported_assets/
```

Use that folder for Godot-ready vehicles, buildings, road/intersection visuals, street furniture,
camera rigs, materials, textures, weather visuals, and UI assets.

Designer-editable visual catalogs live under:

```text
res://resources/catalogs/VehicleAssetCatalog.tres
res://resources/catalogs/ZoneAssetCatalog.tres
res://resources/catalogs/RoadStyleCatalog.tres
```

Use `.tres` catalogs for visual choices that only Godot needs, such as which scene/material a
vehicle, zone, or road style should use. Keep SUMO/overlay/trace/project data as JSON/XML.

`Main.tscn` now includes a `SumoRenderBridge` node as the future central wiring point. Existing
replay modules still run directly while the bridge migration happens incrementally.

The current low-poly starter assets are Kenney CC0 assets. Crediting Kenney / kenney.nl in public
materials is recommended.

Pre-Godot map sources do **not** belong in `render/`. Put OSM/SUMO/GeoJSON/synthetic seed maps in:

```text
../simulation_projects/map_intake/
```

No-code map authoring rule of thumb:

- Drag or duplicate `IntersectionMarker`, `RoadSegment`, `ZoneArea`, `DemandFlow`,
  `TrafficLightMarker`, and `InvestmentCandidateMarker` nodes.
- Prefer NodePath fields such as `from_intersection_path`, `to_intersection_path`,
  `origin_zone_path`, `destination_zone_path`, and `intersection_path`.
- Treat text ID fields as fallback/compatibility fields only.
- VND cost fields live on `InvestmentCandidateMarker`; traffic lights only describe signal control.

Useful smoke commands:

```powershell
uv run python scripts/render/godot_authoring_export.py --out <tmp>/district_spec.generated.json

uv run python scripts/render/godot_authoring_roundtrip_smoke.py `
  --output-root <tmp>/roundtrip `
  --max-frames 60

uv run python scripts/render/godot_sumo_trace_replay_smoke.py `
  --output-root <tmp>/godot_replay `
  --max-frames 60

uv run python scripts/smoke/district7_roundtrip_smoke.py `
  --output-root <tmp>/district7_roundtrip `
  --require-godot

uv run python scripts/render/godot_sensor_dataset_smoke.py `
  --dataset-root <tmp>/sensor_dataset `
  --force
```

Generated outputs stay out of Git:

- `.godot/`
- `generated/`
- `exports/`
- `screenshots/`
- `datasets/`
- `videos/`
- `captures/`
- `outputs/`
