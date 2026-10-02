# Retained city geometry

The SUMO geometry manifest references the unchanged District 7 retained network.
urban_geometry.v1.json freezes its lane shapes and mapped building footprints for native rendering;
it is stored with Git LFS. Building height, materials, lane styling, sidewalks and greenery are
configured in Unreal Data Assets, not this source snapshot.

Footprints derive from the Geofabrik Vietnam 2026-07-01 OSM extract. Map data:
© OpenStreetMap contributors, Open Database License (ODbL); see
https://www.openstreetmap.org/copyright and https://download.geofabrik.de/asia/vietnam.html.
Input hashes and extraction limitations are embedded in the snapshot and recorded in
simulation_projects/map_intake/04_review_notes/district7_building_footprints_geofabrik_20260929.md.
No surveyed height, occupancy or demand is inferred from these footprints.

Preparation excludes confirmed road/junction overlaps and footprints outside the retained map;
unknown clearance where the SUMO source lacks usable junction geometry is still a limitation.
Regenerate with the source files present:

    uv run --with shapely python scripts/render/prepare_urban_environment.py --output <new-file.json>

The preparation tool refuses to replace an existing frozen source snapshot.
