# Trace replay design

`simulation_trace.jsonl` is one JSON object per frame or timestep. It is the shared contract between
SUMO, the future React dashboard, and the Godot render app.

SUMO is the official simulation backend. Godot should prefer FCD-derived vehicle trace frames when
they are available. Aggregate frames are still acceptable for dashboards and validation-only
backends, but they are not enough for a convincing Godot replay.

## Detailed vehicle replay frame

Godot needs at least:

- `timestep` or `time_seconds`
- `district_id`
- `scenario_id`
- `controller_id`
- `engine_id`
- `vehicle_id`
- `vehicle_type`
- `x`
- `y`
- `speed`
- `angle`
- `lane` or `road_id`

Recommended extra fields:

- traffic-light state snapshot for controlled intersections;
- route id or origin-destination tags when safe to expose;
- camera visibility hints for dataset export;
- event markers such as emergency priority, incident, or controller intervention.

## Aggregate dashboard frame

React dashboards may also consume aggregate frames:

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

Godot should not infer traffic physics. It should read trace frames, map SUMO coordinates into Godot
world coordinates, instance scenes from `render/resources/configs/asset_manifest*.json`, and render
camera outputs.

If a trace only has aggregate metrics, Godot may show dashboard-style overlays, but it should not be
presented as a full vehicle-level replay.
