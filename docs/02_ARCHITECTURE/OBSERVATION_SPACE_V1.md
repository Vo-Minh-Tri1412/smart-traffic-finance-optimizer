# Observation Space v1

This is the single canonical observation-space contract for the smart-traffic RL controller.
Other architecture documents must reference this file instead of defining their own incompatible
observation lists.

## Plain meaning

At each decision step, the traffic-light agent should answer:

> What is happening around this intersection right now, and is there any public-service vehicle or
> downstream road condition that should affect the next signal decision?

The observation is what the RL agent can see. It is not the final economic score, and it is not the
whole city story.

## Controlled unit

Default unit: **one controlled traffic light = one RL agent**.

Each controlled intersection observes only:

- its incoming approaches;
- its outgoing/downstream congestion risk;
- its current signal phase;
- priority vehicles near that intersection;
- coarse time/scenario context.

Multi-agent coordination can be added later, but v1 should not require a single agent to observe the
entire district.

## Required observation fields

These fields are required for v1 unless an implementation task explicitly records a smaller fallback.

| Group | Field | Type | Plain meaning |
|---|---|---|---|
| Queue | `queue_length_by_approach` | numeric vector | How many vehicles are waiting on each incoming road. |
| Waiting | `waiting_time_by_approach` | numeric vector | How long vehicles have been waiting on each incoming road. |
| Arrival pressure | `approaching_vehicle_count_by_approach` | numeric vector | How many vehicles are close enough to arrive soon. |
| Downstream risk | `downstream_density_by_movement` | numeric vector, 0..1 | Whether the road after the green light is already full. |
| Signal state | `current_phase_id` | one-hot or integer | Which light phase is active now. |
| Signal timing | `elapsed_phase_time_seconds` | numeric | How long the current phase has been active. |
| Safety timing | `min_green_satisfied` | boolean | Whether switching phase is legally/safely allowed. |
| Emergency | `emergency_vehicle_present_by_approach` | boolean vector | Whether an ambulance/emergency vehicle is waiting or approaching. |
| Public transport | `bus_waiting_count_by_approach` | numeric vector | How many buses are waiting. |
| Freight | `truck_waiting_count_by_approach` | numeric vector | How many trucks are waiting. |
| Time context | `time_of_day_bucket` | one-hot | Morning rush, daytime, evening, night, event window, etc. |

## Optional context fields

These fields are useful but should be added only after the basic observation works.

| Field | Plain meaning | Caution |
|---|---|---|
| `intersection_role_tags` | Static tags such as hospital access, school zone, industrial gate, bus corridor, bottleneck. | Good for policy-aware control, but keep encoding simple. |
| `scenario_id` | Normal day, industrial shift, hospital emergency, event, incident, etc. | Useful in controlled experiments; avoid hiding unrealistic assumptions. |
| `neighbor_queue_summary` | Small summary of nearby controlled intersections. | Add only after single-intersection observations are stable. |
| `weather_or_incident_flag` | Whether a special incident reduces capacity. | Only use if the scenario actually models it. |

## Do not put these in the observation

The agent should not directly receive:

- final `public_value_score`;
- installation cost or budget rank;
- future metric values;
- answer labels such as "this intersection should win";
- hidden data from the whole simulation that a traffic controller could not plausibly know.

Those belong to evaluation and public-finance scoring, not to the RL observation.

## Fallback observation

If implementation is blocked, the minimum acceptable fallback is:

```text
queue_length_by_approach
waiting_time_by_approach
current_phase_id
elapsed_phase_time_seconds
```

This fallback is acceptable only for a debug prototype. The project-grade demo should restore priority
vehicle, downstream-density, bus/truck, and time-context fields.

## Relationship to economics

Economics does **not** need to fill this observation space.

Economics only needs to define the real-world meaning behind the fields:

- Which zones create the trips?
- Which vehicle types matter more?
- Which scenarios should be tested?
- Which delays are more serious for society or the economy?
- Which investment choices are worth comparing?

CS converts those decisions into observation fields, routes, metrics, and scoring code later.

## Version rule

If this observation space changes, update this file first. Then update dependent docs by reference.
Do not maintain separate observation-space lists in multiple documents.
