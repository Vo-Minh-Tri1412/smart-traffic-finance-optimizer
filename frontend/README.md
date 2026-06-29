# Frontend Architecture Placeholder

This folder prepares the future React simulator UI without adding Node/Vite dependencies yet.

The frontend should not run traffic physics. It should replay backend artifacts:

- `contracts/district_spec.schema.json`
- `contracts/simulation_trace.schema.json`
- `contracts/metrics_summary.schema.json`
- `contracts/public_finance_summary.schema.json`
- `mock-data/*.json`

Target UI modules:

- District map view
- Traffic replay timeline
- Scenario/controller comparison
- Public-finance decision panel
- Evidence and caveat panel

SUMO/SUMO-RL remains the high-fidelity backend. The future React UI reads trace and summary files.
