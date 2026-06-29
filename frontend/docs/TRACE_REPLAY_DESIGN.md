# Trace replay design

`simulation_trace.jsonl` is one JSON object per timestep.

The UI should treat missing detailed vehicle positions as acceptable. The reference backend may only
emit aggregate queues and events, while SUMO can later emit richer vehicle positions. This keeps the
UI stable even when the backend changes.

Minimum frame fields:

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
