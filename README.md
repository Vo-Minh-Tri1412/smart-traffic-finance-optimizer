# Smart Traffic Public Finance Optimizer

AI Quantum HVTC challenge project for **smart traffic control** and **public-finance
investment prioritization**.

The project studies a practical policy question:

> If a city has limited public money and cannot upgrade every traffic light, which intersections
> should receive AI traffic-control investment first, and why?

The system combines traffic simulation, reinforcement learning, optional camera-based sensing,
and public-finance optimization. It does not treat "AI traffic lights" as the final answer by
itself. The final decision is a budget allocation problem: choose where to invest so that the
whole district receives the highest public value under cost, fairness, and operational constraints.

Primary competition track: **AI for Public Policy and Public Finance**.

## Abstract

Urban traffic-light upgrades are public investments. A technically better signal policy is not
automatically a better public policy if it improves one corridor while pushing congestion into a
hospital route, school zone, residential area, or logistics corridor. This project builds a
spec-driven district simulation in which candidate intersections can be controlled by AI while
non-upgraded intersections remain under fixed-time or rule-based control. The resulting traffic
metrics are converted into a public-value score and passed to a budget optimizer that chooses the
investment subset with the best expected social value.

The proposed architecture has three coordinated model layers, plus an optional visual-rendering layer
for sensor realism:

1. **Sensor / observation layer**: ground-truth simulation sensors for training, with optional
   YOLO/CV camera-like sensing as a deployment or robustness extension.
2. **Traffic-control layer**: SUMO/SUMO-RL environment with fixed-time, rule-based, and RL
   controllers.
3. **Public-finance optimizer layer**: budget-constrained selection of intersections using exact,
   greedy, robust, and future QUBO/quantum-compatible formulations.
4. **Synthetic visual sensor layer**: a Godot 3D render workspace that will turn SUMO/SUMO-RL
   vehicle trajectories into camera-like frames, YOLO labels, weather/noise variants, and demo
   video.

The current repository is a technical scaffold. It contains the simulation architecture, SUMO
adapter scaffold, frontend contracts, Drive-backed data/artifact workflow, and notebook entrypoints.
It does **not** yet contain a final trained RL policy, final YOLO model, or approved real-world
finance assumptions.

## Research framing

### Problem

Cities face limited budgets. Upgrading every intersection with AI signal control may be impossible
or unjustified. A naive approach would score each intersection separately and fund the top-ranked
ones. That is risky because traffic lights interact:

- clearing one upstream intersection can overload a downstream bottleneck;
- prioritizing a logistics corridor can increase waiting time in residential streets;
- reducing average waiting time can still harm buses or emergency vehicles;
- two AI-controlled intersections may create more value together than either does alone, or the
  second upgrade may add almost no value after the first.

Therefore, the investment decision is a **networked, budget-constrained policy problem**, not a
single-intersection ranking problem.

### Main question

```text
Given a district, scenarios, candidate intersections, and budget B:
which subset of intersections should receive AI traffic-light control
so that public value is maximized across the whole network?
```

### Core hypothesis

An AI traffic controller should be evaluated not only by traffic metrics such as waiting time, but
also by public-finance metrics such as cost, social value, emergency delay, bus passenger impact,
logistics delay, and fairness across areas. The system should make the trade-off explicit instead
of claiming that one trained policy is universally optimal.

## System architecture

```text
                external or simulated observations
                             |
                             v
                 +-------------------------+
                 |  Sensor / observation   |
                 |  - ground truth sensor  |
                 |  - optional YOLO sensor |
                 +-----------+-------------+
                             |
                             v
                 +-------------------------+
                 |  SUMO / SUMO-RL world   |
                 |  district, flows, TLS   |
                 +-----------+-------------+
                             |
                             v
                 +-------------------------+
                 |  Traffic controllers    |
                 |  fixed / rule / RL      |
                 +-----------+-------------+
                             |
                             v
                 +-------------------------+
                 |  Metrics and traces     |
                 |  wait, queue, delay     |
                 +-----------+-------------+
                             |
                             v
                 +-------------------------+
                 |  Public-value scoring   |
                 |  benefit - cost - risk  |
                 +-----------+-------------+
                             |
                             v
                 +-------------------------+
                 |  Investment optimizer   |
                 |  exact / greedy / QUBO  |
                 +-------------------------+
```

