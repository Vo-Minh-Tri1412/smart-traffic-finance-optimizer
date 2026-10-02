# Scripts layout

This folder is organized by operational responsibility.

Audit 2026-09-20: retained-project roundtrip is blocked by overlay schema mismatch; the existence
of smoke scripts does not prove that the unchanged map pipeline currently passes.

- `training/`: DistrictSpec-based PPO/stack/LSTM scaffold, not retained-net training.
- `render/`: native UE build/replay helpers; sensor export remains planned.
- `finance/`: map-aware QUBO CLI; coefficients are inputs, not automatically measured impacts.
- `maps/`: map preparation utilities; do not recut the retained map for the pilot.
- `sensors/`: offline geometry visibility tools, not a trained detector.
- `admin/`: repository governance and manifest validation.
- `smoke/`: local smoke checks for installed tools such as SUMO/SUMO-RL, including the Quận 7
  SUMO-net/Unreal-contract roundtrip.
- `data/`: dataset preparation and validation helpers. These scripts may write into ignored
  local data folders or Google Drive Desktop folders, never into tracked dataset files.
- `artifacts/`: training-run and artifact folder scaffolding.
- `cloud/`: Google Drive Desktop / Colab / Kaggle handoff helpers.

Large data, model checkpoints, videos, logs, TensorBoard runs, and generated reports must stay
outside Git. Put them in the CS Workspace Data Hub on Google Drive.
