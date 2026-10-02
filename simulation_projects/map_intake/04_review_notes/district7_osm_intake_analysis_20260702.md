# District 7 OSM intake analysis — 2026-07-02

This is an infrastructure-readiness note for using a real OpenStreetMap seed instead of hand-authoring
the full road network in Unreal.

The goal is **not** to trim the map into another toy grid. The goal is to understand what the
project must support if OSM/SUMO becomes the primary map source and Unreal becomes the visual and
semantic authoring layer.

## Source

- Source: OpenStreetMap via Overpass API.
- Seed region: approximate District 7 / Tan Thuan / Phu My Hung bounding box.
- Bounding box used: south `10.705`, west `106.695`, north `10.775`, east `106.780`.
- Query file: `simulation_projects/map_intake/01_raw_sources/district7_osm_seed_20260702/district7_overpass_query.overpassql`.
- Raw OSM file: `simulation_projects/map_intake/01_raw_sources/district7_osm_seed_20260702/district7_seed.osm`.
- SUMO net file: `simulation_projects/map_intake/02_prepared_sources/district7_osm_seed_20260702/district7_seed.net.xml`.

Raw/prepared map artifacts are ignored by Git by design. This note is the committed/reviewable
handoff; the large OSM/SUMO files should stay local or move to Drive/DVC later.

## Import result

The raw OSM seed downloaded and converted successfully with SUMO `netconvert`.

### OSM raw stats

- Raw `.osm` size: about `6.28 MB`.
- OSM nodes: `43,926`.
- OSM ways: `9,958`.
- OSM relations: `3`.

Top road/transport tags observed:

- `service`: `3,773`
- `residential`: `2,629`
- `crossing`: `1,424`
- `footway`: `1,146`
- `primary`: `513`
- `tertiary`: `396`
- `traffic_signals`: `390`
- `secondary`: `378`
- `trunk`: `177`

Relevant semantic tags observed:

- amenities: `school 93`, `fuel 30`, `marketplace 18`, `hospital 17`, `clinic 14`,
  `university 12`, `college 6`, `bus_station 3`.
- landuse: `residential 164`, `industrial 30`, `commercial 24`, `retail 6`.

This is a strong sign that District 7 can support the public-finance story: residential zones,
industry/logistics, schools, commerce, medical services, and bus-related infrastructure are all
present in the source data.

### SUMO conversion stats

SUMO `netconvert` succeeded with a light import profile:

- SUMO `.net.xml` size: about `51.65 MB`.
- traffic-light junctions: `169`.
- priority junctions: `6,125`.
- right-before-left junctions: `1,890`.
- dead-end junctions: `4,889`.
- internal junctions: `4,793`.
- SUMO edges: `82,133`, including `53,132` internal edges.
- SUMO lanes: `88,163`.

This is much larger than the tiny committed test fixture. It is a real-scale network, so the project
must stop assuming that a district map is small enough to inspect or control manually.

### SUMO smoke run

A routing smoke test using SUMO `randomTrips.py` generated `100` random trips and SUMO ran them
for `600` seconds.

Observed from the smoke output:

- inserted vehicles: `100`.
- completed trips by 600s: `48`.
- running at final step: `52`.
- collisions: `0`.
- teleports: `0`.
- average completed-trip duration: `306.44 s`.
- average completed-trip waiting time: `26.83 s`.
- average completed-trip time loss: `75.45 s`.
- average completed-trip route length: `4,741.19 m`.

This is only a routability smoke test. It is not a realistic demand model.

## Main import warnings

The map is usable, but current infrastructure is not ready to treat this as the official demo map.
Important warning classes from `netconvert`:

- non-numeric `maxspeed:type = urban`;
- unknown lane-use specifiers;
- many junction clusters were reduced or not joined;
- many turnarounds were ambiguous;
- sharp turns and very small turning radii;
- disconnected incoming/outgoing lanes;
- traffic-light minor greens that suggest missing or imperfect turn-lane modeling;
- OSM traffic-signal nodes (`390`) do not map one-to-one to SUMO traffic-light junctions (`169`).

These are normal for OSM import. The answer should not be “delete most of the map”. The answer
should be better intake, indexing, validation, semantic overlay, and candidate selection.

## Infrastructure upgrades needed

### 1. Add OSM/SUMO-first map source support

Current backend is still centered around `district_spec.json` as the road source. With OSM, the
road source should often be:

```text
OSM raw extract
-> SUMO netconvert
-> SUMO .net.xml as geometry/source of truth
-> semantic overlay for zones, candidates, flows, public finance
```

