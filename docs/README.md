# Project Documentation Index

This folder is the canonical documentation surface for the repository. If a future agent or teammate
is unsure where to read first, start here.

## Folder map

```text
docs/
├── 00_TARGETS/            # durable goals and non-negotiable decisions
├── 01_PROJECT_BRIEF/      # product direction and core problem framing
├── 02_ARCHITECTURE/       # accepted system contracts and interfaces
├── 03_COMPETITION/        # competition facts and external challenge context
└── 04_STATUS/             # verified capability, gaps and dependencies
```

Weekly plans, Economics tasks, CS tasks, owners, deadlines, and handoff checklists live in the
Google Drive taskboard. Do not duplicate them as repo docs unless the content is a durable
architecture/contract decision.

## Read by purpose

### Understand the long-term target

1. [Project Target](00_TARGETS/PROJECT_TARGET.md)
2. [Optical Sensor Target](00_TARGETS/OPTICAL_SENSOR_TARGET.md)
3. [Smart Traffic Public Finance brief](01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md)

### Design or change an interface

Start with the accepted [System delivery plan](02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md) for the
unchanged-map, eight-candidate research pilot and module acceptance gates. It records a plan,
not completed implementation. UE art configuration is specified in
[Unreal asset pipeline](02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md).

1. [Simulation backend architecture](02_ARCHITECTURE/SIMULATION_BACKEND_ARCHITECTURE.md)
2. [SUMO-backed render bridge framework](02_ARCHITECTURE/SUMO_RENDER_BRIDGE_FRAMEWORK.md)
3. [Render bridge contracts](02_ARCHITECTURE/RENDER_BRIDGE_CONTRACTS.md)
4. [SUMO-RL system design](02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md)
5. [Observation space v1](02_ARCHITECTURE/OBSERVATION_SPACE_V1.md)
6. [Structured occlusion and sensor-based RL](02_ARCHITECTURE/STRUCTURED_OCCLUSION_AND_SENSOR_RL.md)
7. [Synthetic visual sensor dataset contract](02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md)
8. [Unreal render migration plan](02_ARCHITECTURE/UNREAL_RENDER_MIGRATION_PLAN.md)
9. [Map economic data model](02_ARCHITECTURE/MAP_ECONOMIC_DATA_MODEL.md)
10. [Map-aware QUBO](02_ARCHITECTURE/MAP_AWARE_QUBO.md)
11. [RL/QUBO objective rationale](02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md)
12. [Economic source review](02_ARCHITECTURE/MAP_ECONOMIC_SOURCE_RESEARCH.md)
13. [Retained-ROI travel source review](02_ARCHITECTURE/CURRENT_ROI_TRAVEL_SOURCE_REVIEW.md)
14. [Demand dataset design and reproducible inventory](02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md)

Use the remaining architecture documents for their bounded domain: map intake, Unreal rendering,
multi-agent memory, QUBO coupling, data artifacts and DVC.

### Check what is true now

1. [Implementation Status](04_STATUS/IMPLEMENTATION_STATUS.md)
2. `coordination/tasks/` for task-level evidence and validation commands.
3. Generated manifests/reports for a specific run; do not infer capability from a screenshot alone.

## Documentation ownership

- `00_TARGETS/` owns durable intent, decision boundaries and non-negotiable rules.
- `02_ARCHITECTURE/` owns accepted contracts, schemas, interfaces and implementation design.
- `04_STATUS/` owns repository-wide current capability, blockers and dependency order.
- `coordination/tasks/` owns task-scoped completion evidence. Google Drive owns weekly planning,
  deadlines and team assignment.

Do not state a capability as current merely because it appears in a target or architecture diagram.
Do not put temporary status prose into a target document.

## Cleanup rule

Before adding a new docs folder or a new team-task document, ask:

1. Does an existing folder already own this topic?
2. Will `docs/README.md` need a new reading-order entry?
3. Is this a durable technical decision, or should it live in the Drive taskboard instead?
4. Will `ai_quantum_hvtc doctor` need to know about the new canonical document?

If the answer is “maybe”, prefer adding a file under an existing folder first.