Future visual-sensor path:

```text
SUMO/SUMO-RL world
        |
        v
vehicle trajectory + signal trace
        |
        v
Godot 3D synthetic camera renderer
        |
        +--> camera frames/video
        +--> YOLO labels
        +--> render manifest
        |
        v
YOLO sensor model
        |
        v
vehicle counts/type estimates + sensor-error report
```

### Why CV is not the core data source in simulation

Inside a simulation, the system already knows each vehicle's ID, type, position, lane, route, and
waiting time. Training a CV model to re-detect those synthetic vehicles from UI assets would be
mostly redundant if the RL controller can read the simulator state directly.

So CV is treated as a **sensor layer**, not as the main source of truth:

- During simulation training, RL may use ground-truth simulator observations for stability.
- For deployment-style demos, YOLO can estimate vehicle counts/types from camera or video frames.
- For robustness testing, a synthetic camera view may be compared against ground truth to measure
  sensor error.

This keeps the architecture honest: CV is useful when the system does not have direct access to
perfect simulator state, not when it merely re-detects UI icons that the simulator generated.

### Godot 3D synthetic visual sensor layer

The preferred project-specific CV path is not to train YOLO on an unrelated public traffic-camera
dataset and then ask it to understand a synthetic mini-city. That creates a domain mismatch:

```text
real street-camera images != rendered simulation district images
```

Instead, the project can add **Godot 3D as a renderer**, not as the main simulator. SUMO/SUMO-RL
remains responsible for traffic dynamics, vehicle trajectories, signal phases, RL training, metrics,
and public-finance evaluation. Godot receives exported simulation state and renders camera-like
frames from the same district:

```text
district_spec.json
  -> SUMO/SUMO-RL simulation
  -> vehicle trajectories + signal states
  -> Godot 3D camera renderer
  -> synthetic frames/video + YOLO labels
  -> YOLO sensor model
  -> sensor estimates compared with SUMO ground truth
```

This makes the camera layer both visually stronger and scientifically cleaner: YOLO sees only images,
while SUMO provides ground truth for measuring sensor error. The RL controller does not need to train
from pixels in v1; it can train from SUMO-RL state observations while the Godot/YOLO layer supports
deployment-style sensing, robustness checks, and a more convincing demo.

Godot 3D is scoped as a lightweight scene-first synthetic renderer:

- low-poly public-service district, not photorealistic open-world simulation;
- reusable Godot scenes for world objects, vehicles, cameras, traffic lights, and UI panels;
- fixed traffic cameras near hospitals, schools, industrial gates, bottlenecks, and arterial roads;
- vehicle assets for motorbike, car, bus, truck, ambulance, and worker shuttle;
- day/night/rain/noise variants for domain randomization;
- automatic YOLO label export from known object positions;
- generated frames, videos, labels, and model artifacts stored in Google Drive, not Git.

Godot must not silently replace SUMO-RL. It is a visual/sensor layer that consumes simulation traces.
The `render/` folder is the Godot project. It is organized as a scene-first app with `scenes/`,
`scripts/`, `resources/`, `imported_assets/`, and ignored local `outputs/`. If the project uses
Godot AI MCP tooling, that tooling is an implementation accelerator only; the repository should
remain understandable and runnable without requiring an agent-specific MCP session.

## The three model layers

### 1. Sensor / CV model

Purpose:

- Estimate traffic state from image or video when direct ground truth is unavailable.
- Provide vehicle counts and vehicle-type counts as possible inputs to the observation layer.
- Evaluate robustness when sensor estimates are noisy or incomplete.

Possible inputs:

- Godot-rendered synthetic traffic-camera frames generated from SUMO/SUMO-RL trajectories;
- camera-like frames rendered from simulation for pipeline testing;
- optional public traffic images/videos for future external validation;
- future real-world camera clips if permissions are clear.

Possible outputs:

- vehicle count by class;
- queue-length proxy;
- density estimate;
- optional confidence/error report versus simulation ground truth.

Current status:

- YOLO workflow is scaffolded.
- `requirements-colab.txt` includes `ultralytics` and OpenCV for cloud training.
- Local default `uv sync` does not install YOLO yet.
- No real CV dataset or trained YOLO model is claimed.
- Godot 3D render workspace structure exists under `render/`, but the final district replay scene
  and dataset exporter are not implemented yet.

