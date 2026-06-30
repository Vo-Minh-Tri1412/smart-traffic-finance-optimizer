# Godot Synthetic CV Smoke Export

Task 2 verifies that the visual-sensor data contract is not just folder theory.

The smoke exporter creates a tiny YOLO dataset by asking Godot to generate two synthetic camera
frames and matching labels:

```text
Godot smoke script
  -> PNG frame for train
  -> PNG frame for val
  -> YOLO label files
  -> render_manifest.json
  -> dataset validator from task 1
```

This is intentionally small. It is not a final city renderer and not a YOLO training dataset.
Its job is to catch basic pipeline problems early:

- Can Codex/Python find and run Godot headless?
- Can Godot write images into the dataset folder?
- Are YOLO labels normalized to `0..1`?
- Do image and label file names match?
- Does the task 1 validator accept the generated dataset?

## Command

```powershell
uv run python scripts/render/godot_synthetic_cv_smoke.py `
  --dataset-id SYNTH-CV-GODOT-SMOKE `
  --output-root data/processed/cv_yolo `
  --force
```

Validate again:

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py `
  --dataset-root data/processed/cv_yolo/SYNTH-CV-GODOT-SMOKE `
  --validate
```

The generated folder is ignored by Git. If the smoke dataset is useful to inspect or share, sync it
through Drive Desktop:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py `
  --drive-root "<local Data Hub path>" `
  push-dataset `
  --stream cv_yolo `
  --dataset-id SYNTH-CV-GODOT-SMOKE `
  --source data/processed/cv_yolo/SYNTH-CV-GODOT-SMOKE
```

Add `--apply` only after the dry-run copy plan is correct.

## Godot-side location

The Godot project lives in `render/` and is organized as a scene-first renderer. The current smoke
export script is located at:

```text
render/scripts/dataset_export/export_synthetic_cv_smoke.gd
```

Future replay/dataset code should stay inside the purpose-specific folders:

- `render/scenes/` for reusable Godot scenes;
- `render/scripts/replay/` for SUMO trace replay;
- `render/scripts/sensors/` for camera capture and label export;
- `render/resources/configs/` for asset, camera, label, and render preset contracts.

## Caveat

The current smoke scene uses a simple Godot-generated top-down image, not the final 3D district
render. That is deliberate: this task tests the plumbing. A later exporter should replay SUMO/SUMO-RL
trajectories into a richer Godot 3D scene with cameras, weather, lighting, and occlusion.
