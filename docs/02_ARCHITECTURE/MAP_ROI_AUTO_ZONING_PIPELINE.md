# Map → ROI → Auto-Zoning → Road Cleanup Pipeline

This pipeline prepares any real-map ROI without editing the full source map.

```text
full OSM/SUMO map
→ polygon ROI config
→ OSM tag zoning + point-tag buffers
→ neutral background fill zone
→ road classification / review flags
→ generated semantic overlay
→ prepared SUMO ROI net when requested
→ generated renderer-neutral preview data
→ QA report
```

## Design rules

- The full OSM/SUMO source remains immutable.
- ROI selection is polygon-only. Rectangular ROI is not a supported production workflow.
- ROI artifacts are generated into an output directory.
- Auto-zoning is the default; manual editing is review/override only.
- The pipeline should create many micro-zones, then group them for story/demand.
- Untagged land is covered by a `neutral` background zone so the renderer has semantic coverage,
  but this zone has `demand_enabled = false` and must not generate traffic flows.
- Small point tags such as school, hospital, market, parking, bus station, or nightlife POIs are
  expanded into approximate local polygon buffers. This makes them usable for rendering, flow
  anchoring, and public-finance interpretation instead of leaving them as invisible points.
- Small roads inside zones are flagged first; they are not deleted automatically.
- SUMO remains the source of truth for road/lane geometry.
- The planned Unreal visual layer renders roads from the prepared SUMO geometry and renders buildings symbolically from zone
  assets, not from thousands of real OSM buildings.

## Zone taxonomy v1

```text
neutral
residential
commercial
market_retail
education
healthcare
industrial
port_logistics
transport_hub
public_service
nightlife
gateway
mixed
```

The first implementation maps OSM tags such as `landuse`, `amenity`, `industrial`,
`public_transport`, `shop`, `office`, `building`, `tourism`, and `leisure` to this taxonomy.

`neutral` is special: it is a render/semantic background layer, not a demand source and not a
policy-impact zone by itself.

## Road classification v1

```text
keep_simulation
keep_render_only
zone_internal_service
pedestrian_only
review_required
drop_from_simulation_candidate
```

V1 is conservative about cleanup: it flags risky roads for review instead of deleting them
automatically. When `--clip-sumo-net` is used, SUMO net clipping follows the reviewed ROI polygon.

## CLI

Dry-run the template without requiring map files:

```powershell
uv run python scripts/maps/prepare_roi.py `
  --config simulation_projects/map_intake/templates/roi_config.template.json `
  --output-root artifacts/tmp/roi_template_smoke `
  --dry-run
```

Run on a real ROI config:

```powershell
uv run python scripts/maps/prepare_roi.py `
  --config simulation_projects/map_intake/roi_configs/<roi>.json `
  --output-root artifacts/tmp/<roi> `
  --clip-sumo-net
```

The generated files are:

- `semantic_overlay.generated.json`
- `road_review.generated.json`
- `render_preview.generated.json`
- `qa_report.json`
- `qa_report.md`
- `<roi>.prepared.net.xml` when `--clip-sumo-net` is used

## Current limitation

This task implements polygon ROI preparation and polygon-based SUMO net clipping. It still does not
execute destructive road cleanup decisions automatically; road cleanup remains review-first.
