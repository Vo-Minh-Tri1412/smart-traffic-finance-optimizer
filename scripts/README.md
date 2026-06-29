# Scripts layout

This folder is organized by operational responsibility.

- `admin/`: repository governance and manifest validation.
- `smoke/`: local smoke checks for installed tools such as SUMO/SUMO-RL.
- `data/`: dataset preparation and validation helpers. These scripts may write into ignored
  local data folders or Google Drive Desktop folders, never into tracked dataset files.
- `artifacts/`: training-run and artifact folder scaffolding.
- `cloud/`: Google Drive Desktop / Colab / Kaggle handoff helpers.

Large data, model checkpoints, videos, logs, TensorBoard runs, and generated reports must stay
outside Git. Put them in the CS Workspace Data Hub on Google Drive.
