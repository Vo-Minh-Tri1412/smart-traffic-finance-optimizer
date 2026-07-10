# Observation Space v1

This is the canonical local observation contract for the multi-agent traffic-signal policy. It is
valid for the full Quận 7 SUMO network or a reviewed large ROI; the small fixture is only a schema
and runtime test input.

## Controlled unit

Default unit: **one controlled traffic light = one agent**. Agents share policy parameters but do not
need to receive the whole district vector. Coordination comes from downstream summaries,
neighborhood messages or centralized training when required.

At each decision step, the agent should answer:

> What is happening on my approaches, what can arrive next, what is downstream, and how certain is
> the available observation?

## Required fields

| Group | Field | Type | Meaning |
|---|---|---|---|
| Queue | `queue_length_by_approach` | numeric vector | Estimated waiting vehicles per incoming approach. |
| Waiting | `waiting_time_by_approach` | numeric vector | Estimated waiting time per approach. |
| Arrival | `approaching_vehicle_count_by_approach` | numeric vector | Vehicles likely to arrive before the next decision. |
| Downstream | `downstream_density_by_movement` | numeric vector, 0..1 | Estimated downstream occupancy/capacity risk. |
| Signal | `current_phase_id` | integer/one-hot | Current legal phase. |
| Timing | `elapsed_phase_time_seconds` | numeric | Time spent in the current phase. |
| Safety | `min_green_satisfied` | boolean/vector | Whether a switch is legal. |
| Emergency | `emergency_vehicle_present_by_approach` | boolean vector | Ambulance/emergency presence estimate. |
| Public transport | `bus_waiting_count_by_approach` | numeric vector | Estimated buses waiting. |
| Freight | `truck_waiting_count_by_approach` | numeric vector | Estimated trucks waiting. |
| Context | `time_of_day_bucket` | one-hot | Rush, daytime, night, event or incident window. |

## Sensor uncertainty fields

These fields are required when the policy is evaluated as camera-based or partially observed:

| Field | Type | Meaning |
|---|---|---|
| `observation_confidence_by_approach` | numeric vector, 0..1 | Confidence in the approach estimate. |
| `visible_fraction_by_approach` | numeric vector, 0..1 | Approximate fraction of relevant vehicles/area visible. |
| `time_since_last_observed_by_approach` | numeric vector | Age of the last reliable observation. |
| `detector_unknown_count_by_approach` | numeric vector | Objects visible but not confidently classified. |
| `sensor_mode` | categorical/one-hot | SUMO oracle, geometry visibility, detector or mixed. |

The visibility fields let the policy learn a conservative response to a bus/truck occlusion without
receiving hidden SUMO IDs or exact hidden counts.

## Optional coordination fields

- `neighbor_queue_summary`: bounded summaries of adjacent signals;
- `neighbor_phase_summary`: phase and remaining-green summaries for adjacent signals;
- `intersection_role_tags`: hospital, school, industrial, bus corridor or bottleneck tags;
- `scenario_id` or `weather_or_incident_flag` when the scenario genuinely exposes that context;
- `upgrade_mask_local`: whether the signal and relevant neighbors are equipped for intelligent control.

Neighborhood fields must have a stable maximum size or graph adapter. Do not concatenate an
unbounded 100-signal vector into every agent observation.

## Memory contract

The observation at time `t` may be passed directly, stacked over a fixed window, or consumed by a
recurrent policy state:

```text
o_t                 -> memoryless PPO baseline
[o_t-k ... o_t]     -> frame-stack baseline
(o_t, h_{t-1})      -> LSTM/RecurrentPPO policy
```

The camera capture interval and policy decision interval must be recorded in the training manifest.
The adapter should aggregate intermediate frames rather than silently dropping them.

## Do not expose

The agent must not directly receive:

- final `public_value_score`;
- installation cost or QUBO rank;
- future metric values;
- hidden vehicle state that is unavailable to the selected sensor mode;
- an answer label saying which intersection should receive investment.

Those belong to evaluation, finance and experiment design.

## Oracle/debug mode

SUMO state observations remain useful for debugging and an upper-bound policy. They must be tagged as
`sensor_mode = oracle` and reported separately from geometry-visibility or detector-based runs.

## Version rule

If this contract changes, update this file first, then update the sensor adapter, training manifest,
and dependent docs. Keep the visibility and memory additions compatible with the multi-agent local
observation shape.
