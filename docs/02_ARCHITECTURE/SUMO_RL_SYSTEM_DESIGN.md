# SUMO-RL System Design

## Status and target

SUMO is the official traffic simulator and SUMO-RL is the official signal-control environment.
The current project target is the full Quận 7 OSM/SUMO map or a reviewed ROI of roughly 100
signalized intersections. The small package fixture and the one-intersection SUMO smoke test remain
CI/runtime checks only; they are not the research environment or final demo claim.

The latest map/render work uses the SUMO net, semantic overlay, DVC/Drive artifacts and Godot LOD
replay path. A renderer must not replace SUMO traffic dynamics.

## End-to-end architecture

```text
Quận 7 SUMO net + semantic overlay + demand scenarios
        |
        v
SUMO / SUMO-RL traffic dynamics and signal phases
        |
        +--> fixed-time baseline
        +--> rule-based baseline
        +--> shared multi-agent RL policy
        |
        +--> vehicle/signal/event traces
                    |
                    v
      calibrated optical visibility sensor (optional at first)
                    |
                    v
      lane features + uncertainty + temporal memory
                    |
                    v
      RL observations and policy actions
        |
        v
metrics -> public-value scoring -> QUBO/budget allocation
```

## Environment interfaces

SUMO-RL supports Gymnasium and PettingZoo interfaces. The project training entrypoint uses the
PettingZoo parallel interface for multi-agent mode, converts it to a Stable-Baselines vector
environment through SuperSuit, and applies one shared policy across signal agents.

The current train scaffold supports:

- `multi_agent` shared-policy mode for all traffic signals in the loaded SUMO network;
- `single_agent` mode only as a debugging fallback;
- plain PPO, vector frame stacking, or RecurrentPPO LSTM memory;
- the existing reward callback and route/export contracts as templates;
- configurable parallel environment copies for cloud training.

The scaffold does not claim that the final project observation adapter, reward profile, flow
calibration or hard safety constraints are approved.

## Observation, action and memory

The canonical observation contract is [Observation Space v1](OBSERVATION_SPACE_V1.md). It is a
per-signal local observation, not a single vector containing the whole district.

Every agent should observe:

- local incoming approach pressure and waiting time;
- approaching vehicles and downstream capacity risk;
- current signal phase and timing safety;
- emergency, bus and truck pressure;
- time/scenario context;
- when camera-based sensing is enabled, estimated counts, confidence, visible fraction and
  time-since-last-observed.

Memory is part of the policy contract for partial observation:

1. memoryless PPO baseline;
2. 4–8 snapshots of compact lane features;
3. RecurrentPPO/LSTM shared policy;
4. graph/neighborhood message passing or centralized training if network coordination remains weak.

Raw RGB frame stacking is not the first signal-control target. Camera frames should first be reduced
to a fixed-size sensor observation by a geometry-based visibility model, tracker and optional YOLO
detector.

## Structured optical occlusion

The RL policy may be trained before YOLO exists. The first sensor can use deterministic or randomized
3D visibility:

```text
camera height/pitch/FOV
  + SUMO x/y/angle and lane geometry
  + vehicle length/width/height
  -> projected boxes and depth ordering
  -> visible fraction and lane-level observation
```

The traffic state in SUMO is not corrupted. Only the observation is partially observed. This permits
training under bus/truck occlusion without inventing detector-specific errors. Later, YOLO errors,
weather, blur and class confusion may be calibrated and inserted after the visibility model. See
[Structured Occlusion and Sensor-Based RL](STRUCTURED_OCCLUSION_AND_SENSOR_RL.md).

## Action and reward

The action remains a legal signal-phase choice supplied by SUMO-RL. The environment must enforce
yellow/minimum-green safety timing. A policy must not be credited for illegal phase changes.

The current reward callback remains a template until the reward profile is approved. The initial
traffic objective may use waiting time, queue pressure and switching penalties. Final evaluation must
also report emergency, bus passenger, truck/logistics, fairness and spillback effects.

The RL reward and public-value score are related but not identical:

```text
RL: learn safe operational signal control
finance: choose where investment creates public value under budget
```

## Scope and scaling

The full Quận 7/ROI network is the target. The fixture at
`tests/fixtures/specs/toy_public_district_v1.json` is a reproducible test input only.

At approximately 100–160 signals, the project should use:

- shared policy parameters rather than one model per signal;
- fixed-size local observations and adjacency/neighborhood summaries;
- scenario and seed randomization;
- centralized training/decentralized execution or graph policies when local policies cannot
  coordinate;
- LOD and camera-window rendering so Godot does not instantiate the whole map unnecessarily.

The number of signals alone is not evidence of a stable policy. Claims require network-level metrics,
per-signal metrics, unseen demand scenarios and multiple seeds.

## Required baselines

Every RL claim must be compared with:

- fixed-time control;
- rule-based adaptive control;
- the same SUMO network, demand scenarios, seeds and signal scope.

For camera-based runs, also compare clean geometry visibility against structured occlusion and
optional detector-noise conditions.

## QUBO/RL relationship

The long-horizon investment decision and short-horizon signal policy should be coupled through a
bilevel or alternating workflow. QUBO selects an upgrade mask under budget; RL is evaluated or
fine-tuned for that mask. QUBO coefficients must eventually include measured corridor interactions,
not only independent candidate values. See [QUBO and RL Joint Optimization](QUBO_RL_JOINT_OPTIMIZATION.md).

## Outputs

Required outputs remain:

- `simulation_summary`: scenario, controller, signal scope, total waiting time, throughput and queue
  statistics;
- `sensor_summary`: camera/visibility configuration, observation error, occlusion rate and tracker
  continuity;
- `public_finance_summary`: value-of-time, emergency, bus and logistics effects with caveats;
- `budget_priority`: candidate/mask, cost assumption, public value and robustness rank;
- `sensitivity_summary`: changed demand, visibility, reward or cost assumption and decision impact;
- `training_manifest`: agent mode, memory mode, seeds, scenario, checkpoint and environment contract.

## Current limitations

- SUMO runtime and existing-net replay are operational, but full Quận 7/ROI multi-agent training
  still needs cloud-scale validation.
- Reward and demand/flow calibration remain templates until approved by the project owners.
- Current Godot sensor smoke output is not yet a production depth/instance visibility pass.
- Vehicle height and road elevation are not yet first-class fields in the SUMO/domain/trace contract.
- A trained policy, YOLO model and public-finance assumptions must not be claimed before their
  artifacts and evaluation reports exist.
