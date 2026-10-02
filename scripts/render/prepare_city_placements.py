"""Place illustrative visual sites inside the retained road-clipped overlay.

The output is a renderer-neutral placement input, not surveyed building geometry,
facility capacity or travel demand. Asset selection remains owned by Unreal.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_quantum_hvtc.simulation.maps import (  # noqa: E402
    load_semantic_overlay,
    load_sumo_net_index,
    load_sumo_project,
)
from ai_quantum_hvtc.simulation.maps.source import sha256_file  # noqa: E402

DEFAULT_PROJECT = ROOT / "simulation_projects/map_intake/district7.project.json"
DEFAULT_PROFILE = ROOT / "render_unreal/Config/city_placement.v2.json"
Point = tuple[float, float]


def _inside(point: Point, polygon: tuple[Point, ...]) -> bool:
    x, y = point
    hit = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def _clearance(point: Point, polygon: tuple[Point, ...]) -> float:
    x, y = point
    best = math.inf
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        fraction = (
            max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq)) if length_sq else 0.0
        )
        px, py = ax + fraction * dx, ay + fraction * dy
        best = min(best, math.hypot(x - px, y - py))
    return best


def _scanline_candidates(polygon: tuple[Point, ...], y: float) -> list[Point]:
    cuts = sorted(
        ax + (y - ay) * (bx - ax) / (by - ay)
        for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1], strict=True)
        if (ay <= y < by) or (by <= y < ay)
    )
    return [
        ((left + right) * 0.5, y)
        for left, right in zip(cuts[::2], cuts[1::2], strict=True)
        if right > left
    ]


def _representative_point(
    polygon: tuple[Point, ...], centroid: Point, minimum_clearance: float
) -> tuple[Point, float] | None:
    if _inside(centroid, polygon):
        centroid_clearance = _clearance(centroid, polygon)
        if centroid_clearance >= minimum_clearance:
            return centroid, centroid_clearance

    ys = [point[1] for point in polygon]
    low, high = min(ys), max(ys)
    best: tuple[Point, float] | None = None
    for index in range(1, 32):
        y = low + (high - low) * index / 32
        for candidate in _scanline_candidates(polygon, y):
            if not _inside(candidate, polygon):
                continue
            score = _clearance(candidate, polygon)
            if best is None or score > best[1]:
                best = candidate, score
    if best is None:
        # A very narrow polygon can fall between regular scanlines. A midpoint
        # between successive vertex heights crosses a non-empty simple polygon.
        unique_ys = sorted(set(ys))
        for lower, upper in zip(unique_ys, unique_ys[1:], strict=False):
            if upper - lower <= 1e-9:
                continue
            for candidate in _scanline_candidates(polygon, (lower + upper) * 0.5):
                if not _inside(candidate, polygon):
                    continue
                score = _clearance(candidate, polygon)
                if best is None or score > best[1]:
                    best = candidate, score
    return best if best is not None and best[1] >= minimum_clearance else None


def _area(polygon: tuple[Point, ...]) -> float:
    return (
        abs(
            sum(
                ax * by - bx * ay
                for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1], strict=True)
            )
        )
        * 0.5
    )


def _longest_edge_heading(polygon: tuple[Point, ...]) -> float:
    longest = -1.0
    heading = 0.0
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq > longest:
            longest = length_sq
            heading = math.degrees(math.atan2(dy, dx)) % 180.0
    return heading


def _positive_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return number


def _profile(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") not in {
        "city_placement_profile.v1",
        "city_placement_profile.v2",
    }:
        raise ValueError("unsupported city placement profile")
    if data.get("purpose") != "illustrative_visual_only":
        raise ValueError("city placement profile must explicitly remain illustrative")
    for key in ("building_zone_types", "landscape_zone_types"):
        value = data.get(key)
        if (
            not isinstance(value, list)
            or (
                not value
                and (
                    key == "building_zone_types"
                    or data["schema_version"] == "city_placement_profile.v1"
                )
            )
            or any(not isinstance(v, str) or not v for v in value)
        ):
            raise ValueError(f"{key} must be a valid string list")
        if len(set(value)) != len(value):
            raise ValueError(f"{key} contains duplicate zone types")
    ignored = data.get("ignored_zone_types", [])
    if data["schema_version"] == "city_placement_profile.v2":
        if (
            not isinstance(ignored, list)
            or not ignored
            or any(not isinstance(value, str) or not value for value in ignored)
        ):
            raise ValueError("ignored_zone_types must be an explicit non-empty string list")
    elif ignored:
        raise ValueError("ignored_zone_types is only supported in placement profile v2")
    if len(set(ignored)) != len(ignored):
        raise ValueError("ignored_zone_types contains duplicate zone types")
    data["ignored_zone_types"] = ignored
    if set(data["building_zone_types"]) & set(data["landscape_zone_types"]):
        raise ValueError("building and landscape zone types overlap")
    if set(ignored) & (set(data["building_zone_types"]) | set(data["landscape_zone_types"])):
        raise ValueError("ignored zone types overlap visual placement types")
    for key in (
        "building_min_area_m2",
        "building_min_clearance_m",
        "landscape_min_area_m2",
        "landscape_min_clearance_m",
        "max_building_footprint_radius_m",
        "max_landscape_footprint_radius_m",
    ):
        data[key] = _positive_number(data.get(key), key)
    return data


def prepare(project_path: Path, profile_path: Path) -> dict[str, Any]:
    project = load_sumo_project(project_path)
    net_index = load_sumo_net_index(project.source.net_path)
    overlay = load_semantic_overlay(project.overlay_path, net_index)
    if overlay.schema_version != "roi_semantic_overlay.v2":
        raise ValueError("city placement requires the retained roi_semantic_overlay.v2")
    profile = _profile(profile_path)
    known_types = {zone.zone_type for zone in overlay.zones.values()}
    configured_types = (
        set(profile["building_zone_types"])
        | set(profile["landscape_zone_types"])
        | set(profile["ignored_zone_types"])
    )
    if known_types - configured_types:
        raise ValueError(
            f"placement profile omits zone types: {sorted(known_types - configured_types)}"
        )

    placements: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for zone in sorted(overlay.zones.values(), key=lambda item: item.zone_id):
        if zone.zone_type in profile["ignored_zone_types"]:
            skipped[f"{zone.zone_type}_visual_omitted"] += 1
            continue
        kind = "building" if zone.zone_type in profile["building_zone_types"] else "landscape"
        area_threshold = profile[f"{kind}_min_area_m2"]
        clearance_threshold = profile[f"{kind}_min_clearance_m"]
        radius_cap = profile[f"max_{kind}_footprint_radius_m"]
        coordinates = zone.geometry.get("coordinates")
        if not isinstance(coordinates, list):
            raise ValueError(f"{zone.zone_id}: polygon coordinates are unavailable")
        polygon = tuple((float(p[0]), float(p[1])) for p in coordinates)
        area = _area(polygon)
        if area < area_threshold:
            skipped[f"{kind}_area_below_threshold"] += 1
            continue
        raw_centroid = zone.raw.get("centroid")
        if not isinstance(raw_centroid, list) or len(raw_centroid) != 2:
            raise ValueError(f"{zone.zone_id}: centroid is unavailable")
        centroid = (float(raw_centroid[0]), float(raw_centroid[1]))
        site = _representative_point(polygon, centroid, clearance_threshold)
        if site is None:
            skipped[f"{kind}_clearance_below_threshold"] += 1
            continue
        point, clearance = site
        if not _inside(point, polygon):
            raise ValueError(f"{zone.zone_id}: selected point lies outside source polygon")
        placements.append(
            {
                "id": f"{zone.zone_id}_visual_1",
                "source_zone_id": zone.zone_id,
                "source_element_id": zone.source_element_id,
                "zone_type": zone.zone_type,
                "kind": kind,
                "x_m": point[0],
                "y_m": point[1],
                "heading_degrees": _longest_edge_heading(polygon),
                "source_polygon_area_m2": area,
                "source_clearance_m": clearance,
                "max_footprint_radius_m": min(clearance * 0.8, radius_cap),
                "source_has_building_tag": "building" in zone.source_tags,
                "basis": "illustrative_site_within_road_clipped_semantic_polygon",
            }
        )
    if not placements:
        raise ValueError("no illustrative visual sites survived the placement profile")
    return {
        "schema_version": "city_visual_placements.v1",
        "purpose": "illustrative_visual_only",
        "project_id": project.project_id,
        "overlay_id": overlay.overlay_id,
        "coordinate_system": "sumo_xy_meters",
        "local_origin": {"x": net_index.bounds_min[0], "y": net_index.bounds_min[1]},
        "source_net_sha256": sha256_file(project.source.net_path),
        "source_overlay_sha256": sha256_file(project.overlay_path),
        "placement_profile_sha256": sha256_file(profile_path),
        "zone_count": len(overlay.zones),
        "placement_count": len(placements),
        "skipped_by_reason": dict(sorted(skipped.items())),
        "placements": placements,
        "limitations": [
            "Sites are visual approximations, not surveyed building footprints or structures.",
            "Visual orientation follows each polygon's longest edge, not a surveyed facade.",
            "The source overlay says polygons were clipped away from roads; "
            "this step does not revalidate that clipping.",
            "No facility capacity, occupancy, demand, or trip count is derived from these sites.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.project, args.profile)
        path = args.output.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[FAIL] Could not prepare city visual placements: {exc}")
        return 1
    print(f"[OK] {result['placement_count']} illustrative sites written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
