# Godot render workspace

`render/` is the Godot project for map authoring, SUMO trace replay, future demo rendering, and
future synthetic CV dataset generation.

Full architecture:

```text
../docs/02_ARCHITECTURE/GODOT_RENDER_ARCHITECTURE.md
```

Key rule:

- SUMO/SUMO-RL is the traffic simulator.
- Godot is the authoring/render/replay layer.
- YOLO/CV may only read rendered camera frames, not hidden SUMO state.

Useful scenes:

```text
res://scenes/main/Main.tscn
res://scenes/authoring/DistrictAuthoringMap.tscn
res://scenes/authoring/presets/*.tscn
```

Visual assets live under:

```text
res://imported_assets/
```

Use that folder for Godot-ready vehicles, buildings, road/intersection visuals, street furniture,
camera rigs, materials, textures, weather visuals, and UI assets.

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
