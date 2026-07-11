# Optical Sensor Target

This document defines the long-term camera-based observation boundary. It is the authoritative
target for synthetic camera data, structured occlusion and future YOLO integration. It is not a
claim that the production sensor already exists.

## Canonical virtual camera

`DetectionCamera3D` is the project’s canonical virtual traffic camera. Its physical calibration is
stored in a renderer-neutral `camera_calibration.v1` document. The V1 RL sensor evaluates this
calibration headlessly against SUMO vehicle geometry; Godot imports the same calibration for replay
parity and later image capture.

For every configured camera frame, the camera should be able to produce:

- RGB image;
- depth information;
- instance/object-ID information;
- visibility records and label metadata;
- calibrated camera pose, FOV/intrinsics, image size, timestamp and render preset.

The demo may display this camera’s viewport, but it remains a fixed calibrated sensor. It is not
the user’s free-fly or walk camera.

## Observation boundary

```text
SUMO truth + signal timeline
  -> calibrated headless geometry camera
  -> deterministic depth/instance visibility
  -> visible-object tracker and structured uncertainty
  -> fixed-size approach/lane observation
  -> memory-aware traffic-control policy
```

SUMO truth may create training labels, reward and evaluation metrics. A policy evaluated as
camera-based receives only the resulting observed features and uncertainty, never hidden vehicle
ids, exact hidden counts or future state.

## Structured occlusion target

Occlusion is a physical observation effect, not corruption of SUMO traffic state. Visibility must
depend on camera pose, image resolution, lane geometry, vehicle dimensions, depth ordering and
occluders such as buses and trucks.

The observation adapter should preserve uncertainty rather than invent certainty:

- estimated count and class mix by approach/lane;
- confidence and visible fraction;
- time since reliable observation;
- unknown-object count and temporal tracker continuity;
- a declared sensor mode: oracle, geometry visibility, detector or mixed.

Noise is applied after physical visibility. Temporal dropout, type uncertainty, weather and detector
error must be correlated by camera, lane, distance, vehicle type and time; they are not independent
per-frame random deletion.

## Progressive delivery

1. Calibrated geometry visibility with canonical vehicle dimensions.
2. RGB/depth/instance output and depth-correct visible fraction.
3. Tracker and lane/approach observation adapter.
4. Clean-versus-occluded RL baselines using the approved reward and flow scenarios.
5. YOLO training/evaluation on exported camera frames.
6. Detector-error calibration and robust RL scenarios.

Raw image RL is not the first target. The first policy input is a compact lane/approach feature
vector with temporal memory.

## Non-negotiable constraints

- One metre in the prepared SUMO map and Godot world must retain a declared, stable relationship.
- Vehicle length, width, height and ground offset must be canonical data, not implicit mesh values.
- The headless geometry camera cannot read player-camera LOD. The future Godot depth/instance pass
  must similarly retain every object capable of affecting the configured sensor view.
- The capture interval, decision interval and aggregation rule are recorded in the training
  manifest.

## Related documents

- [Implementation Status](../04_STATUS/IMPLEMENTATION_STATUS.md)
- [Observation Space v1](../02_ARCHITECTURE/OBSERVATION_SPACE_V1.md)
- [Structured Occlusion and Sensor-Based RL](../02_ARCHITECTURE/STRUCTURED_OCCLUSION_AND_SENSOR_RL.md)
- [Synthetic Visual Sensor Dataset Contract](../02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md)

Change this document only when the sensor’s target boundary or scientific claim changes. Record
implementation progress in the status document instead.
