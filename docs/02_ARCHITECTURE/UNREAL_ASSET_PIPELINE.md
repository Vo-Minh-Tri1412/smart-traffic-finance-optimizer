# Unreal asset pipeline and interactive demo

Decision recorded: 2026-09-19. **Accepted design, not implemented capability.**
The full delivery sequence is in [System delivery plan](SYSTEM_DELIVERY_PLAN.md).

## Ownership and editing surface

SUMO owns positions, routes, dimensions and signal states. UE owns their visual representation.
Use native `UPrimaryDataAsset` catalogs, `TSoftObjectPtr`/`TSoftClassPtr` references and the built-in
Asset Manager. Register primary asset types and load/unload bundles asynchronously; do not build a
second general-purpose asset manager. See [Epic asset management](https://dev.epicgames.com/documentation/unreal-engine/asset-management-in-unreal-engine).

Three separately editable data groups are required:

| Group | Contents | Must not contain |
|---|---|---|
| Asset catalog | Stable ID, mesh/Blueprint, materials, physical envelope, pivot, forward axis, LOD, source/license | Traffic or financial decisions |
| Placement profile | Geometry/semantic-based placement and object-ID-specific overrides | A second road network |
| Scene profile | Catalog references, lighting, camera, quality and streaming presets | Demand or reward changes |

Data Assets are authoritative for UE-only art settings. Export a read-only JSON snapshot and hash
for each render run; do not maintain hand-edited JSON and Data Assets as competing authorities.
Keep existing renderer-neutral bridge schemas compatible. Engine paths belong to profiles/catalogs,
not branches in replay code. Source geometry, overlay IDs and trace timestamps remain authoritative.

## Components and replacement contract

- Vehicle actors separate their canonical physical proxy from replaceable visual components.
  Body/wheel attachments, forward axis, ground pivot and material slots are explicit.
- Signal actors expose pole, arm, head, lens/material slots and facing. Map each head to actual
  SUMO `tls_id` and controlled `linkIndex`; do not infer one color for an entire junction.
- Buildings, curbs, lights and props are selected through semantic/road catalogs. A land-use polygon
  is not automatically a measured building footprint or a facility capacity.
- A designer must be able to replace a vehicle or signal-head asset in the Editor without editing
  the bridge, SUMO controller or reward code. Canonical coordinates and dimensions must not change.
- Missing assets produce an explicit warning and counted debug fallback. Final demo validation
  rejects unresolved critical assets; no silent substitution that could change sensor labels.

Import validation checks finite dimensions, axis/pivot, scale, missing textures, material slots,
required attachments, unique IDs and source/license metadata. Preserve provenance for existing
Kenney assets; mixing their style with new assets is not itself a semi-realistic art direction.

## Geometry, streaming and reproducibility

Read roads and junctions from the retained SUMO net. Preserve Z when present; declare missing
elevation as a flat assumption. Do not silently flatten bridges or change the source net.
Use spatial tile meshes, instanced repeated props, vehicle pooling and bounded incremental loading.
Avoid a separate editable actor for every lane/polygon across the complete network.

Display-camera streaming must not remove objects that can occlude a calibrated sensor. Sensor
capture has its own complete active set and deterministic pose/time. Free camera movement never
changes a sensor calibration or a traffic result. Run manifests record map, trace, asset snapshot,
camera and preset identities.

## Demo and sensor presets

The chosen target is semi-realistic interactive rendering on the existing RTX 3050 4 GB machine.
Prepare readable daylight and presentation dusk presets; hardware ray tracing is not a default
requirement. Prefer consistent PBR materials and appropriately sized textures over asset quantity.
The first corner must come from the retained map, at a validated pilot signal, with actual replay
and TLS trace. Unverified surrounding architecture is illustrative, not a surveyed reconstruction.

Acceptance: a real UE 1920x1080 still plus replay, no missing textures, incorrect ground contact or
TLS state mismatch. Record a 60-second benchmark after warm-up with preset, visible counts and GPU
memory. Target P95 frame time <= 33.3 ms at 1080p; this is an acceptance target, not measured FPS.
Do not achieve it by dropping traffic from the active view without reporting that loss.

Use a distinct sensor preset for synchronized RGB/depth/instance exports. Do not use post-processing
that makes masks disagree with RGB, or projected rectangles as depth-correct masks. Actor-ID mapping
must survive pooling and seek. Movie Render Queue Object IDs are experimental and Editor-only;
the initial exporter targets Editor batch, not a shipping executable. See
[Epic render passes](https://dev.epicgames.com/documentation/unreal-engine/cinematic-render-passes-in-unreal-engine).

Split physical appearance labels from economic roles. An unmarked car cannot reveal its passenger's
trip purpose; a worker shuttle is not a separately detectable class without visible evidence.
Test bus/truck occlusion, truncation and more than 255 identities; do not assume an 8-bit stencil
is a globally unique instance registry.

## Storage and control plane

Keep small curated non-regenerable UE packages in Git LFS under existing attributes. Generated
maps, imported bulk data, screenshots, sensor datasets and checkpoints use DVC/Drive or ignored
artifact directories. Validate licenses before redistributing downloaded assets.
The existing experimental UE MCP is optional Editor tooling on loopback, not runtime transport
and not a reason to install unrelated plugins. CLI/Editor automation must work without MCP.

The current staged `unreal_signal_demo.py` scene is a prototype, not this architecture and not
proof of retained-map geometry, calibrated demand or completed sensor exports.