Needed abstraction:

- `DistrictSpecSource`: current JSON-authored map.
- `OsmMapSource`: raw OSM + netconvert profile.
- `SumoNetSource`: existing `.net.xml` accepted directly by simulation/replay tooling.

The pipeline should not require converting all OSM geometry back into a hand-authored
`district_spec`.

### 2. Add map intake profiles

Instead of one hard-coded `netconvert` command, define import profiles:

- `district7_full_road_seed`: keep most drivable roads for inspection.
- `district7_simulation_core`: keep simulation-relevant roads but avoid footway/path noise.
- `district7_tls_focus`: preserve traffic-light and major-road fidelity for RL/control.

Profiles should be versioned and recorded with:

- bbox;
- Overpass query;
- netconvert arguments;
- SUMO version;
- generated file checksums;
- source attribution.

### 3. Keep semantic overlay separate from map geometry

OSM gives road geometry and some POI/landuse hints. It does not give the project’s policy model.

Create a separate overlay format for:

- zones: hospital, school, industry, residential, commercial, nightlife/logistics if needed;
- spawn/destination groups;
- candidate investment intersections;
- public-value labels;
- scenario demand multipliers;
- notes/caveats.

Unreal can become the editor for this overlay, but should not be forced to redraw the OSM road
network manually.

### 4. Add network indexing and candidate selection

With `169` SUMO traffic lights, the system needs a way to select a manageable controlled subset:

- traffic-light ranking by connectivity;
- proximity to zones;
- route-flow centrality;
- queue/time-loss metrics from baseline SUMO runs;
- public-value exposure, such as school/hospital/industry access.

This directly supports the third model / public-finance optimizer: the model should choose which
traffic lights to upgrade under a budget, not assume all lights are upgraded.

### 5. Add realistic demand generation

`randomTrips.py` proves the map can route vehicles, but it is not enough for the project.

Needed demand layer:

- zone-to-zone OD generation;
- time windows: morning, afternoon, logistics, evening, incident;
- vehicle mix: motorbike, car, bus, truck, emergency;
- flow multipliers by landuse/amenity;
- route validation and route cache.

This layer should be parameterized by economics/CS decisions, not baked into OSM.

### 6. Upgrade SUMO adapter to consume external SUMO net

The current project can generate SUMO artifacts from its own spec. For OSM maps, it also needs:

- run SUMO from an existing `.net.xml`;
- attach route files generated separately;
- parse tripinfo/summary/edge/lane/fcd outputs into the existing `SimulationResult`;
- keep `district_spec` optional for road geometry and required only for semantic overlays if needed.

### 7. Upgrade Unreal replay to render SUMO net geometry first

For OSM, Unreal should not draw roads from a hand-authored toy spec. It should import:

- lane shapes from `district.net.xml`;
- junction polygons;
- coordinate bounds and offsets;
- vehicle positions from FCD/trace in the same coordinate system.

This prevents coordinate-system mismatches such as vehicles visually drifting away from roads.

### 8. Add artifact/data management

The generated `.net.xml` alone is about `51.65 MB`. Full traces and training logs will be larger.

Needed:

- keep raw/prepared maps ignored in Git;
- store reviewable provenance notes in Git;
- optionally store raw/prepared data in Google Drive or DVC;
- define which artifacts are local-only, Drive-shared, or commit-safe.

### 9. Add OSM import QA report

Every imported map should produce a small QA report:

- counts of OSM nodes/ways/amenities/landuse;
- SUMO junction/edge/lane/TLS counts;
- disconnected-edge warning summary;
- traffic-light mismatch summary;
- smoke simulation result;
- whether the map is ready for baseline, Unreal replay, or RL.

### 10. Remove the synthetic project-map folder

The repository should not keep a synthetic district under `simulation_projects/` as if it were a
candidate product map. Keep only a tiny neutral fixture under `tests/fixtures/specs/` for CI and
contract tests. Real candidate maps should enter through OSM/SUMO intake and DVC-managed artifacts.

## Recommendation

Implement next:

```text
045_osm_sumo_first_pipeline
```

Scope:

1. add OSM intake config/profile files;
2. add a Python wrapper for Overpass download + netconvert;
3. produce an import QA JSON/Markdown report;
4. allow `simulate run` or a new map-intake command to accept an existing SUMO `.net.xml`;
5. add Unreal/SUMO geometry-readiness notes, but do not build the whole Unreal overlay editor yet.

This keeps the real map mostly intact and upgrades the project infrastructure around it.
