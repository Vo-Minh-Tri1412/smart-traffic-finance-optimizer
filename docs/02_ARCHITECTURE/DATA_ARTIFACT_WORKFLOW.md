# Data and Artifact Workflow

The project uses GitHub for code and Google Drive for data/model/output artifacts.

```text
local code -> GitHub -> Colab/Kaggle
local or Drive Desktop data -> preprocess -> Google Drive Data Hub
Colab/Kaggle -> train/evaluate -> Google Drive Data Hub -> local via Drive Desktop
```

## Why this split exists

Git is good for code, small specs, tests, notebooks, and documentation. It is bad for videos,
large datasets, model weights, training logs, TensorBoard runs, and generated reports.

Google Drive is the artifact store. It holds raw data, processed data, training runs, model
artifacts, metrics, logs, and reports.

## Drive Data Hub

The CS Workspace contains:

```text
00_Data_Management/
├── 00_Registry/
├── 01_Raw_Data/
├── 02_Processed_Data/
├── 03_Training_Runs/
├── 04_Model_Artifacts/
├── 05_Reports_For_Team/
├── 06_Colab_Kaggle_Workspace/
└── 99_Archive/
```

Registry sheet:

<https://docs.google.com/spreadsheets/d/1srINZhdV7w1f6AHJ49F6IS81CvzdVtV8LQQ-Fhnw80M/edit>

## Three managed streams

| Stream | Data | Training/run output | Model/artifact |
| --- | --- | --- | --- |
| `cv_yolo` | images, videos, labels, `data.yaml` | YOLO logs, predictions, metrics | `.pt` weights, sample predictions |
| `rl_sumo` | district spec, SUMO generated files, scenarios | rollout traces, traffic metrics | RL policy checkpoint |
| `public_finance` | cost, budget, public-value assumptions | sensitivity results, investment ranking | optimizer config/report |

## Minimum run folder

Each run should have:

```text
run_config.json
metrics.json or metrics.placeholder.json
logs/
artifacts/
reports/
```

Create a local run folder:

```powershell
uv run python scripts/artifacts/prepare_run_dir.py --stream yolo --run-id RUN-YOLO-V0-001
```

Push it to Drive Desktop after training:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py --drive-root "<Data Hub local path>" --apply push-run --stream yolo --run-id RUN-YOLO-V0-001 --source artifacts/runs/yolo/RUN-YOLO-V0-001
```

Without `--apply`, the sync script is a dry run.

## Colab/Kaggle pattern

1. Clone the GitHub repo.
2. Install `requirements-colab.txt`.
3. Mount or attach Google Drive/Kaggle dataset.
4. Read data from Drive Data Hub.
5. Write run outputs back to Drive Data Hub.
6. Update the registry sheet.

## Current limitation

This is a management scaffold. The first real YOLO/RL/optimizer run will teach us the exact
metrics, logs, model files, and reports worth keeping. Until then, the registry rows are examples.
