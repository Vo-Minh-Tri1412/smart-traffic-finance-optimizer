# Map intake workspace

This folder is the staging area for maps before they become a Godot authoring scene or a committed
`district_spec`.

Use it when the team already has or generates a map first, then wants to refine the semantic,
economic, and visual layers in Godot.

## Intended flow

```text
raw/prepared map source
  -> map intake manifest
  -> conversion/import script or manual Godot import
  -> Godot authoring scene
  -> district_spec.generated.json
  -> SUMO simulation
```

This keeps the workflow clear:

- `map_intake/` owns pre-Godot map sources and review notes.
- `render/` owns Godot scenes and visual assets.
- `simulation_projects/<district>/specs/` owns committed district specs.
- SUMO-generated artifacts stay in ignored output folders.

## Folder map

```text
simulation_projects/map_intake/
├── 01_raw_sources/       # original OSM/SUMO/GeoJSON/CAD/manual files; ignored by Git
├── 02_prepared_sources/  # clipped/simplified/cleaned sources; ignored by Git
├── 03_godot_seed_specs/  # generated seed specs before manual Godot editing; ignored by Git
├── 04_review_notes/      # small notes/checklists about map quality and assumptions
└── templates/            # committed templates for future map intake packages
```

## What belongs here

Examples:

- OpenStreetMap extract for a candidate district;
- SUMO `.net.xml` or `.edg.xml/.nod.xml` generated outside the main pipeline;
- GeoJSON road graph exported from another tool;
- a synthetic map generator output before Godot cleanup;
- notes on why a road, zone, or intersection exists.

## What does not belong here

- Godot visual assets: use `render/imported_assets/`.
- model checkpoints or training logs: use `artifacts/` or Google Drive.
- generated SUMO run outputs: use the district-specific ignored `sumo_generated/` or `outputs/`.
- final team task ownership/deadlines: use the Google Drive taskboard.

## Commit policy

Raw and prepared map files are ignored by default. Commit only:

- README files;
- `.gitkeep` placeholders;
- small templates;
- small, explicitly approved sample maps with clear license/provenance.

If a map source is large or license-sensitive, store it in Google Drive and record the Drive link in
an intake manifest.
