# Render asset intake

Unreal is the active renderer. Shared source GLB/PNG assets live in render_assets/ at repository root.
They are not yet a complete native UE catalog. The current replay actor still uses canonical
cuboid proxies; [asset pipeline](../02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md) describes planned
Data Assets, attachment slots, physical validation and scene profiles.

## Needed assets

- P0: sidewalk/curb straight, corner and curb-ramp modules.
- P0: simple and arterial street-light poles; signal heads with separately controllable lenses.
- P0: bus-stop shelter, sign, bench and route board; the reserved source folder is empty.
- P1: guardrails, bollards, separators, utility cabinets and urban furniture.

Each asset needs source/license, real envelope, forward axis, ground pivot, material/texture slots
and LOD choices. Register it in the future UE catalog rather than branching placement code on paths.
Imported buildings are illustrative unless footprints/heights are validated; they do not establish
facility capacity or economic value. Preserve source bytes and attribution during import.
