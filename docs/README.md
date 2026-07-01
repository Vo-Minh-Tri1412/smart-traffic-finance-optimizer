# Project Documentation Index

This folder is the canonical documentation surface for the repository. If a future agent or teammate
is unsure where to read first, start here.

## Folder map

```text
docs/
├── 01_PROJECT_BRIEF/      # product direction and core problem framing
├── 02_ARCHITECTURE/       # system design, simulation, data, sensors, rendering
└── 03_COMPETITION/        # competition facts and external challenge context
```

Weekly plans, Economics tasks, CS tasks, owners, deadlines, and handoff checklists live in the
Google Drive taskboard. Do not duplicate them as repo docs unless the content is a durable
architecture/contract decision.

## Recommended reading order

0. Google Drive: `00_Master_Project_Brief_Smart_Traffic_Public_Finance` for the full team-facing
   summary.
1. [Smart Traffic Public Finance brief](01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md)
2. [Simulation backend architecture](02_ARCHITECTURE/SIMULATION_BACKEND_ARCHITECTURE.md)
3. [Godot render architecture](02_ARCHITECTURE/GODOT_RENDER_ARCHITECTURE.md)
4. [SUMO-RL system design](02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md)
5. [Public-service district environment spec](02_ARCHITECTURE/PUBLIC_SERVICE_DISTRICT_ENVIRONMENT_SPEC.md)
6. [Observation space v1](02_ARCHITECTURE/OBSERVATION_SPACE_V1.md)
7. [Data and artifact workflow](02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md)
8. [DVC data management](02_ARCHITECTURE/DVC_DATA_MANAGEMENT.md)
9. [Synthetic visual sensor dataset contract](02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md)
10. [Godot synthetic CV smoke export](02_ARCHITECTURE/GODOT_SYNTHETIC_CV_SMOKE.md)

## Current architecture stance

- SUMO/SUMO-RL remains the official traffic simulation and RL environment.
- SUMO backend runs today, but map realism, traffic-light programs, and baseline strength are still
  active work.
- Godot is a renderer/sensor-data generator, not the main traffic simulator.
- YOLO/CV is a sensor layer over rendered frames, not a direct reader of hidden SUMO state.
- Public-finance optimization chooses which intersections to invest in under a budget **after**
  baseline/RL evaluation has produced scenario metrics. Before evaluation, the team may only define
  candidate sets and experiment scope.
- Baseline/report work can proceed before reward is finalized; reward/public-value definitions need
  CS and Economics alignment before RL claims.
- Generated datasets, training runs, checkpoints, videos, and local simulator outputs stay out of Git
  and should be tracked with DVC when they must be reproducible.

## Cleanup rule

Before adding a new docs folder or a new team-task document, ask:

1. Does an existing folder already own this topic?
2. Will `docs/README.md` need a new reading-order entry?
3. Is this a durable technical decision, or should it live in the Drive taskboard instead?
4. Will `ai_quantum_hvtc doctor` need to know about the new canonical document?

If the answer is “maybe”, prefer adding a file under an existing folder first.
