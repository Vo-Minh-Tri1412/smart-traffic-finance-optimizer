# Trace replay design

`simulation_trace.jsonl` is one JSON object per frame or timestep. It is the shared contract between
SUMO, the React dashboard, and the Unreal render adapter.

Legacy aggregate schema version (vehicle replay uses vehicle_trace.v2):

```text
simulation_trace_frame.v1
```

Every frame must include `schema_version`. Consumers should fail clearly on unsupported versions
instead of silently guessing field semantics.

SUMO is the official simulation backend. Unreal uses FCD-derived vehicle trace frames when
they are available. Aggregate frames are still acceptable for dashboards and validation-only
backends, but they are not enough for vehicle replay.

## Detailed vehicle replay frame

The legacy example below describes compatibility data, not the complete physical vehicle contract.
New UE/sensor runs require vehicle_trace.v2 canonical dimensions, ground offsets and front-bumper
reference semantics; see [bridge contracts](../../docs/02_ARCHITECTURE/RENDER_BRIDGE_CONTRACTS.md).
The FCD-derived export contains one frame per timestep:

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
  "district_id": "toy_public_district_v1",
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

## Unreal boundary

Unreal must not infer traffic physics. It reads vehicle traces and maps SUMO metres to UE centimetres
with an explicit origin and front-bumper correction. Planned Data Assets select meshes/materials;
camera output remains a separate validated sensor feature.

If a trace only has aggregate metrics, the UI may show dashboard-style overlays, but it must not be
presented as a full vehicle-level replay.

## Versioning rule

Trace JSONL is a cross-system contract, so it stays language-neutral and versioned. If the schema
changes in a breaking way, create a new version string such as `simulation_trace_frame.v2` and update
Python exporters, frontend schema/tests, and Unreal loaders together. Do not add breaking fields and
hope downstream consumers infer the change.
