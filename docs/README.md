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
3. [SUMO-backed render bridge framework](02_ARCHITECTURE/SUMO_RENDER_BRIDGE_FRAMEWORK.md)
4. [Render bridge contracts](02_ARCHITECTURE/RENDER_BRIDGE_CONTRACTS.md)
5. [Godot render architecture](02_ARCHITECTURE/GODOT_RENDER_ARCHITECTURE.md)
6. [Godot bridge refactor plan](02_ARCHITECTURE/GODOT_BRIDGE_REFACTOR_PLAN.md)
7. [Map ROI auto-zoning pipeline](02_ARCHITECTURE/MAP_ROI_AUTO_ZONING_PIPELINE.md)
8. [SUMO-RL system design](02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md)
9. [Multi-agent RL with temporal memory](02_ARCHITECTURE/MULTI_AGENT_RL_MEMORY_TRAINING.md)
10. [Observation space v1](02_ARCHITECTURE/OBSERVATION_SPACE_V1.md)
11. [Structured occlusion and sensor-based RL](02_ARCHITECTURE/STRUCTURED_OCCLUSION_AND_SENSOR_RL.md)
12. [Public-service district environment spec](02_ARCHITECTURE/PUBLIC_SERVICE_DISTRICT_ENVIRONMENT_SPEC.md)
13. [QUBO and RL joint optimization](02_ARCHITECTURE/QUBO_RL_JOINT_OPTIMIZATION.md)
14. [Data and artifact workflow](02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md)
15. [DVC data management](02_ARCHITECTURE/DVC_DATA_MANAGEMENT.md)
16. [Synthetic visual sensor dataset contract](02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md)
17. [Godot synthetic CV smoke export](02_ARCHITECTURE/GODOT_SYNTHETIC_CV_SMOKE.md)

## Current architecture stance

- SUMO/SUMO-RL remains the official traffic simulation and RL environment.
- The SUMO render bridge is the contract layer between traffic simulation and any renderer.
- The current target is the full Quận 7 OSM/SUMO network or a reviewed ROI of roughly 100 signals;
  the package fixture is CI-only.
- SUMO backend and the SUMO-to-Godot bridge run today, while large-ROI demand, signal programs and
  baseline strength remain active work.
- Godot is the current reference renderer/sensor-data generator, not the main traffic simulator.
- YOLO/CV is an optional sensor layer over rendered frames, not a direct reader of hidden SUMO state;
  geometry-based optical visibility can support the first camera-partial-observation RL experiments.
- Multi-agent training uses a shared policy with optional frame stack or recurrent memory; it does
  not create one independently trained policy per signal.
- Public-finance optimization chooses which intersections to invest in under a budget **after**
  baseline/RL evaluation has produced scenario metrics. Before evaluation, the team may only define
  candidate sets and experiment scope.
- Baseline/report work can proceed before reward is finalized; reward/public-value definitions need
  CS and Economics alignment before RL claims.
- Structured occlusion is modeled at the optical observation boundary. Vehicle dimensions and camera
  calibration are prerequisites for physical occlusion claims; detector-specific YOLO errors are a
  later layer.
- Generated datasets, training runs, checkpoints, videos, and local simulator outputs stay out of Git
  and should be tracked with DVC when they must be reproducible.

## Cleanup rule

Before adding a new docs folder or a new team-task document, ask:

1. Does an existing folder already own this topic?
2. Will `docs/README.md` need a new reading-order entry?
3. Is this a durable technical decision, or should it live in the Drive taskboard instead?
4. Will `ai_quantum_hvtc doctor` need to know about the new canonical document?

If the answer is “maybe”, prefer adding a file under an existing folder first.
