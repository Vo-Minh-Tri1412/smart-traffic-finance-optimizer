# Data scripts

Dataset preparation/validation covers cv_yolo, rl_sumo and public_finance. Templates and inventory
tools do not establish calibrated data or a trained model.

## Synthetic image dataset template

```powershell
uv run python scripts/data/prepare_synthetic_cv_dataset.py --dataset-id SYNTH-CV-UE-V0 --output-root data/processed/cv_yolo --init-template --validate
```

This initializes metadata/layout; it does not render images. The UE RGB/depth/instance exporter is
planned. See [sensor contract](../../docs/02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md).

Use scripts/cloud/drive_desktop_sync.py push-dataset with stream cv_yolo, dataset ID and source
directory for a dry-run copy plan before --apply. Generated datasets/images/models stay in DVC/Drive,
not Git.

prepare_demand_inventory.py groups candidate facility parents and historical population priors.
prepare_map_economic_profile.py joins map entities and explicit economic assumptions. Neither
invents observed OD counts, entrance gates or measured intervention benefits. Follow
[retained demand design](../../docs/02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md) and
[delivery plan](../../docs/02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md).
