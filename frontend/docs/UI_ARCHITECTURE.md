# React-ready UI architecture

The future UI should be a replay and decision-support app, not a second simulator.

## Data flow

```text
district_spec.json
  -> Python simulation backend
  -> simulation_trace.jsonl + metrics_summary.json + public_finance_summary.json
  -> React UI
```

## Main views

- District map: zones, roads, intersections, hospitals, schools, industry, logistics, nightlife.
- Replay timeline: traffic light state, queue size, scenario events, controller changes.
- Compare mode: fixed-time vs rule-based vs RL.
- Public-finance panel: cost, public value, benefit-cost ratio, uncertainty/caveats.

## Non-goals for v1

- No custom physics in React.
- No direct SUMO-GUI dependency.
- No map editor until the backend spec and trace contracts are stable.
