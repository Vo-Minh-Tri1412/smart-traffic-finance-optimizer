# Render bridge contracts

This document defines the artifact contracts between SUMO/Python and render adapters.

JSON/XML are used when data crosses process or language boundaries. Godot `.tres` resources are used
only for Godot-owned visual configuration.

## Contract versions

| Contract | Version | Producer | Consumer | Purpose |
|---|---:|---|---|---|
| `geometry_manifest` | `geometry_manifest.v1` | Python/SUMO map prep | render adapter | points to SUMO net, bounds, geometry metadata |
| `vehicle_trace` | `vehicle_trace.v2` | Python SUMO parser | render adapter, sensors | vehicle-level frame stream |
| `traffic_light_trace` | `traffic_light_trace.v1` | Python SUMO parser | render adapter | traffic-light phase/state replay |
| `semantic_overlay` | `semantic_overlay.v2` | map ROI/zoning pipeline | render adapter, finance | zones, demand anchors, public-finance tags |
| `event_trace` | `event_trace.v1` | scenario runner | render adapter, reports | incidents, closures, road works, temporary speed changes |
| `visibility_trace` | `visibility_trace.v1` | geometry sensor adapter | RL observation adapter, sensor reports | camera FOV, depth ordering, visible/occluded vehicle state |
| `render_run_manifest` | `render_run_manifest.v1` | Python wrapper or demo config | render adapter | one file that wires geometry, traces, overlay, assets |
| `sensor_dataset_manifest` | `sensor_dataset_manifest.v1` | render sensor exporter | Python training workflow | frames, labels, masks, camera config, provenance |

`visibility_trace.v1` is produced by the deterministic Python geometry camera. It rasterizes
canonical vehicle cuboids into a software depth/instance buffer and does not depend on Godot meshes
or player-camera LOD. The Godot smoke path remains a projected-bounds plumbing test; it is not the
visibility producer.

Existing `simulation_trace_frame.v1` remains supported for backward compatibility. New render bridge
work should prefer `vehicle_trace.v2` naming for vehicle-level replay.

## `render_run_manifest.v1`

Minimum fields:

```json
{
  "schema_version": "render_run_manifest.v1",
  "run_id": "district7_roi_a_fixed_time_001",
  "geometry_manifest": "geometry_manifest.json",
  "vehicle_trace": "trace.jsonl",
  "traffic_light_trace": "traffic_lights.jsonl",
  "semantic_overlay": "semantic_overlay.json",
  "event_trace": "events.jsonl",
  "renderer": "godot",
  "quality_report": "render_bridge_quality_report.json"
}
```

Render adapters may ignore optional paths that are empty, but must warn when a declared file is
missing.

## `geometry_manifest.v1`

Minimum fields:

```json
{
  "schema_version": "geometry_manifest.v1",
  "geometry_source": "sumo_net_xml",
  "net_xml": "district.net.xml",
  "coordinate_system": "sumo_xy_meters",
  "bounds": {"min_x": 0.0, "min_y": 0.0, "max_x": 1000.0, "max_y": 1000.0},
  "lane_count": 0,
  "junction_count": 0
}
```

Road/lane geometry truth stays in SUMO `.net.xml`. The manifest indexes it; it does not duplicate
the full network.

## `vehicle_trace.v2`

Vehicle trace is JSONL. Each line is one frame.

```json
{
  "schema_version": "vehicle_trace.v2",
  "timestep": 12,
  "time_seconds": 12.0,
  "district_id": "district7_roi_a",
  "scenario_id": "normal_weekday",
  "controller_id": "fixed_time",
  "engine_id": "sumo",
  "vehicles": [
    {
      "vehicle_id": "veh_001",
      "vehicle_type": "car",
      "x": 123.4,
      "y": 567.8,
      "speed": 8.9,
      "angle": 90.0,
      "lane_id": "edge_0_0",
      "road_id": "edge_0",
      "length_m": 4.5,
      "width_m": 1.8,
      "height_m": 1.5,
      "ground_clearance_m": 0.0,
      "elevation_m": 0.0,
      "pos_lat_m": 0.0,
      "reference_point": "front_bumper_center"
    }
  ]
}
```

The model input for CV must be rendered images, not hidden vehicle trace values. The trace is only
ground truth for replay and label generation.

