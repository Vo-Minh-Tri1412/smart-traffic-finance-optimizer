# Godot Render Workspace

`render/` is the Godot app for visual replay, demo rendering, and future synthetic CV dataset
generation.

It is **not** the traffic simulator. SUMO/SUMO-RL remains the official backend for traffic dynamics,
routes, queues, traffic-light policies, RL training, and metrics. Godot consumes SUMO traces and
renders them as scenes.

## Current status

- Godot project created with Godot 4.6.
- Godot AI MCP plugin installed under `addons/godot_ai`.
- Codex is configured through the Godot AI MCP server.
- Tiny headless smoke exporter exists under `scripts/dataset_export/`.
- Final district scene, assets, replay controller, and camera export pipeline are not implemented
  yet.

## Scene-first architecture

Godot prefers scenes as reusable objects. This project follows that style:

```text
render/
├── project.godot
├── scenes/
│   ├── main/       # Main.tscn, app entry scene
│   ├── world/      # DistrictWorld, roads, intersections, traffic lights
│   ├── vehicles/   # VehicleBase, car, motorbike, bus, ambulance, truck
│   ├── sensors/    # DetectionCamera, CameraRig
│   └── ui/         # Replay HUD, finance panel, scenario controls
├── scripts/
│   ├── replay/         # SUMO trace replay and coordinate mapping
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

The intended runtime flow is:

```text
SUMO/SUMO-RL run
  -> simulation_trace.jsonl / FCD-derived vehicle trace
  -> Godot TraceReplayController
  -> scene instances from asset_manifest
  -> camera frames, video, YOLO labels, and demo visuals
```

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
- YOLO inference may only read rendered frames, not hidden SUMO state.
- Labels may be generated from SUMO/Godot ground truth during dataset generation.
- Scene names and config keys should remain stable so Python, Godot, and future React tooling can
  talk through explicit contracts.
