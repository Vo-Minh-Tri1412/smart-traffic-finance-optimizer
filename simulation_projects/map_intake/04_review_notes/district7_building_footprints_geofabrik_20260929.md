# District 7 building footprints from Geofabrik PBF — 2026-09-29

## Result and scope

This is a separate visual geometry layer extracted from the already-downloaded local Geofabrik
Vietnam PBF. It supplements the 2026-09-28 baseline note, whose 28 incidental building-tagged
ways came from an Overpass extract that did not request generic buildings. It does not replace or
edit the retained SUMO net, the approved semantic overlay, demand configuration, or existing Unreal
placements. No building capacity, occupancy, demand, trips, public value, economic impact, or
observed building height is assigned. Source OSM tags, including any height tag, are preserved as
unverified source attributes only.

The input PBF is
`artifacts/tmp/district7_geofabrik_vietnam_260701/vietnam-260701.osm.pbf` (325,119,062 bytes).
Its header reports OSM replication timestamp `2026-07-01T20:22:00Z`, sequence `4832`, and
country bounds `102.095945,7.382239` to `114.642323,23.402135`. The adjacent Geofabrik MD5 sidecar
was verified: `538d1129498dad129cd558c088c1afe0`. SHA-256 is
`b5ebb3c2aaa8933344cfe331c594c08b0e5993da237f54635da6d3a15354cdd4`. The PBF was already local;
this extraction did not download another map extract. OpenStreetMap data is licensed under ODbL 1.0
and requires attribution: © OpenStreetMap contributors. Geofabrik source page:
[Vietnam download page](https://download.geofabrik.de/asia/vietnam.html).

## ROI and geometry handling

The extraction ROI follows the retained SUMO net's `origBoundary`
`west_lon,south_lat,east_lon,north_lat = 106.690981,10.692829,106.788488,10.779370`, expanded by
500 m in the net's projected coordinate system. The projection is UTM zone 48N from the net's
`projParameter`, with the retained `netOffset` applied to produce SUMO-local metres. The broad
WGS84 source-search envelope is
`west_lon,south_lat,east_lon,north_lat = 106.6859047,10.6877395,106.7935951,10.7844626`.

This is intentionally distinct from the earlier Overpass bbox
`south_lat,west_lon,north_lat,east_lon = 10.705,106.695,10.775,106.780`. That earlier bbox misses
the retained net's western and eastern edges and most of its southern and northern extent. The
output contains full OSM area geometry for every selected feature; polygons are not clipped to
either bbox or to the net boundary.

Libosmium assembled closed way areas and relation multipolygons with their member-node locations.
The source-wide pass reported 1,248,986 building area callbacks; after excluding `building=no`,
invalid/unavailable area geometry, and areas outside the expanded ROI, the output has 9,807 valid
features: 9,768 ways and 39 relations. Six source area geometries could not be used. These are
polygonable OSM area features, not a census of every element tagged `building`; open, incomplete,
or otherwise non-area elements are not counted as footprint polygons. OSM coverage can be
incomplete or stale.

Of the 9,807 features, 7,920 intersect the retained net boundary; 7,834 are fully inside it, and
86 cross or extend beyond it. Another 1,887 intersect the 500 m margin only. The complete source
geometry remains in each output feature, including parts outside the net boundary and ROI.

## Road and junction clearance QA

Each footprint was projected to SUMO-local coordinates and checked against lane corridors formed
from each SUMO lane shape buffered by half its lane width plus 0.5 m. Junction envelopes use the
SUMO junction polygon buffered by 2 m. The check found 1,576 footprint overlaps with lane
corridors and 549 with valid junction envelopes, affecting 1,677 unique footprints. These are
source-geometry overlaps to review; the extractor flags them and does not move, trim, or reject the
footprints.

This clearance result is **partial**. The net contains 17,866 junction elements: 9,324 had valid
polygon shapes used for envelope checks, 5,113 had no shape, and 3,429 had invalid shapes. All
8,542 missing or invalid junction shapes are explicitly unverified. Twenty-four lane shapes were
also invalid and excluded. No `buffer(0)` or other topology repair was applied. Therefore, the
1,677 reported overlaps are confirmed conflicts against analyzed geometry, while the remaining
features do not have a complete clearance certificate. The road/junction geometry is a QA
reference, not an authoritative property boundary.

The nearest distance fields in the artifacts measure footprint-to-lane-corridor or
footprint-to-valid-junction-envelope distance. They do not identify an entrance or a walkable path
to a building. A separate preliminary review of the pre-existing 1,087 illustrative placement
sites reported 80 site-circle/junction intersections affecting 79 unique sites; that review did
not filter invalid junction polygons, so it is context only and is not used as a validated
clearance result here.

## Artifacts and reproducibility

The versioned outputs are in the ignored local directory
`artifacts/tmp/district7_building_footprints_geofabrik_20260929/`:

- `district7_building_footprints_geofabrik_20260929.wgs84.geojson` — 9,807 full source geometries
  in EPSG:4326; SHA-256 `cdd81369136fc0f28355aec346b0722c94de74cb187e97577b77ee97314bd8b2`.
- `district7_building_footprints_geofabrik_20260929.sumo_xy.json` — the same 9,807 geometries in
  the retained SUMO local-metre coordinate system; SHA-256
  `465e47f094c483b5febd4b3f2f0ce883a526e9b4889bea73719ccb963556f130`.
- `district7_building_footprints_geofabrik_20260929.qa.json` — coverage, boundary, road-clearance,
  and limitation counts; SHA-256
  `189f1e748e23965e4980d0b6a7fd927332f7d847eaa11fb069ac39f0dc66a5ea`.
- `district7_building_footprints_geofabrik_20260929.manifest.json` — source/header/license, ROI,
  dependency and artifact hashes, method, and exact command; SHA-256
  `307df339bffa888d93fcc9ea5f52c24d5138c5d1d1d9f69882d204ad6feff7a7`.

The new source extractor is `scripts/maps/extract_building_footprints_geofabrik.py`. It uses
ephemeral `osmium`, `shapely`, and `pyproj` packages and refuses to reuse an existing output
directory. From PowerShell, rerun with:

```powershell
uv run --no-project --python 3.12 --with osmium==4.3.1 --with shapely==2.1.2 --with pyproj==3.8.0 `
  python scripts/maps/extract_building_footprints_geofabrik.py `
  --source-pbf artifacts/tmp/district7_geofabrik_vietnam_260701/vietnam-260701.osm.pbf `
  --retained-net simulation_projects/map_intake/02_prepared_sources/district7_osm_seed_20260702/district7_seed.net.xml `
  --output-dir artifacts/tmp/district7_building_footprints_geofabrik_20260929 `
  --margin-m 500 --lane-clearance-m 0.5 --junction-clearance-m 2
```

The retained net and semantic overlay were not changed; their verified SHA-256 hashes remain
`80637f09674799490eecfcd9ae1c9abe3f795795350ca3b61e8aa53d4d1f33e0` and
`9f596884721a3ccc956a929feabc83419816d9279a805ceb63a1b2edb331183a`. The existing visual
placement input was also left untouched (SHA-256
`61d6ff3f469df63ec2b2d60f6fbc4f219f35b5b42ca8d0065cdb87b379516542`).
