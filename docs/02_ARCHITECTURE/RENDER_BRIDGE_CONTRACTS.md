# Render bridge contracts

This document defines the artifact contracts between SUMO/Python and render adapters.

JSON/XML are used when data crosses process or language boundaries. UE-native Data Assets are the
planned editing surface for renderer-only configuration; see [asset pipeline](UNREAL_ASSET_PIPELINE.md).

## Contract versions

Bảng này là registry và trách nhiệm thiết kế, không chứng minh mọi producer đã hoàn tất.
Geometry/vehicle replay có implementation; TLS/event full-net logs và UE sensor exporter chưa đủ.
M0 TASK-095: loader đọc riêng `semantic_overlay.v1` (legacy anchored flows) và
`roi_semantic_overlay.v2` (polygon inventory). Giữ nguyên schema, geometry, parent source IDs,
tags, caveats và toàn bộ raw payload; không suy ra cổng hoặc demand từ polygon.
`roi_semantic_overlay.v1` của ROI utility chưa được adapter này hỗ trợ.
Registry constants Python/UE và report của `unreal_contract_smoke.py` vẫn chứa tên proposal
`semantic_overlay.v2`; smoke hiện chỉ kiểm tra geometry/vehicle, chưa validate overlay được khai báo.
Không coi report đó là bằng chứng native UE đã đọc retained polygon schema. Phần này còn phải
nối vào render consumer; table dưới ghi wire format thực của đầu vào.

| Contract | Version | Producer | Consumer | Purpose |
|---|---:|---|---|---|
| `geometry_manifest` | `geometry_manifest.v1` | Python/SUMO map prep | render adapter | points to SUMO net, bounds, geometry metadata |
| `vehicle_trace` | `vehicle_trace.v2` | Python SUMO parser | render adapter, sensors | vehicle-level frame stream |
| `traffic_light_trace` | `traffic_light_trace.v1` | Python SUMO parser | render adapter | traffic-light phase/state replay |
| `semantic_overlay` | `roi_semantic_overlay.v2` | retained map preparation | Python map loader, render/finance inputs | polygon inventory and provenance; no implied demand |
| `event_trace` | `event_trace.v1` | scenario runner | render adapter, reports | incidents, closures, road works, temporary speed changes |
| `visibility_trace` | `visibility_trace.v1` | geometry sensor adapter | RL observation adapter, sensor reports | camera FOV, depth ordering, visible/occluded vehicle state |
| `render_run_manifest` | `render_run_manifest.v1` | Python wrapper or demo config | render adapter | one file that wires geometry, traces, overlay, assets |
| `sensor_dataset_manifest` | `sensor_dataset_manifest.v1` | render sensor exporter | Python training workflow | frames, labels, masks, camera config, provenance |

`visibility_trace.v1` is produced by the deterministic Python geometry camera. It rasterizes
canonical vehicle cuboids into a software depth/instance buffer and does not depend on Unreal meshes
or presentation-camera LOD. This geometry producer is not a completed Unreal RGB/instance exporter.

Legacy `simulation_trace_frame.v1` remains in the dashboard/legacy path, not the native UE v2 reader. New render bridge
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
  "renderer": "unreal",
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
`simulation_trace_frame.v1` is a legacy path, rejected by the geometry camera and not the native UE v2 contract.

With the SUMO Sublane model, FCD `x,y` already includes the physical lateral displacement. The
separate `pos_lat_m` is preserved and interpolated as lateral-motion state, but replay must **not**
add it to `x,y` a second time. The renderer must fit each fallback mesh or imported visual asset to
the canonical `width_m × height_m × length_m` proxy after mapping that FCD pose.

## Camera-zone streaming — planned, not native UE implementation

Use spatial bounds and incremental activation, not arbitrary global quotas.
Sensor occluders must remain complete independently of presentation LOD/streaming.
Neutral zones are unclassified land, not verified building footprints, heights or capacities.

## `camera_calibration.v1`

Camera calibration is JSON so Python geometry visibility and
Unreal receive the same physical source. It contains camera pose in `sumo_xy_meters_z_up`, intrinsics,
image size, clipping planes, capture interval and target lanes. Unreal converts this coordinate system
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

## `roi_semantic_overlay.v2`

Overlay owns meaning, not road geometry.

```json
{
  "schema_version": "roi_semantic_overlay.v2",
  "id": "prepared_overlay",
  "name": "Prepared polygon inventory",
  "coordinate_system": "sumo_xy",
  "zones": [
    {
      "id": "zone_001",
      "type": "healthcare",
      "name": "Bệnh viện",
      "source_element_id": "way/123",
      "source_element_kind": "buildable_geometry",
      "geometry": {
        "type": "polygon",
        "coordinate_system": "sumo_xy",
        "coordinates": [[0, 0], [10, 0], [10, 10], [0, 0]]
      },
      "centroid": [6.67, 3.33],
      "anchor_edges": [],
      "anchor_junctions": [],
      "demand_enabled": true,
      "source_tags": {"amenity": "hospital"},
      "confidence": 0.85,
      "manual_review_required": false
    }
  ],
  "investment_candidates": []
}
```

IDs must be non-empty and unique within each collection. Polygon XY coordinates and centroid
must be finite; the polygon needs three distinct points and non-zero area. This checks structure,
not surveyed geometry, polygon topology, facility capacity or accessibility. Non-empty edge and
junction references must exist in the retained net. Unresolved anchors are permitted in the
inventory and remain explicitly empty. `demand_enabled` is eligibility, not a trip count or
reviewed gate. Any supplied legacy flow must use enabled, anchored zones. The generator rejects
missing flows or an empty scenario before creating outputs or invoking SUMO routing.

The former `semantic_overlay.v2` example with `zone_id/zone_type/display_name` was an unimplemented
proposal, not the retained wire format, and is rejected by the Python map loader. Legacy
`semantic_overlay.v1`
continues to require anchored zones. Planned UE Data Asset catalogs decide how a `healthcare`
zone looks without changing its semantics.

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

Traffic effects belong to SUMO/Python. Unreal may show cones, warnings, damaged vehicles, or camera
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
