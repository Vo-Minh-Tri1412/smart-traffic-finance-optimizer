# Dashboard architecture

The existing React/Vite frontend and FastAPI service provide views for district, runs, replay,
comparison, finance and system status. They are not a second simulator.
The current default remains a toy DistrictSpec/reference-engine demo; real-map integration is planned.

## Data flow

Retained SUMO project + demand + controller → run artifacts and cost ledger →
dashboard and Unreal consuming the same experiment/run identity.

The source SUMO net owns geometry; semantic overlays own meaning. UE owns replaceable visual assets
and camera presets. React is not a map editor and must not modify generated inputs as a source of truth.

## Delivery requirements

- District view: retained geometry, zones, facility/candidate IDs and coverage.
- Replay: trace/TLS/event time; do not fabricate vehicles from aggregate counts.
- Compare: same demand/settings across fixed-time, rule-based and RL.
- Finance: measured QUBO impacts, raw cost, budget, uncertainty and evidence status.
- Explicit missing/error/synthetic state; disable automatic reference demo seeding for official runs.
- No separate reward or valuation calculation in the browser.

These requirements are not completed integration. See the
[delivery plan](../../docs/02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md) for gates.
