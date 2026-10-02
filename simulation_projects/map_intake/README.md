# Map intake workspace

This folder owns the retained SUMO project and map-intake artifacts. The current map is not
converted back into a DistrictSpec fixture.

M0 TASK-095, 2026-09-20: validate-sumo-net --project district7.project.json now validates the
retained roi_semantic_overlay.v2 without changing its geometry or provenance. It reports 2,588
unanchored polygons and missing demand. The roundtrip fails explicitly before routing when no
flows exist; map validation does not certify demand or end-to-end research readiness.

Use it when the team already has or generates a map first, then wants to refine the semantic,
economic, and visual layers for Unreal.

## Intended flow

```text
raw/prepared map source
  -> map intake manifest
  -> source preparation (preserve the existing reviewed net)
  -> SUMO netconvert / SUMO .net.xml
  -> semantic overlay + renderer-neutral annotation / Unreal render
  -> SUMO simulation and replay traces
```

For Quận 7 V1, the committed source of truth is:

```text
district7.project.json
  -> 02_prepared_sources/district7_osm_seed_20260702/district7_seed.net.xml  (DVC)
  -> 05_semantic_overlays/district7_buildable_polygons.v2.json
  -> 06_demand_configs/district7_demand.v1.json
```

The `.net.xml` owns road/lane/junction geometry. The overlay owns policy semantics such as zones,
demand anchors, candidate traffic lights, and public-value tags.

This keeps the workflow clear:

- `map_intake/` owns simulation map sources, DVC pointers, and review notes.
- `render_unreal/` owns UE code; `render_assets/` owns shared visual source assets.
- `tests/fixtures/specs/` owns tiny committed test specs.
- OSM/SUMO map artifacts are DVC-tracked when they need to be reproducible.
- SUMO-generated artifacts stay in ignored output folders.

## Folder map

```text
simulation_projects/map_intake/
├── 01_raw_sources/       # original OSM/SUMO/GeoJSON/CAD/manual files; ignored by Git
├── 02_prepared_sources/  # clipped/simplified/cleaned sources; ignored by Git
├── 04_review_notes/      # small notes/checklists about map quality and assumptions
├── 05_semantic_overlays/  # approved semantic polygons and SUMO-ID overlays for zones/candidates
├── 06_demand_configs/    # small committed scenario/demand runtime config
└── templates/            # committed templates for future map intake packages
```

## What belongs here

Examples:

- OpenStreetMap extract for a candidate district;
- SUMO `.net.xml` or `.edg.xml/.nod.xml` generated outside the main pipeline;
- GeoJSON road graph exported from another tool;
- a synthetic map generator output before reviewed map preparation;
- notes on why a road, zone, or intersection exists.

## What does not belong here

- Visual source assets: use `render_assets/`.
- model checkpoints or training logs: use `artifacts/` or Google Drive.
- generated SUMO run outputs: use the district-specific ignored `sumo_generated/` or `outputs/`.
- final team task ownership/deadlines: use the Google Drive taskboard.

## Commit policy

Raw and prepared map files are ignored by default. Commit only:

- README files;
- `.gitkeep` placeholders;
- small templates;
- `.dvc` pointer files for approved DVC-tracked artifacts;
  - explicitly approved semantic overlays with clear provenance.

If a map source is large or license-sensitive, track it with DVC or store it in Google Drive and
record the Drive/DVC reference in an intake manifest.
