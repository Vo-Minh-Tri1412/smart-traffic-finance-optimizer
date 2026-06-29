# Project Documentation Index

This folder is the canonical documentation surface for the repository. If a future agent or teammate
is unsure where to read first, start here.

## Folder map

```text
docs/
├── 01_PROJECT_BRIEF/      # product direction and core problem framing
├── 02_ARCHITECTURE/       # system design, simulation, data, sensors, rendering
├── 03_COMPETITION/        # competition facts and external challenge context
├── 04_WEEKLY_PLANS/       # weekly planning snapshots
└── 05_TEAM_GUIDES/        # CS/economics handoff guides in plain language
```

There should be only one weekly-plan folder: `04_WEEKLY_PLANS/`. Empty duplicate planning folders
should not be recreated.

## Recommended reading order

1. [Smart Traffic Public Finance brief](01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md)
2. [SUMO-RL system design](02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md)
3. [Public-service district environment spec](02_ARCHITECTURE/PUBLIC_SERVICE_DISTRICT_ENVIRONMENT_SPEC.md)
4. [Observation space v1](02_ARCHITECTURE/OBSERVATION_SPACE_V1.md)
5. [Data and artifact workflow](02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md)
6. [Synthetic visual sensor dataset contract](02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md)
7. [Godot synthetic CV smoke export](02_ARCHITECTURE/GODOT_SYNTHETIC_CV_SMOKE.md)
8. [Economics plain-language guide](05_TEAM_GUIDES/ECONOMICS_PLAIN_LANGUAGE_GUIDE.md)
9. [Week 1 plan](04_WEEKLY_PLANS/WEEK1_PLAN.md)

## Current architecture stance

- SUMO/SUMO-RL remains the official traffic simulation and RL environment.
- Godot is a renderer/sensor-data generator, not the main traffic simulator.
- YOLO/CV is a sensor layer, not the source of simulator ground truth.
- Public-finance optimization chooses which intersections to invest in under a budget.
- Generated datasets, training runs, checkpoints, videos, and local simulator outputs stay out of Git.

## Cleanup rule

Before adding a new docs folder, ask:

1. Does an existing folder already own this topic?
2. Will `docs/README.md` need a new reading-order entry?
3. Will `ai_quantum_hvtc doctor` need to know about the new canonical document?

If the answer is “maybe”, prefer adding a file under an existing folder first.