### 2. SUMO-RL traffic-control model

Purpose:

- Compare fixed-time, rule-based, and RL traffic-light control.
- Evaluate how different control policies affect the district under several scenarios.
- Export metrics and traces for the finance layer and future UI.

Main backend:

- SUMO / SUMO-RL is the official traffic environment.
- A reference graph engine exists for fast logic tests, but it is not the main high-fidelity
  environment.

Important implementation requirements:

- stable SUMO map/network;
- controlled traffic-light IDs and phases;
- meaningful origin-destination flows;
- observation space that matches the policy question;
- reward profiles that can evolve from technical reward to public-value reward;
- fixed-time and rule-based baselines;
- metric export for public-finance scoring.

Current status:

- SUMO runtime and SUMO-RL imports are verified locally.
- SUMO adapter scaffold exists.
- Final project-specific SUMO-RL training environment and trained policy are not complete yet.

### 3. Public-finance investment optimizer

Purpose:

- Decide which intersections should receive AI control when budget is limited.
- Account for network interactions between upgraded and non-upgraded intersections.
- Compare classical and future quantum-compatible optimization strategies.

Decision variable:

```text
x_i = 1 if intersection i receives AI traffic-light upgrade
x_i = 0 otherwise
```

Objective sketch:

```text
maximize public_value(subset)
subject to total_cost(subset) <= budget
```

Public value may include:

- time saved;
- bus passenger delay reduction;
- emergency vehicle delay reduction;
- logistics delay reduction;
- fairness or residential-area penalty;
- hardware and maintenance cost;
- deployment risk penalty.

Optimization approaches:

- exact subset search for small candidate sets;
- greedy benefit-cost baseline;
- robust selection across multiple traffic scenarios;
- QUBO export for later QAOA/D-Wave style quantum experiments.

Current status:

- exact/greedy/QUBO scaffolding exists.
- It still needs real traffic metrics and Economics-approved finance assumptions.

## Data and artifact workflow

Code and data are intentionally separated:

```text
local code -> GitHub -> Colab/Kaggle
local or Drive Desktop data -> preprocess -> Google Drive Data Hub
Colab/Kaggle -> train/evaluate -> Google Drive Data Hub -> local via Drive Desktop
```

GitHub stores:

- source code;
- tests;
- configuration examples;
- small district specs;
- notebook skeletons;
- documentation and governance.

Google Drive stores:

- raw data;
- processed data;
- training runs;
- model artifacts;
- metrics;
- logs;
- reports;
- handoffs for non-code teammates.

CS Data Hub:

- Drive folder: `02_CS_Workspace/00_Data_Management`
- Registry sheet: `00_Data_Model_Run_Registry`

Local scripts are organized by responsibility:

```text
scripts/
├── admin/       # governance and task validation
├── artifacts/   # run folder creation
├── cloud/       # Drive Desktop / cloud handoff helpers
├── data/        # dataset preparation helpers
└── smoke/       # smoke tests
```

Notebook entrypoints:

```text
notebooks/
├── 00_colab_kaggle_setup.ipynb
├── 01_yolo_train_colab.ipynb
├── 02_rl_train_sumo_colab.ipynb
└── 03_export_artifacts_to_drive.ipynb
```

Notebooks are not the product. They are cloud-runtime entrypoints for training and artifact export.
Core logic should remain in package code and scripts.

## Repository layout

```text
ai_quantum_hvtc/
├── core/
├── simulation/
│   ├── domain/
│   ├── specs/
│   ├── routing/
│   ├── controllers/
│   ├── engines/
│   │   ├── reference/
│   │   └── sumo/
│   └── metrics/
├── sensors/
├── rl/
├── public_finance/
├── policy/
├── pipeline/
└── reports/
```

Supporting folders:

```text
configs/                  # local/cloud config examples
data/catalog/             # dataset/run/model-card templates
docs/README.md            # canonical documentation index and reading order
docs/01_PROJECT_BRIEF/    # product direction and public-finance problem framing
docs/02_ARCHITECTURE/     # SUMO-RL, data workflow, sensors, Godot renderer contracts
docs/03_COMPETITION/      # AI Quantum HVTC competition facts
docs/04_WEEKLY_PLANS/     # weekly planning snapshots
docs/05_TEAM_GUIDES/      # CS/economics collaboration guides
frontend/                 # future React contract and mock-data layer
notebooks/                # Colab/Kaggle entrypoints
render/                   # Godot scene-first visual replay and synthetic sensor app
simulation_projects/      # district specs and generated-output placeholders
tests/                    # unit, integration, smoke, fixtures
```

