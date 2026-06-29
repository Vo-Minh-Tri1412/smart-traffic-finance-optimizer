# Synthetic Visual Sensor Dataset Contract

This document defines the first technical contract for the computer-vision layer.
It is intentionally a contract, not a finished dataset. The project can train later on
Colab/Kaggle/cloud GPU, but the local repository must already know what a valid dataset looks like.

## Why this layer exists

The traffic simulator already knows the internal truth: vehicle ids, positions, routes, speeds,
queues, and traffic-light states. A real camera does not know those values. It only sees pixels.

For that reason, the visual sensor layer must follow one rule:

> The CV model may use rendered camera frames, but it must not read hidden simulator state at
> inference time.

During dataset generation, the renderer may use simulator truth to create labels. During model
inference, YOLO only receives images. This makes the camera layer meaningful instead of a fake
shortcut.

## Intended pipeline

```text
SUMO/SUMO-RL run
  -> vehicle trajectories and traffic-light timeline
  -> Godot 3D renderer
  -> camera frames + generated labels
  -> YOLO-format dataset
  -> train/evaluate vision model on Colab/Kaggle/cloud GPU
  -> exported detections/counts
  -> sensor observation contract used by the traffic system
```

The renderer is allowed to stay synthetic in early versions. Synthetic data is useful because it is
aligned with the simulated district, can include weather/lighting perturbations, and avoids the
awkward mismatch where a real-world dataset sees real cars while the demo city uses simple icons.

## Dataset layout

Each dataset lives under a dataset id, for example:

```text
data/processed/cv_yolo/SYNTH-CV-GODOT-V0/
├── images/
│   ├── train/
│   └── val/
├── labels/
│   ├── train/
│   └── val/
├── data.yaml
├── dataset_manifest.json
├── render_manifest.json
└── camera_config.template.json
```

Generated frames, labels, videos, and render logs are not committed to Git. The repo only commits
scripts, contracts, fixtures, and documentation.

## Default classes

The initial YOLO class list is:

- `motorbike`
- `car`
- `bus`
- `truck`
- `ambulance`
- `worker_shuttle`
- `taxi_ride_hailing`
- `delivery_bike`

This list is deliberately tied to the project’s district simulation rather than a generic COCO
vehicle list. It preserves policy-relevant differences: emergency vehicles, public transport,
logistics, industrial commute, and small urban vehicles.

## What each manifest means

`data.yaml` is the training-facing YOLO config.

`dataset_manifest.json` records the dataset id, format, class names, and whether the folder is only
a template or contains real generated frames.

`render_manifest.json` records the renderer and source run: SUMO/SUMO-RL run id, Godot render id,
camera ids, image size, weather profiles, and caveats.

`camera_config.template.json` is the bridge between map design and visual sensing. It describes
where cameras are placed and why they exist. Later, this should be generated from the district spec
or Godot scene rather than handwritten.

## Drive workflow

Local generated data should be pushed to the CS Data Hub through Google Drive Desktop:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py `
  --drive-root "<local Data Hub path>" `
  push-dataset `
  --stream cv_yolo `
  --dataset-id SYNTH-CV-GODOT-V0 `
  --source data/processed/cv_yolo/SYNTH-CV-GODOT-V0
```

The command is dry-run by default. Add `--apply` only after the copy plan looks correct.

## Validation commands

Create a smoke template:

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py `
  --dataset-id SYNTH-CV-SMOKE `
  --output-root data/processed/cv_yolo `
  --init-template `
  --force
```

Validate it:

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py `
  --dataset-root data/processed/cv_yolo/SYNTH-CV-SMOKE `
  --validate
```

The validator accepts an empty template as a warning-only state. Once real frames exist, it checks
image/label pairing and YOLO label ranges.

## What this does not solve yet

- It does not train YOLO.
- It does not export Godot frames yet.
- It does not replace SUMO/SUMO-RL.
- It does not claim synthetic data is equivalent to real traffic-camera footage.

The goal of task 1 is simply to make future generated data manageable, testable, and easy to sync
without polluting Git.
