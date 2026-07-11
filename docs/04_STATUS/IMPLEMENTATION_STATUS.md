# Implementation Status

This is the repository-level status record. It summarizes verified capability and important gaps;
individual task evidence remains in `coordination/tasks/` and generated run artifacts remain outside
Git.

## Confirmed foundations

- SUMO is the traffic simulator and the bridge/replay path consumes prepared net and trace artifacts.
- The Godot project has scene-native road, vehicle, zone, traffic-light and camera scaffolding.
- The training scaffold supports shared multi-agent mode, a frame-stack baseline and optional
  RecurrentPPO mode. This is scaffolding, not a validated Quận 7 policy claim.
- Synthetic dataset layout, camera and label catalogs, a sensor dataset writer and smoke export path
  exist.
- Canonical vehicle height/ground-clearance profiles, `vehicle_geometry_catalog.v1`, and a SUMO
  `geometry_sensor` profile now exist. The profile uses a 0.2-second simulation step, one-second FCD
  capture and 0.4m Sublane resolution without changing demand, reward or economics.
- A deterministic Python geometry camera consumes `vehicle_trace.v2`, camera calibration and vehicle
  cuboids to emit `visibility_trace.v1` plus compact geometry-visibility observations. Golden tests
  cover bus/truck-style occlusion, tie ordering, frustum bounds and legacy-trace rejection.

## Not yet a production claim

- Reward profile, demand/flow calibration, scenario set and evaluation economics remain subject to
  project-owner approval.
- Full-ROI multi-agent training, baseline comparison and cloud-scale validation are unfinished.
- The current sensor smoke path is not a calibrated depth/instance visibility pass. It must not be
  used as proof of physical occlusion or a final YOLO dataset.
- Road elevation is explicitly propagated when present; the current District 7 flat-map fallback is
  labelled `flat_assumption`. Bridges/ramps still need elevation-calibrated map data before physical
  elevation claims.
- Godot imports the shared camera calibration and receives hidden physical vehicle proxies, but it
  does not yet perform a depth/instance visibility pass.
- No trained RL policy, trained YOLO detector or final public-finance result should be claimed.

## Active dependency order

```text
map and physical render alignment
  -> camera calibration + vehicle dimensions
  -> geometry visibility and sensor observation adapter
  -> approved reward/flow scenarios
  -> RL baselines and partial-observation evaluation
  -> YOLO calibration and robust detector-noise experiments
```

Sensor geometry work may advance before reward/flow approval. RL performance claims may not.

## Status update rule

Update this file when a repository-wide capability becomes verified, superseded or blocked. Do not
copy individual task narratives here. Link a task manifest, test report or artifact manifest when a
status statement needs evidence.
