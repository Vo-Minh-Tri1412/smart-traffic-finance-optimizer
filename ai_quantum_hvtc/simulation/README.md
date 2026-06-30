# Simulation package

This package orchestrates traffic simulation inputs, backends, metrics, and trace export.

Read the full architecture note here:

```text
../../docs/02_ARCHITECTURE/SIMULATION_BACKEND_ARCHITECTURE.md
```

Short version:

- `engines/sumo/` is the official SUMO backend adapter.
- `engines/reference/` is validation-only and must not be used for final demo claims.
- `domain/`, `specs/`, and `routing/` prepare/validate the district problem.
- `metrics/` normalizes backend outputs into `SimulationResult`.
- `traces/` writes versioned replay/dashboard frames.

Python does not replace SUMO. Python exports SUMO inputs, calls SUMO, and parses SUMO outputs.
