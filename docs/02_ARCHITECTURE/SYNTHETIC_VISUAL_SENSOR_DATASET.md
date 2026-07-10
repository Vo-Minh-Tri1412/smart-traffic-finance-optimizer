# Synthetic Visual Sensor Dataset and Optical Visibility Contract

This document defines the first technical contract for the computer-vision layer.
It is intentionally a contract, not a finished dataset. The project can train RL before YOLO by
using a geometry-based optical visibility adapter. YOLO remains an optional detector layer for later
detector-specific error modeling and validation.

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
  -> calibrated Godot 3D camera and visibility pass
  -> visible/occluded lane features for geometry-only RL
  -> optional RGB/depth/instance frames and YOLO labels
  -> optional detector training/evaluation on Colab/Kaggle/cloud GPU
  -> observed detections/counts and uncertainty
  -> sensor observation contract used by the traffic system
```

The renderer is allowed to stay synthetic in early versions. Synthetic geometry is useful because it is
aligned with the simulated district, can include weather/lighting perturbations, and avoids the
awkward mismatch where a real-world dataset sees real cars while the demo city uses simple icons.

The first visibility model does not require a trained CV model. Camera pose, FOV, lane geometry and
vehicle 3D dimensions can determine approximate depth ordering and visible fraction. This models
structured bus/truck occlusion. It does not by itself model false positives, class confusion,
rain/glare or motion-blur detector failures.

The Godot project is intentionally organized as a real app under `render/`, not as a loose asset
folder. Simulation vehicle types should map to Godot scenes through the Godot-native vehicle asset
catalog:

```text
vehicle_type = "ambulance"
  -> render/resources/catalogs/VehicleAssetCatalog.tres
  -> res://scenes/vehicles/Ambulance.tscn
  -> DetectionCamera captures rendered pixels
  -> YOLO label exporter writes class id and bounding box
```

The old JSON asset manifest remains compatibility-only. Visual asset choices that only Godot needs
belong in `.tres` catalogs so designers can edit them in the Inspector.

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

`camera_config.template.json` is the bridge between map design and visual sensing. It describes where
cameras are placed and why they exist. Production camera entries must also record calibrated pose,
FOV/intrinsics, image size, capture interval and the target approaches/intersections. Later, this
should be generated from the district spec or render manifest rather than handwritten in isolation.

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
- It does not export a final large-ROI RGB/depth/instance dataset yet.
- It does not replace SUMO/SUMO-RL.
- It does not claim synthetic data is equivalent to real traffic-camera footage.
- It does not yet provide a canonical `height_m`/road-elevation contract for vehicles.

The original smoke exporter only proves the PNG/label plumbing. The newer sensor smoke path is the
architecture target:

```text
SUMO trace replay in Godot
  -> DetectionCamera3D rigs from CameraRigCatalog.tres
  -> RGB viewport frame
  -> ObjectIdRegistry + mask-pass interface
  -> YOLO labels + object-id mask image + sensor_frame_manifest.jsonl
```

The current object-id mask smoke uses projected Godot replay vehicle nodes to produce an object-id
mask artifact. It is intentionally shaped like the future material/object-id render pass, but it is
not a depth-correct occlusion labeler. The production pass must use depth/instance visibility or an
equivalent deterministic geometry algorithm before the dataset is used for sensor claims.

Godot-only sensor configuration is stored as `.tres` resources:

- `CameraRigCatalog.tres`: editable multi-camera rigs, roles, splits, FOV, and image size.
- `LabelMappingCatalog.tres`: project vehicle types mapped to YOLO class ids/names.

Cross-system outputs remain JSON/JSONL/YAML because Python, Colab/Kaggle, Drive, and review scripts
need to read them.
