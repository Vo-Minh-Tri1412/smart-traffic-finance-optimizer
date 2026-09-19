# Research dashboard

React/Vite/TypeScript frontend for the FastAPI service in ai_quantum_hvtc/dashboard.
Run npm install (or npm ci with the lockfile), npm run dev for development, and npm run build to
produce dist/. The dev server proxies /api; the backend can serve the built frontend.

Views cover district, replay, runs, comparison, finance and system state.
contracts/ and mock-data/ remain fixtures for tests and explicit demo mode; they are not retained-map
traffic or calibrated finance evidence. The current backend defaults to fixture/reference data.
Official retained-map integration must disable seeding and use matching experiment/run artifacts.

See [UI architecture](docs/UI_ARCHITECTURE.md), [trace design](docs/TRACE_REPLAY_DESIGN.md) and
[system delivery plan](../docs/02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md).
