# Imported visual assets

This folder is the Godot-side asset library. It is for curated assets that a scene can directly
instance or assign in the Godot editor.

Use this folder for visual/demo assets only:

- vehicle models and materials;
- building and landmark models;
- road/intersection meshes or materials;
- traffic-light props;
- street furniture;
- camera rigs;
- weather, sky, lighting, and UI/demo visuals.

Do not put SUMO maps, OSM extracts, model checkpoints, datasets, videos, or generated simulation
outputs here. Those belong in `simulation_projects/map_intake/`, `data/`, `artifacts/`, or Google
Drive depending on size and ownership.

## Folder map

```text
render/imported_assets/
├── vehicles/
├── buildings/
│   ├── hospital/
│   ├── school/
│   ├── industrial/
│   ├── residential/
│   ├── market/
│   ├── nightlife/
│   ├── gateway/
│   └── generic/
├── roads/
│   ├── materials/
│   └── meshes/
├── intersections/
├── traffic_lights/
├── street_furniture/
│   ├── trees/
│   ├── signs/
│   ├── barriers/
│   └── bus_stops/
├── cameras/
├── weather/
├── materials/
├── textures/
└── ui/
```

## Commit policy

- Small, licensed-for-use demo assets may be committed.
- Large asset packs, raw downloads, generated renders, and unclear-license files should stay out of
  Git and be linked from Google Drive.
- Keep attribution/license notes beside any non-original asset.

## How this relates to `.tres`

Godot scenes can already load assets directly from this folder. A `.tres` registry is only needed
later if several systems must choose assets by semantic type, for example:

```text
zone_type = hospital -> HospitalZoneVisual.tscn
road_tag = TRUCK_ROUTE -> TruckRoute material
weather = rain -> Rain render preset
```

Until that mapping becomes painful, scenes and presets can reference assets directly.
