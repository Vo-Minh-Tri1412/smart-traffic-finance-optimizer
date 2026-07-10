# Structured Occlusion and Sensor-Based RL

## Decision

The project may train the traffic-control RL policy before a YOLO model exists. The first visual
sensor should be a deterministic, geometry-based partial-observation layer driven by SUMO traces
and a calibrated Godot camera. YOLO is optional at this stage and is introduced later to model
detector-specific errors or to validate the synthetic sensor pipeline.

This keeps the traffic simulator, visual sensor, and policy layers separate:

```text
SUMO truth and vehicle trace
  -> calibrated 3D camera geometry
  -> RGB/depth/instance visibility approximation
  -> observed lane features
  -> memory-aware multi-agent RL
```

SUMO remains the source of traffic dynamics, routes, signal phases and reward metrics. The optical
layer changes what the controller can observe; it must not mutate the underlying SUMO traffic state.

## Why geometry can come before CV

For a structured occlusion such as a bus or heavy truck blocking cars behind it, the important
causal variables are camera pose, vehicle footprint/height, lane geometry, relative depth and
vehicle motion. They can be approximated without a learned detector.

For each vehicle, the renderer should project a 3D bounding box using camera intrinsics and
extrinsics:

```text
camera pose (height h, pitch, yaw, roll)
  + FOV/resolution/intrinsics
  + SUMO x/y/angle and road elevation
  + vehicle length/width/height
  -> projected footprint and depth ordering
  -> visible fraction / occlusion state
```

This approximation is sufficient to create a partially observed RL environment. It does not model
all YOLO errors: false positives, class confusion, missed detections caused by blur, rain, lighting,
or poor texture. Those errors can be added later as a learned or calibrated sensor-error layer.

## Optical visibility contract

The render bridge should eventually produce one visibility record per vehicle and camera frame:

```json
{
  "vehicle_id": "veh_001",
  "camera_id": "CAM_I06_HIGH_01",
  "visible_fraction": 0.42,
  "occlusion_fraction": 0.58,
  "depth_m": 37.4,
  "in_fov": true,
  "visibility_state": "partially_occluded"
}
```

The exact values may be approximate, but the ordering must be physically consistent. A production
sensor pass should use RGB plus depth and instance/object-ID buffers. The current smoke path uses
projected rectangles and is not yet an occlusion-quality dataset.

### Required geometry fields

- Camera position and orientation in the same world unit as the rendered SUMO map.
- Camera FOV or calibrated focal lengths and principal point.
- Image size and capture interval.
- SUMO vehicle `length_m`, `width_m`, and `height_m`.
- Road/lane elevation when bridges, ramps or overpasses are in the ROI.
- Vehicle ground offset and visual-asset scale.

`body_height` in the current Godot vehicle script is a render placement value, not a canonical
vehicle roof height. A future schema must distinguish vehicle dimensions from ground/world offsets.

## Structured sensor noise

The first RL sensor can use geometry-only visibility. If noise is needed before YOLO exists, it should
be added after visibility and before the observation adapter:

| Noise family | Example | Correlation |
|---|---|---|
| Geometric occlusion | bus/truck blocks a car | same camera, lane and depth ordering |
| Resolution/truncation | small or distant vehicles disappear | distance and camera resolution |
| Temporal dropout | detector stays blind for several frames | consecutive frames and vehicle track |
| Type uncertainty | car/truck class becomes unknown | vehicle type, scale and visibility |
| Count aggregation error | visible count is under/over-estimated | approach, queue density and camera |
| Weather/lighting | rain, night, glare, motion blur | camera preset and scenario |

The RL observation should retain uncertainty features such as confidence, visible fraction and
time-since-last-observed. It should not receive hidden SUMO IDs or exact hidden vehicle counts in a
camera-based experiment.

## Observation pipeline

The recommended observation pipeline is:

```text
SUMO FCD + signal state
  -> camera visibility model
  -> optional detector/noise model
  -> lane/approach tracker
  -> fixed-size local observation
  -> frame stack or recurrent policy state
```

The tracker should preserve short-term identity and queue continuity through brief occlusion. For a
vehicle that is fully hidden for a long time, the system should maintain a belief or uncertainty,
not pretend that its exact state is known.

## Memory strategy

Use the following progression:

1. Geometry-only observations with no memory, as a baseline.
2. A fixed stack of 4–8 aggregated lane-feature snapshots.
3. A shared recurrent policy (`RecurrentPPO` with an LSTM policy) when frame stack is insufficient.
4. A graph/centralized critic or message-passing policy for larger ROIs.

Raw image frame stacking is not the first target for a signal controller. The policy should first
consume compact sensor features so the temporal memory is about traffic state, not image encoding.

The simulator step, camera capture interval and policy decision interval must be explicit. A camera
may capture at 1 second while the policy acts every 5–30 seconds; the adapter should aggregate the
intermediate frames rather than silently treating them as equal decision steps.

## Training curriculum

Training scenarios should progress from easy to hard:

```text
clean geometry visibility
  -> partial occlusion with accurate dimensions
  -> correlated temporal dropout and uncertainty
  -> weather/lighting/domain randomization
  -> optional detector confusion calibrated from YOLO
```

SUMO truth remains available for reward and evaluation. It is not fed into the observation when the
experiment claims camera-based control.

## Evaluation

Report both sensor and control metrics:

- visible/occluded vehicle count error by approach and vehicle type;
- queue-length and downstream-density error;
- detection/tracking continuity through occlusion;
- total delay, throughput and spillback;
- bus passenger, truck and emergency delay;
- policy degradation from clean to severe visibility conditions.

The key claim is not that RL reconstructs every hidden vehicle exactly. The claim is that a policy
trained under structured partial observation remains safe and useful when large vehicles occlude
smaller vehicles.

## Current repository status

The camera catalog already contains positions, orientations, FOV and image sizes, and the render
bridge already carries SUMO vehicle traces. The current sensor smoke exporter is still a plumbing
test: it does not yet provide production RGB/depth/instance visibility or a calibrated `height_m`
contract. This document therefore describes the approved design direction, not a completed CV
dataset.
