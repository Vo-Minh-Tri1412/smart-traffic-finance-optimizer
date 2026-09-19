# Shared visual source assets

Engine-neutral GLB models and PNG textures preserved for Unreal import. This is not a simulator,
dataset, or UE catalog. Curated UE Data Assets will reference imported packages under the design in
[Unreal asset pipeline](../docs/02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md).

The existing starter models/textures are recorded by the original project as Kenney CC0 assets.
Keep source/attribution metadata when importing or adding assets; verify redistribution rights for
new downloads. Legacy import metadata has been removed; source GLB/PNG bytes are preserved.
Credit Kenney / kenney.nl in public presentations. These stylized assets do not by themselves meet
the selected semi-realistic demo quality target.

Subfolders cover vehicles, buildings, traffic lights, street furniture, roads, materials, textures,
intersections, cameras, weather and UI. Empty categories reserve asset intake locations, not
implemented features. Physical dimensions, pivots and orientation need validation on import.

Store SUMO/OSM inputs in the map intake workspace; datasets/models/renders in DVC/Drive-backed
artifact locations. Small licensed source assets may remain in Git; large packs use DVC.
Curated UE packages follow the repository's Git LFS attributes.
