# Render asset intake

## Current road asset pipeline

Roadside assets are registered as `RoadsidePropEntry` resources with a target size in metres. Godot
measures the instantiated GLB bounds, scales it to that physical envelope, and places it outside the
visual lane surface. The initial catalog uses the available directional sign, large/small trees and
planter assets. Traffic signals remain a separate calibrated layer.

## Assets still needed from the asset search

These are visual improvements, not blockers for road geometry or zone placement:

1. **P0 — sidewalk/curb modules:** straight, corner, curb-ramp and drainage variants.
2. **P0 — street lights:** a simple pole, a double-arm arterial pole and a short residential pole.
3. **P0 — bus-stop kit:** shelter, pole/sign, bench and route board. The current `bus_stops/`
   asset folder is empty.
4. **P1 — road safety kit:** guardrail, bollard, lane separator/delineator and non-construction
   barrier.
5. **P1 — urban furniture:** bin, bench, utility cabinet and parking sign.

Each GLB should have a documented real-world envelope (`width_m`, `height_m`, `depth_m`) and a
ground-aligned origin where possible. It can then be added to `RoadStyleCatalog.tres` without
changing road-placement code.
