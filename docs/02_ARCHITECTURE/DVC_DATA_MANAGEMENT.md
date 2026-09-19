# DVC data management

This project uses **Git for code and small metadata**, **DVC for data/model versioning**, and
**Google Drive Desktop for physical storage and team sync**.

The goal is to avoid `final_v2_really_final` data folders while still keeping large OSM, SUMO,
trace, CV, and model artifacts out of Git.

## Storage roles

```text
Git
  -> source code
  -> docs
  -> task manifests
  -> small config/examples
  -> .dvc metadata files

DVC
  -> checksums and version pointers for large artifacts
  -> push/pull against the configured remote

Google Drive Desktop
  -> synced storage backing the DVC remote
  -> human-readable reports and team handoffs
```

## Configured remote

Default DVC remote:

```text
drive_desktop -> D:\AIQ_HVTC_DVC_STORE
```

On this machine, `D:\AIQ_HVTC_DVC_STORE` is a Windows junction pointing to:

```text
G:\My Drive\AI Quantum HVTC — Team Workspace\02_CS_Workspace\00_Data_Management\00_DVC_Store
```

The junction exists because the Google Drive path contains a Unicode dash that caused this DVC
installation to fail when writing config. The ASCII junction keeps DVC stable while Drive Desktop
still syncs the actual storage folder.

Collaborators may need to override the remote locally:

```powershell
dvc remote modify --local drive_desktop url "<their local Drive Desktop path>\00_DVC_Store"
```

Do not hand-edit files inside `00_DVC_Store`. It is machine-managed DVC object storage.

## Current tracked artifacts

The current DVC-tracked map seed is:

```text
simulation_projects/map_intake/01_raw_sources/district7_osm_seed_20260702.dvc
simulation_projects/map_intake/02_prepared_sources/district7_osm_seed_20260702.dvc
```

These point to:

- raw District 7 OSM seed and Overpass query;
- prepared SUMO `.net.xml`, random-trip smoke route files, and smoke outputs.

This seed is the current Quận 7 map-intake source for infrastructure and ROI work. The reviewed
full map or ROI boundary, demand calibration and signal-control scope must still be recorded in the
project manifest before final claims.

## Normal commands

Check data status:

```powershell
dvc status
```

Download DVC-tracked data from Drive Desktop remote:

```powershell
dvc pull
```

Push newly tracked data to Drive Desktop remote:

```powershell
dvc push --no-run-cache
```

Use `--no-run-cache` because this project currently tracks data artifacts directly and does not yet
use DVC pipeline stages. It also avoids unnecessary run-cache writes on Windows.

## What should be DVC-tracked

Use DVC for large or generated artifacts:

- raw OSM extracts;
- SUMO `.net.xml`, `.rou.xml`, `.sumocfg`, tripinfo, edge/lane outputs, FCD traces;
- Unreal-generated frame datasets and YOLO labels;
- training run outputs from Colab/Kaggle/local;
- model checkpoints and exported weights;
- large videos or rendered demo captures.

Keep in Git:

- source code;
- tests;
- tiny fixtures;
- configs;
- data/catalog templates;
- `.dvc` pointer files;
- QA/review notes.

Keep in Google Drive human-readable folders:

- reports for Economics;
- model/result handoff summaries;
- slides/docs for teammates;
- raw files not yet accepted into DVC.

## Recommended Drive layout

Use the existing Drive folder:

```text
02_CS_Workspace/
└── 00_Data_Management/
    ├── 00_DVC_Store/          # DVC remote, do not edit manually
    ├── 00_Registry/           # dataset/run/model registry files
    ├── 01_Raw_Data/           # human-staged raw files before/around DVC tracking
    ├── 02_Processed_Data/     # processed exports for review
    ├── 03_Training_Runs/      # cloud/local run outputs
    ├── 04_Model_Artifacts/    # model weights/checkpoints
    ├── 05_Reports_For_Team/   # readable handoffs
    ├── 06_Colab_Kaggle_.../   # cloud runtime helpers
    └── 99_Archive/
```

## Rule of thumb

If a file is large, generated, or needed to reproduce a model/result, it probably belongs in DVC.
If a teammate needs to read it directly, also export a small summary/report into Drive.
