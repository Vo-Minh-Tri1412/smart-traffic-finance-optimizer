# Shared visual source assets

Engine-neutral GLB models and PNG textures preserved for Unreal import. This is not a simulator,
dataset, or UE catalog. Curated UE Data Assets will reference imported packages under the design in
[Unreal asset pipeline](../docs/02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md).

The existing starter models/textures are recorded by the original project as Kenney CC0 assets.
They remain for the historical `Demo092` scene and are **not selected for the current city scene**.
Keep source/attribution metadata when importing or adding assets; verify redistribution rights for
new downloads. Legacy import metadata has been removed; source GLB/PNG bytes are preserved.
Credit Kenney / kenney.nl if the historical scene is presented.

The active city art intake now uses the CC0 [Poly Haven](https://polyhaven.com/license) selection in
`render_unreal/Config/city_asset_sources.v1.json`. `scripts/render/fetch_city_assets.py` records exact
download URLs, API file checksums and local SHA-256 in an ignored artifact manifest; the large source
files and imported UE packages are generated locally. The API-based intake credits Poly Haven as
required by its [API terms](https://polyhaven.com/our-api). Importing assets does not by itself prove
the rendered city meets the visual or performance target.

Subfolders cover vehicles, buildings, traffic lights, street furniture, roads, materials, textures,
intersections, cameras, weather and UI. Empty categories reserve asset intake locations, not
implemented features. Physical dimensions, pivots and orientation need validation on import.

Store SUMO/OSM inputs in the map intake workspace; datasets/models/renders in DVC/Drive-backed
artifact locations. Small licensed source assets may remain in Git; large packs use DVC.
Curated UE packages follow the repository's Git LFS attributes.