`vehicle_trace.v2` requires canonical physical fields for geometry visibility. SUMO `x,y` is the
front-bumper centre, so consumers must not treat it as the centre of the vehicle box. Existing
`simulation_trace_frame.v1` remains replay-compatible but is rejected by the geometry camera.

With the SUMO Sublane model, FCD `x,y` already includes the physical lateral displacement. The
separate `pos_lat_m` is preserved and interpolated as lateral-motion state, but replay must **not**
add it to `x,y` a second time. Godot fits each vehicle's fallback mesh or imported visual asset to
the canonical `width_m × height_m × length_m` proxy after mapping that FCD pose.

## Camera-zone streaming

The official Quận 7 renderer keeps every semantic and neutral zone whose conservative cached
polygon bound intersects the camera's active-radius and forward-prefetch corridor. It does not
impose a global zone-count quota: the active set is spatial, retained across small camera moves,
and updated incrementally. Neutral zones therefore remain ordinary building-bearing zones; they
are not a blank fallback plane.

## `camera_calibration.v1`

Camera calibration is JSON rather than a Godot `.tres` resource so Python geometry visibility and
Godot receive the same physical source. It contains camera pose in `sumo_xy_meters_z_up`, intrinsics,
image size, clipping planes, capture interval and target lanes. Godot converts this coordinate system
through the active SUMO world mapper; free-fly camera state is never used.

`geometry_raster_size` may be lower than the future RGB resolution for fast RL visibility runs. The
geometry engine scales intrinsics to that raster deterministically and records the calibration, so
the effective resolution remains explicit rather than being an accidental LOD policy.

## `visibility_trace.v1`

The visibility trace is an optional JSONL artifact produced from a calibrated camera and vehicle
geometry. It is also valid when no learned CV model exists:

```json
{
  "schema_version": "visibility_trace.v1",
  "time_seconds": 12.0,
  "camera_id": "CAM_I06_HIGH_01",
  "vehicle_id": "veh_001",
  "visible_fraction": 0.42,
  "occlusion_fraction": 0.58,
  "depth_m": 37.4,
  "in_fov": true,
  "visibility_state": "partially_occluded"
}
```

The producer records camera pose/intrinsics through the linked `camera_calibration.v1` artifact.
This trace describes physical geometry visibility, not a detector confusion matrix. Detector-specific
errors may be attached later by a sensor model.

## `traffic_light_trace.v1`

Traffic lights are first-class state, not just intersection metadata.

```json
{
  "schema_version": "traffic_light_trace.v1",
  "time_seconds": 12.0,
  "traffic_lights": [
    {
      "traffic_light_id": "J42",
      "junction_id": "J42",
      "phase_index": 2,
      "state": "GrGr",
      "remaining_seconds": 8.0
    }
  ]
}
```

If SUMO manages traffic lights, render adapters must follow SUMO state rather than recomputing the
phase visually.

## `semantic_overlay.v2`

Overlay owns meaning, not road geometry.

```json
{
  "schema_version": "semantic_overlay.v2",
  "zones": [
    {
      "zone_id": "zone_001",
      "zone_type": "healthcare",
      "display_name": "Bệnh viện",
      "anchor_edges": ["edge_a", "edge_b"],
      "source_tags": {"amenity": "hospital"},
      "confidence": 0.85,
      "manual_review_required": false
    }
  ],
  "investment_candidates": [],
  "demand_anchors": []
}
```

Godot uses `.tres` catalogs to decide how a `healthcare` zone looks.

## `event_trace.v1`

Events describe scenario state that may affect traffic in SUMO and visuals in render.

```json
{
  "schema_version": "event_trace.v1",
  "time_seconds": 120.0,
  "events": [
    {
      "event_id": "incident_001",
      "event_type": "lane_closure",
      "edge_id": "edge_123",
      "severity": "medium",
      "visual_state": "active"
    }
  ]
}
```

Traffic effects belong to SUMO/Python. Godot may show cones, warnings, damaged vehicles, or camera
labels, but it does not decide route capacity.

## `sensor_dataset_manifest.v1`

Minimum fields:

```json
{
  "schema_version": "sensor_dataset_manifest.v1",
  "dataset_id": "district7_synthetic_cv_smoke",
  "source_render_run": "render_run_manifest.json",
  "frames": [],
  "labels": [],
  "visibility_trace": "visibility.jsonl",
  "camera_rigs": [],
  "caveat": "synthetic rendered data"
}
```

This manifest is for data management and model training workflows. It should be DVC/Drive-backed
when it references large image outputs.
