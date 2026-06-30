# Trace replay design

`simulation_trace.jsonl` is one JSON object per frame or timestep. It is the shared contract between
SUMO, the future React dashboard, and the Godot render app.

Current schema version:

```text
simulation_trace_frame.v1
```

Every frame must include `schema_version`. Consumers should fail clearly on unsupported versions
instead of silently guessing field semantics.

SUMO is the official simulation backend. Godot should prefer FCD-derived vehicle trace frames when
they are available. Aggregate frames are still acceptable for dashboards and validation-only
backends, but they are not enough for a convincing Godot replay.

## Detailed vehicle replay frame

Godot uses this vehicle-level frame as its primary replay input. It is produced from SUMO FCD-derived
trace export and contains one frame per timestep:

- `timestep`
- `schema_version`
- `time_seconds`
- `district_id`
- `scenario_id`
- `controller_id`
- `engine_id`
- `vehicles`, where each vehicle has:
  - `vehicle_id`
  - `vehicle_type`
  - `x`
  - `y`
  - `speed`
  - `angle`
  - `lane_id` or `road_id`

Example:

```json
{
  "schema_version": "simulation_trace_frame.v1",
  "timestep": 0,
  "time_seconds": 0.0,
  "district_id": "minh_khai_district_v1",
  "scenario_id": "normal_weekday",
  "controller_id": "fixed_time",
  "engine_id": "sumo",
  "vehicles": [
    {
      "vehicle_id": "F_MARKET_MORNING_DELIVERY_BIKE.0",
      "vehicle_type": "DELIVERY_BIKE",
      "x": 9.79,
      "y": -4.8,
      "speed": 10.54,
      "angle": 90.0,
      "lane_id": "R01_0",
      "road_id": "R01"
    }
  ]
}
```

Recommended extra fields:

- traffic-light state snapshot for controlled intersections;
- route id or origin-destination tags when safe to expose;
- camera visibility hints for dataset export;
- event markers such as emergency priority, incident, or controller intervention.

## Aggregate dashboard frame

React dashboards may also consume aggregate frames:

- `schema_version`
- `timestep`
- `time_seconds`
- `district_id`
- `scenario_id`
- `controller_id`
- `engine_id`
- `traffic_lights`
- `road_occupancy`
- `intersection_queues`
- `events`
- `metrics`

## Godot boundary

Godot should not infer traffic physics. It should read vehicle-level trace frames, map SUMO
coordinates into Godot world coordinates, instance scenes from
`render/resources/configs/asset_manifest*.json`, and render camera outputs.

If a trace only has aggregate metrics, Godot may show dashboard-style overlays, but it should not be
presented as a full vehicle-level replay.

## Versioning rule

Trace JSONL is a cross-system contract, so it stays language-neutral and versioned. If the schema
changes in a breaking way, create a new version string such as `simulation_trace_frame.v2` and update
Python exporters, frontend schema/tests, and Godot loaders together. Do not add breaking fields and
hope downstream consumers infer the change.
