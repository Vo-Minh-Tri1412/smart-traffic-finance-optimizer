# Godot bridge refactor plan

Godot currently has the right pieces, but they are wired as scene peers. The next architecture step
is to make `SumoRenderBridge` the central coordinator while keeping the existing modules reusable.

## Target scene shape

```text
Main.tscn
└── SumoRenderBridge
    ├── DistrictReplayWorld
    ├── TraceReplayController
    ├── SemanticOverlayRenderer
    ├── TrafficLightStateLayer
    └── SensorExportLayer
```

`Main.tscn` should eventually point to a `render_run_manifest.v1`. The bridge resolves the manifest
and configures child modules.

## Migration order

1. Add a bridge script with exported paths and module NodePaths.
2. Keep existing `DistrictReplayWorld`, `TraceReplayController`, and `SemanticOverlayRenderer`
   behavior unchanged.
3. Move per-run wiring from scene hard-coded paths into a manifest/config step.
4. Add traffic-light state layer.
5. Add integration quality report collection.
6. Add sensor export orchestration.
7. Only after the above works, simplify `Main.tscn`.

## Design rules

- The bridge coordinates modules; it does not parse SUMO XML or spawn vehicles directly.
- Existing modules must remain individually testable.
- Godot-only visual choices stay in `.tres` catalogs.
- Cross-system paths and scenario inputs should move into `render_run_manifest.v1`.
- Standalone toy authoring/preview scenes are not part of the production bridge. Any future editor
  tooling must operate on real SUMO geometry, semantic overlay data, and render run manifests.

## Why not rewrite everything now

The current renderer already has valuable working pieces: typed trace data, interpolation, vehicle
pooling, SUMO geometry parsing, off-lane checks, zone catalogs, and sensor smoke scaffolding. A full
rewrite would create risk without improving traffic correctness. The safer strategy is to insert a
bridge layer, then migrate wiring module by module.
