"""Freeze source geometry for the editable Unreal urban layer; no art settings here."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GEOMETRY = ROOT / "render_unreal/CitySources/district7_geometry_manifest.v1.json"
DEFAULT_FOOTPRINTS = (
    ROOT / "artifacts/tmp/district7_building_footprints_geofabrik_20260929/"
    "district7_building_footprints_geofabrik_20260929.sumo_xy.json"
)
DEFAULT_OUTPUT = ROOT / "render_unreal/CitySources/urban_geometry.v1.json"


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def roof_geometry(polygon: Any) -> list[list[list[float]]]:
    from shapely import constrained_delaunay_triangles

    triangles = constrained_delaunay_triangles(polygon)
    result = []
    area = 0.0
    for triangle in triangles.geoms:
        if not polygon.covers(triangle):
            raise ValueError("Roof triangle extends beyond the source footprint")
        points = list(triangle.exterior.coords)[:3]
        if triangle.area > 1e-8:
            result.append([[float(x), float(y)] for x, y in points])
            area += triangle.area
    if abs(area - polygon.area) > max(0.0001, polygon.area * 1e-7):
        raise ValueError("Roof triangulation does not preserve footprint area/holes")
    return result


def prepare(geometry_path: Path, footprints_path: Path) -> dict[str, Any]:
    from shapely.geometry import box, shape
    from shapely.geometry.polygon import orient

    manifest = json.loads(geometry_path.read_text(encoding="utf-8"))
    net = Path(manifest["net_xml"])
    if not net.is_absolute():
        net = geometry_path.parent / net
    net = net.resolve(strict=True)
    net_hash = hash_file(net)
    if manifest.get("source_net_sha256") != net_hash:
        raise ValueError("SUMO net hash differs from its retained geometry manifest")
    footprints = json.loads(footprints_path.read_text(encoding="utf-8"))
    if footprints.get("schema_version") != "district7_visual_building_footprints.v1":
        raise ValueError("Unsupported source footprint schema")
    if footprints.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("Footprints must use the retained SUMO XY coordinate system")
    bounds = manifest["bounds"]
    region = box(bounds["min_x"], bounds["min_y"], bounds["max_x"], bounds["max_y"])
    exclusions: list[list[float]] = []
    roads: list[dict[str, Any]] = []
    for _, edge in ET.iterparse(net, events=("end",)):
        if edge.tag != "edge":
            continue
        internal = edge.get("function") == "internal" or edge.get("id", "").startswith(":")
        lanes = []
        for lane in edge.findall("lane"):
            points = [
                [float(v) for v in token.split(",")[:2]] for token in lane.get("shape", "").split()
            ]
            width = float(lane.get("width", "3.2"))
            if len(points) < 2 or not math.isfinite(width) or width <= 0:
                continue
            if not all(math.isfinite(value) for point in points for value in point):
                raise ValueError("Non-finite SUMO lane coordinates")
            for a, b in zip(points, points[1:], strict=False):
                if math.dist(a, b) > 1e-7:
                    exclusions.append([*a, *b, width])
            permitted = lane.get("allow", "")
            pedestrian_only = bool(permitted) and set(permitted.split()) <= {"pedestrian"}
            if not internal and not pedestrian_only:
                lanes.append(
                    {
                        "id": lane.get("id"),
                        "index": int(lane.get("index", "0")),
                        "width": width,
                        "points": points,
                    }
                )
        if lanes:
            roads.append(
                {
                    "id": edge.get("id"),
                    "from": edge.get("from", ""),
                    "to": edge.get("to", ""),
                    "lanes": sorted(lanes, key=lambda x: x["index"]),
                }
            )
        edge.clear()
    buildings = []
    counts: Counter[str] = Counter()
    for feature in footprints["features"]:
        properties = feature["properties"]
        counts["source_features"] += 1
        if properties.get("lane_corridor_overlap") or properties.get("junction_envelope_overlap"):
            counts["excluded_confirmed_road_overlap"] += 1
            continue
        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.is_empty:
            counts["excluded_invalid_geometry"] += 1
            continue
        if not region.covers(geometry):
            counts["excluded_not_fully_inside_retained_map"] += 1
            continue
        polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
        for part_index, raw in enumerate(polygons):
            polygon = orient(raw, sign=1.0)
            if polygon.area < 2:
                counts["excluded_tiny_part"] += 1
                continue
            rings = [polygon.exterior, *polygon.interiors]
            buildings.append(
                {
                    "id": feature["id"],
                    "part": part_index,
                    "building_tag": properties.get("building", "yes"),
                    "name": properties.get("osm_tags", {}).get("name", ""),
                    "bounds": list(polygon.bounds),
                    "rings": [[[float(x), float(y)] for x, y in ring.coords] for ring in rings],
                    "roof_triangles": roof_geometry(polygon),
                    "source_area_m2": polygon.area,
                }
            )
        counts["accepted_source_features"] += 1
    return {
        "schema_version": "unreal_urban_geometry.v1",
        "coordinate_system": "sumo_xy_meters",
        "source_net_sha256": net_hash,
        "source_footprints_sha256": hash_file(footprints_path),
        "source_net_path": str(net),
        "source_footprints_path": str(footprints_path.resolve()),
        "local_origin": manifest["local_origin"],
        "bounds": bounds,
        "roads": roads,
        "road_exclusion_segments": exclusions,
        "buildings": buildings,
        "counts": dict(counts),
        "limitations": [
            "Building heights are not assigned here; native Editor profiles own them.",
            "OSM footprints can be incomplete/stale; no survey completeness claim.",
            "Non-overlap is not a full clearance certificate where junction geometry is missing.",
            "Marking styles, sidewalks and generated landscaping are visual assumptions.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--footprints", type=Path, default=DEFAULT_FOOTPRINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to replace frozen source geometry: {args.output}")
    data = prepare(args.geometry.resolve(), args.footprints.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(data, target, separators=(",", ":"), ensure_ascii=False)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": hash_file(args.output),
                "roads": len(data["roads"]),
                "building_parts": len(data["buildings"]),
                "counts": data["counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
