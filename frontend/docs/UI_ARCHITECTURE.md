# React-ready UI architecture

The future UI should be a replay and decision-support app, not a second simulator.

## Data flow

```text
district_spec.json
  -> Python simulation backend
  -> simulation_trace.jsonl + metrics_summary.json + public_finance_summary.json
  -> React UI
```

For map creation, Godot is the authoring tool. The React UI should not become a map editor in v1;
it should read the same exported specs, traces, and summaries for dashboard/demo presentation.

## Main views

- District map: zones, roads, intersections, hospitals, schools, industry, logistics, nightlife,
  exported from the Godot-authored map or backend fixtures.
- Replay timeline: traffic light state, queue size, scenario events, controller changes.
- Compare mode: fixed-time vs rule-based vs RL.
- Public-finance panel: cost, public value, benefit-cost ratio, uncertainty/caveats.

## Non-goals for v1

- No custom physics in React.
- No direct SUMO-GUI dependency.
- No React map editor in v1. Godot Editor is the drag-and-drop map authoring surface.
- Do not edit generated `district_spec.generated.json` as the source of truth when a Godot
  authoring scene exists.
