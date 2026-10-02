# District 7 building-footprint visual intake — 2026-09-28

This is a separate, renderer-neutral visual geometry intake. It does not replace the retained
SUMO net, the approved semantic overlay, the demand config, or the existing Unreal placement file.
It does not assign capacity, occupancy, demand, trips, or economic value.

## Current source and measured coverage

The retained local OSM extract is:

`simulation_projects/map_intake/01_raw_sources/district7_osm_seed_20260702/district7_seed.osm`

Its recorded Overpass query uses the bbox south `10.705`, west `106.695`, north `10.775`, east
`106.780`, but requests highways, selected amenities, and selected landuse. It does not request
generic `way["building"]` elements. Parsing the local extract on 2026-09-28 found:

- 43,926 nodes, 9,958 ways, and 3 relations;
- 28 ways with a `building` tag, all closed and with all referenced nodes present;
- building tag values: `yes` 16, `roof` 9, `retail` 1, `commercial` 1, `hospital` 1;
- the existing `district7_visual_placements.v1.json` has 1,087 illustrative placements, of which
  19 carry `source_has_building_tag=true` (15 distinct source elements).

The 28 ways are therefore an incidental, partial baseline. They are not evidence that the bbox or
the retained SUMO ROI has complete building coverage. The retained net's declared source boundary
is `origBoundary=106.690981,10.692829,106.788488,10.779370`, which is slightly larger than the
Overpass bbox and must not be silently conflated with it.

## Reproducible query and artifact

The intended building-only query is recorded in
`district7_building_footprints_overpassql_20260928.overpassql` with query version
`building_footprints_overpassql.v1`:

```overpass
[out:xml][timeout:180];
way["building"](10.705,106.695,10.775,106.780);
(._;>;);
out body;
```

The current intake was generated from the existing local extract, without a broad new download:

```powershell
uv run python scripts/maps/prepare_building_footprints_intake.py `
  --source-osm simulation_projects/map_intake/01_raw_sources/district7_osm_seed_20260702/district7_seed.osm `
  --query-file simulation_projects/map_intake/04_review_notes/district7_building_footprints_overpassql_20260928.overpassql `
  --output artifacts/tmp/district7_osm_building_footprints_20260928/building_footprints.geojson `
  --qa artifacts/tmp/district7_osm_building_footprints_20260928/qa.json `
  --manifest artifacts/tmp/district7_osm_building_footprints_20260928/manifest.json `
  --placements render_unreal/CitySources/district7_visual_placements.v1.json `
  --retained-net simulation_projects/map_intake/02_prepared_sources/district7_osm_seed_20260702/district7_seed.net.xml `
  --overlay simulation_projects/map_intake/05_semantic_overlays/district7_buildable_polygons.v2.json
```

The generated manifest and QA report contain SHA-256 hashes for the raw OSM input, query,
validator, GeoJSON, retained net, overlay, and existing placement source. The output is WGS84
longitude/latitude GeoJSON with OSM way IDs and source tags retained for visual styling.

The hashes from this local intake are:

| Artifact | SHA-256 |
| --- | --- |
| raw OSM extract | `48ebde0a275940e19a0258f30a40f9f77a3e68eb8ae5866902711f9fb3f72753` |
| building-only query | `afc6213ff94a4894ff5c07227a0413dc996f7b088f9e554256960df3837b2ac9` |
| validator script | `80d418f47885cdc9feb39c10991d3fa6391060705c348d7ec06ea6152b9264ca` |
| derived GeoJSON | `d05da0dd600efc54d3c988ace984409a9dadbc25503f032fd99c9780dc2600c0` |
| QA report | `f7737140c13549a20175158db894a850d9f65dd4793011b06124a20a026c01c1` |
| retained SUMO net dependency | `80637f09674799490eecfcd9ae1c9abe3f795795350ca3b61e8aa53d4d1f33e0` |
| semantic overlay dependency | `9f596884721a3ccc956a929feabc83419816d9279a805ceb63a1b2edb331183a` |
| existing visual placements dependency | `61d6ff3f469df63ec2b2d60f6fbc4f219f35b5b42ca8d0065cdb87b379516542` |

## Expansion gate

Before this intake was created, a count-only building query was attempted against the documented
Overpass endpoint and an alternate public instance. The full bbox and a small tile returned gateway
timeouts; no full building response was downloaded. The endpoint status was reachable, but that is
not evidence that a large data query is safe. A later expansion should first run bounded count-only
tiles, record endpoint timestamp and response size, choose a tile limit, and only then download
exclusive raw tiles with their query and SHA-256 recorded. It must never overwrite the retained OSM
source or DVC pointer.

## Consumer contract

The generated layer is suitable only as a visual context/candidate geometry input after projection,
coordinate alignment, road-clearance checks, and duplicate/overlap review. It can inform building
mesh placement and styling. It must not modify SUMO lanes or signals, replace the semantic overlay,
or become a source for facility capacity, occupancy, demand, trip generation, or public-finance
metrics.
