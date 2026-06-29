# Data scripts

These scripts prepare or validate dataset folders for the three project streams:

- `cv_yolo`: image/video/annotation datasets for YOLO-based traffic sensing.
- `rl_sumo`: SUMO/SUMO-RL scenario inputs and generated simulation artifacts.
- `public_finance`: cost, budget, public-value, and sensitivity tables.

The scripts are intentionally light in this scaffold. They define expected folders and manifest
shapes before real datasets exist.

## Synthetic CV dataset

`prepare_synthetic_cv_dataset.py` defines the Godot-rendered YOLO dataset contract:

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py `
  --dataset-id SYNTH-CV-GODOT-V0 `
  --output-root data/processed/cv_yolo `
  --init-template `
  --validate
```

Generated images, labels, videos, and render logs must stay out of Git. Push processed dataset
folders to the Drive Data Hub with:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py `
  --drive-root "<Data Hub local path>" `
  push-dataset `
  --stream cv_yolo `
  --dataset-id SYNTH-CV-GODOT-V0 `
  --source data/processed/cv_yolo/SYNTH-CV-GODOT-V0
```

Add `--apply` only after the dry-run copy plan is correct.