## Quick start

Ensure Python 3.12 and `uv` are installed.

```powershell
uv sync --frozen
uv run python -m ai_quantum_hvtc doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy ai_quantum_hvtc scripts
uv run pytest
```

SUMO is an external runtime. Install it separately and ensure these are available:

- `sumo`
- `sumo-gui`
- `SUMO_HOME`

Local development uses `pyproject.toml` and `uv.lock`. The cloud notebook convenience file is
`requirements-colab.txt`.

## Useful commands

Validate the project scaffold:

```powershell
uv run python -m ai_quantum_hvtc doctor
uv run python -m ai_quantum_hvtc simulate validate --spec simulation_projects/minh_khai_district_v1/specs/district_spec.json
```

Run the current SUMO backend:

```powershell
uv run python -m ai_quantum_hvtc simulate run `
  --spec simulation_projects/minh_khai_district_v1/specs/district_spec.json `
  --scenario normal_weekday `
  --controller fixed_time `
  --out simulation_projects/minh_khai_district_v1/outputs/run_normal_fixed_time.json `
  --trace-out simulation_projects/minh_khai_district_v1/outputs/run_normal_fixed_time.trace.jsonl `
  --sumo-work-dir simulation_projects/minh_khai_district_v1/sumo_generated
```

The `reference` engine is still available only as a lightweight validation backend for fast schema
and finance-pipeline checks. Do not use it for final simulation claims or the main demo.

Prepare a local training-run artifact folder:

```powershell
uv run python scripts/artifacts/prepare_run_dir.py --stream yolo --run-id RUN-YOLO-V0-001
```

Check Google Drive Desktop Data Hub discovery:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py --drive-root "<local Data Hub path>" status
```

Dry-run a run-folder push to Drive:

```powershell
uv run python scripts/cloud/drive_desktop_sync.py `
  --drive-root "<local Data Hub path>" `
  push-run `
  --stream yolo `
  --run-id RUN-YOLO-V0-001 `
  --source artifacts/runs/yolo/RUN-YOLO-V0-001
```

Add `--apply` only when the copy plan is correct.

## Team workflow and governance

Read `AGENTS.md` before changing files. Every repository write task needs a manifest in
`coordination/tasks/` and must pass:

```powershell
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

High-level ownership:

- CS owns simulation, training scripts, data/artifact workflow, and implementation.
- Economics owns public-value logic, scenario meaning, cost assumptions, and policy narrative.
- Both sides must agree on reward/public-value definitions before claiming a policy conclusion.

## What is intentionally not claimed yet

The current scaffold does not claim:

- a final trained RL policy;
- a final trained YOLO detector;
- an implemented Godot 3D renderer or generated synthetic camera dataset;
- a completed Godot district scene or asset library;
- real-world causal traffic savings;
- real-world budget savings;
- validated finance assumptions;
- production-ready deployment.

It does claim:

- a disciplined architecture for connecting traffic AI to public-finance decisions;
- a reproducible repository structure;
- a Drive-backed data/model/output workflow;
- an honest separation between simulation ground truth, Godot-rendered camera views, and YOLO
  sensing;
- a clear path toward classical and quantum-compatible investment optimization.

## Scope guardrails

- SUMO-RL remains the official traffic environment.
- Do not replace SUMO-RL with a custom simulator as the main environment without a recorded
  integrator decision.
- Computer vision / YOLO is a sensor-layer extension, not the core data source inside simulation.
- Do not use unrelated public camera datasets as proof that YOLO understands the synthetic district.
- Do not use flat UI icons as proof of a real CV model; prefer a controlled Godot 3D synthetic
  camera layer if CV becomes part of the demo.
- Do not let Godot replace SUMO-RL as the traffic/RL environment without a new integrator decision.
- Do not claim real-world causal savings from simulation alone.
- Compare RL against fixed-time and rule-based baselines.
- Public-finance assumptions must be sourced, estimated, or clearly marked as placeholders.
