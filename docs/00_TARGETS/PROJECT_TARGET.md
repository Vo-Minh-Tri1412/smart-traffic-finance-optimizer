# Project Target

This is the durable product and research direction for the project. It describes what the team is
trying to prove and build; it is not a progress report or task list.

## North star

Evaluate traffic-control and investment choices for Quận 7 or a reviewed large ROI using one
reproducible evidence chain:

```text
prepared map + demand scenarios
  -> SUMO traffic dynamics and legal signal control
  -> observed traffic state and uncertainty
  -> controller evaluation across scenarios and seeds
  -> public-value and budget decisions
```

The desired outcome is not a visually impressive city alone. It is a defensible comparison of
control and investment choices under explicit traffic, sensing, safety and public-value
assumptions.

## Durable decisions

- SUMO/SUMO-RL owns traffic dynamics, signal legality, routes, queues and operational metrics.
- Unreal is the renderer, replay client and planned synthetic sensor-data producer; it does not replace SUMO
  as the traffic simulator.
- The renderer consumes the same prepared SUMO map and traces as the simulation. It must not invent
  a separate toy road network for production claims.
- A shared multi-agent policy is the intended large-ROI control direction. One independent policy
  per signal is not the target architecture.
- Public-finance optimization selects long-horizon upgrades under a budget. RL performs
  short-horizon legal signal control. They are evaluated together but are not one monolithic model.
- Camera-based claims must use an observation boundary. Hidden SUMO truth may create labels, reward
  and evaluation metrics, but may not be passed to a camera-based policy as an observation.
- Generated datasets, training runs, models, screenshots and local simulator outputs are artifacts,
  not source code. Their provenance belongs in manifests and the implementation status record.

## Evidence required for final claims

- A reviewed map/ROI, demand scenarios, signal scope and multiple seeds.
- Fixed-time and rule-based baselines on the same scenarios.
- A declared observation mode: oracle, geometry visibility, detector or mixed.
- Safety, throughput, delay, queue, spillback, emergency, transit, freight and fairness metrics as
  applicable to the approved evaluation profile.
- Explicit public-value/cost assumptions for budget claims.

## Reading boundaries

- Read [Implementation Status](../04_STATUS/IMPLEMENTATION_STATUS.md) for what works now, active
  gaps and validation evidence.
- Read [Optical Sensor Target](OPTICAL_SENSOR_TARGET.md) for the camera-based observation target.
- Read `docs/02_ARCHITECTURE/` for current accepted interfaces and implementation contracts.

Change this document only for a durable product or research decision. Do not use it to record a
completed task, a local artifact path, or a temporary workaround.
