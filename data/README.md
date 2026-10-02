# Data Workspace

This folder holds small data contracts and templates that are safe to keep in Git.

Large or generated artifacts are managed by DVC and Google Drive Desktop, not committed directly.
See `docs/02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md` for the current DVC workflow.

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
- Unreal synthetic CV datasets (planned capture);
- Colab/Kaggle training outputs;
- model checkpoints and exported weights.

The configured DVC remote is `drive_desktop`. Its local backing and cloud sync availability
were not revalidated in the 2026-09-20 audit.

## Evidence ownership

The Economics/Public Finance team defines assumptions and policy scenarios. The CS team defines how
those assumptions become SUMO-RL inputs and reproducible outputs.

Use the catalog templates in this order:

1. `source_registry.template.csv`: list public-finance and traffic assumption sources.
2. `variable_dictionary.template.csv`: define traffic, cost, and policy variables.
3. `crawl_plan.template.csv`: convert approved sources into a technical collection or manual-entry plan.

No real collection starts until the team has reviewed source reliability, legal/crawl constraints,
update frequency, expected output format, and whether the artifact should be DVC-tracked.
