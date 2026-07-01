# Data Workspace

This folder holds small data contracts and templates that are safe to keep in Git.

Large or generated artifacts are managed by DVC and Google Drive Desktop, not committed directly.
See `docs/02_ARCHITECTURE/DVC_DATA_MANAGEMENT.md` for the current DVC workflow.

## Folder Roles

- `raw/`: small placeholders or catalog examples only; real raw data should be DVC-tracked.
- `interim/`: temporary transformed placeholders only; real interim artifacts should be DVC-tracked.
- `processed/`: model-ready schema examples only; real processed outputs should be DVC-tracked.
- `external/`: small public-finance/source templates; large external extracts should be DVC-tracked.
- `catalog/`: small metadata templates that are safe to commit.

## DVC-backed artifact classes

Use DVC for:

- raw OSM extracts;
- SUMO network/routes/traces/tripinfo outputs;
- Godot synthetic CV datasets;
- Colab/Kaggle training outputs;
- model checkpoints and exported weights.

The default DVC remote is `drive_desktop`, backed by the team's Drive Desktop data-management
workspace.

## Week 1 Rule

The Economics/Public Finance team defines assumptions and policy scenarios. The CS team defines how
those assumptions become SUMO-RL inputs and reproducible outputs.

Use the catalog templates in this order:

1. `source_registry.template.csv`: list public-finance and traffic assumption sources.
2. `variable_dictionary.template.csv`: define traffic, cost, and policy variables.
3. `crawl_plan.template.csv`: convert approved sources into a technical collection or manual-entry plan.

No real collection starts until the team has reviewed source reliability, legal/crawl constraints,
update frequency, expected output format, and whether the artifact should be DVC-tracked.
