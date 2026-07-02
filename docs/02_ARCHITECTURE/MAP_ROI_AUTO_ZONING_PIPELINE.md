# Map → ROI → Auto-Zoning → Road Cleanup Pipeline

This pipeline prepares any real-map ROI without editing the full source map.

```text
full OSM/SUMO map
→ ROI config
→ OSM tag zoning
→ road classification / review flags
→ generated semantic overlay
→ generated Godot preview data
→ QA report
```

## Design rules

- The full OSM/SUMO source remains immutable.
- ROI artifacts are generated into an output directory.
- Auto-zoning is the default; manual editing is review/override only.
- The pipeline should create many micro-zones, then group them for story/demand.
- Small roads inside zones are flagged first; they are not deleted automatically.
- SUMO remains the source of truth for road/lane geometry.
- Godot renders roads from the prepared SUMO geometry and renders buildings symbolically from zone
  assets, not from thousands of real OSM buildings.

## Zone taxonomy v1

```text
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
`public_transport`, `shop`, `office`, `tourism`, and `leisure` to this taxonomy.

## Road classification v1

```text
keep_simulation
keep_render_only
zone_internal_service
pedestrian_only
review_required
drop_from_simulation_candidate
```

V1 is conservative: it flags risky roads for review instead of modifying the SUMO net. A later
netconvert step can consume the review decisions to produce a truly clipped/cleaned ROI net.

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
  --output-root artifacts/tmp/<roi>
```

The generated files are:

- `semantic_overlay.generated.json`
- `road_review.generated.json`
- `godot_preview.generated.json`
- `qa_report.json`
- `qa_report.md`

## Current limitation

This task implements review-safe ROI preparation. It does not yet execute a destructive road cleanup
or final SUMO net clipping. That should be added only after the review rules are accepted on a small
ROI.
