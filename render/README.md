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
```

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
