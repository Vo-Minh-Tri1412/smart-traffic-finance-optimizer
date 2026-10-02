"""Extract complete OSM building area geometries from a local Geofabrik PBF.

The output is a renderer-neutral visual candidate layer. This command reads the
source PBF and retained SUMO net but never edits either one, the semantic overlay,
the demand configuration, or existing Unreal placement files. It preserves full
way and multipolygon geometry for selected features; it does not clip footprints
to the ROI or infer building height, occupancy, demand, capacity, or value.

Runtime packages are intentionally ephemeral for this one-off PBF task:
``uv run --no-project --python 3.12 --with osmium==4.3.1 --with shapely==2.1.2
--with pyproj==3.8.0 python ...``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import osmium
from pyproj import Transformer
from shapely import STRtree, from_wkb
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import transform, unary_union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_VERSION = "extract_building_footprints_geofabrik.v1"
OUTPUT_SCHEMA_VERSION = "district7_visual_building_footprints.v1"
QA_SCHEMA_VERSION = "district7_visual_building_footprints_qa.v1"
MANIFEST_SCHEMA_VERSION = "district7_visual_building_footprints_manifest.v1"
HASH_CHUNK_SIZE = 1024 * 1024
DEFAULT_SOURCE = (
    PROJECT_ROOT
    / "artifacts"
    / "tmp"
    / "district7_geofabrik_vietnam_260701"
    / "vietnam-260701.osm.pbf"
)
DEFAULT_NET = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "02_prepared_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.net.xml"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "artifacts" / "tmp" / "district7_building_footprints_geofabrik_20260929"
)
GEOfABRIK_PAGE = "https://download.geofabrik.de/asia/vietnam.html"
ODBL_ATTRIBUTION = "© OpenStreetMap contributors"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _assert_absent(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing artifact(s): " + ", ".join(map(str, existing))
        )


def _exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _parse_numbers(value: str, expected: int, label: str) -> tuple[float, ...]:
    try:
        numbers = tuple(float(part) for part in value.split(","))
    except ValueError as exc:
        raise ValueError(f"invalid {label}: {value!r}") from exc
    if len(numbers) != expected or not all(math.isfinite(item) for item in numbers):
        raise ValueError(f"invalid {label}: {value!r}")
    return numbers


@dataclass(frozen=True)
class NetContext:
    path: Path
    sha256: str
    original_bounds: tuple[float, float, float, float]
    projection: str
    net_offset: tuple[float, float]
    to_sumo_xy: Transformer
    to_wgs84: Transformer
    net_boundary_xy: Polygon
    search_roi_xy: Any
    search_bbox_wgs84: tuple[float, float, float, float]

    def project_geometry(self, geometry: Any) -> Any:
        offset_x, offset_y = self.net_offset

        def project(x: Any, y: Any, z: Any = None) -> Any:
            projected_x, projected_y = self.to_sumo_xy.transform(x, y)
            return projected_x + offset_x, projected_y + offset_y

        return transform(project, geometry)

    def unproject_xy(self, x: Any, y: Any, z: Any = None) -> Any:
        offset_x, offset_y = self.net_offset
        return self.to_wgs84.transform(x - offset_x, y - offset_y)


def _load_net_context(net_path: Path, margin_m: float) -> NetContext:
    if not math.isfinite(margin_m) or margin_m < 0:
        raise ValueError("margin_m must be a finite non-negative number")

    location: dict[str, str] | None = None
    with net_path.open("rb") as handle:
        for event, element in ET.iterparse(handle, events=("start",)):
            if event == "start" and element.tag == "location":
                location = element.attrib
                break
    if location is None:
        raise ValueError(f"retained SUMO net has no <location> header: {net_path}")

    original_bounds = _parse_numbers(location.get("origBoundary", ""), 4, "SUMO origBoundary")
    offset = _parse_numbers(location.get("netOffset", ""), 2, "SUMO netOffset")
    projection = location.get("projParameter", "").strip()
    if not projection or projection.lower() in {"!", "-"}:
        raise ValueError("retained SUMO net has no usable projParameter")
    west, south, east, north = original_bounds
    if not west < east or not south < north:
        raise ValueError(f"invalid SUMO origBoundary: {original_bounds}")

    forward = Transformer.from_crs("EPSG:4326", projection, always_xy=True)
    reverse = Transformer.from_crs(projection, "EPSG:4326", always_xy=True)

    def project_boundary(x: Any, y: Any, z: Any = None) -> Any:
        projected_x, projected_y = forward.transform(x, y)
        return projected_x + offset[0], projected_y + offset[1]

    net_boundary_wgs84 = box(west, south, east, north)
    net_boundary_xy = transform(project_boundary, net_boundary_wgs84)
    search_roi_xy = net_boundary_xy.buffer(margin_m, quad_segs=4)
    min_x, min_y, max_x, max_y = search_roi_xy.bounds
    roi_corners = [
        (min_x - offset[0], min_y - offset[1]),
        (min_x - offset[0], max_y - offset[1]),
        (max_x - offset[0], min_y - offset[1]),
        (max_x - offset[0], max_y - offset[1]),
    ]
    lon_lat = [reverse.transform(x, y) for x, y in roi_corners]
    search_bbox_wgs84 = (
        min(point[0] for point in lon_lat),
        min(point[1] for point in lon_lat),
        max(point[0] for point in lon_lat),
        max(point[1] for point in lon_lat),
    )
    return NetContext(
        path=net_path,
        sha256=_sha256_file(net_path),
        original_bounds=original_bounds,
        projection=projection,
        net_offset=offset,
        to_sumo_xy=forward,
        to_wgs84=reverse,
        net_boundary_xy=net_boundary_xy,
        search_roi_xy=search_roi_xy,
        search_bbox_wgs84=search_bbox_wgs84,
    )


def _parse_shape(value: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for coordinate in value.split():
        parts = coordinate.split(",")
        if len(parts) < 2:
            continue
        try:
            point = (float(parts[0]), float(parts[1]))
        except ValueError:
            continue
        if all(math.isfinite(axis) for axis in point):
            points.append(point)
    return points


def _load_road_geometry(
    net_path: Path,
    roi_xy: Any,
    lane_clearance_m: float,
    junction_clearance_m: float,
) -> tuple[list[Any], list[Any], dict[str, int]]:
    if lane_clearance_m < 0 or junction_clearance_m < 0:
        raise ValueError("lane and junction clearances must be non-negative")

    lane_corridors: list[Any] = []
    junction_envelopes: list[Any] = []
    counts = Counter()
    for _, element in ET.iterparse(net_path, events=("end",)):
        if element.tag == "lane":
            counts["lane_elements"] += 1
            points = _parse_shape(element.attrib.get("shape", ""))
            if len(points) >= 2:
                try:
                    lane = LineString(points)
                    width = float(element.attrib.get("width", "3.2"))
                    if lane.is_valid and lane.length > 0 and math.isfinite(width) and width > 0:
                        corridor = lane.buffer(
                            width / 2 + lane_clearance_m,
                            cap_style="flat",
                            join_style="mitre",
                        )
                        if corridor.intersects(roi_xy):
                            lane_corridors.append(corridor)
                    else:
                        counts["invalid_lane_geometry_count"] += 1
                except (ValueError, TypeError):
                    counts["invalid_lane_geometry_count"] += 1
            else:
                counts["lane_without_shape_count"] += 1
            element.clear()
        elif element.tag == "junction":
            counts["junction_elements"] += 1
            points = _parse_shape(element.attrib.get("shape", ""))
            if len(points) >= 3:
                try:
                    polygon = Polygon(points)
                    if polygon.is_valid and polygon.area > 0:
                        envelope = polygon.buffer(junction_clearance_m)
                        if envelope.intersects(roi_xy):
                            junction_envelopes.append(envelope)
                            counts["junction_shapes_in_roi"] += 1
                    else:
                        counts["invalid_junction_geometry_count"] += 1
                except (ValueError, TypeError):
                    counts["invalid_junction_geometry_count"] += 1
            else:
                counts["junction_without_shape_count"] += 1
            element.clear()
        elif element.tag in {"edge", "net"}:
            element.clear()
    counts["lane_corridor_count_in_roi"] = len(lane_corridors)
    counts["junction_envelope_count_in_roi"] = len(junction_envelopes)
    return lane_corridors, junction_envelopes, dict(sorted(counts.items()))


class BuildingAreaHandler(osmium.SimpleHandler):
    """Collect complete pyosmium-assembled building areas that touch the ROI."""

    def __init__(self, net: NetContext) -> None:
        super().__init__()
        self.net = net
        self.factory = osmium.geom.WKBFactory()
        self.features: list[dict[str, Any]] = []
        self.tag_values: Counter[str] = Counter()
        self.by_osm_type: Counter[str] = Counter()
        self.building_area_callback_count = 0
        self.building_no_area_count = 0
        self.invalid_or_unavailable_geometry_count = 0
        self.outside_roi_area_count = 0
        self.invalid_ids: list[str] = []

    def area(self, area: osmium.osm.Area) -> None:
        tags = {tag.k: tag.v for tag in area.tags}
        building = tags.get("building")
        if building is None:
            return
        self.building_area_callback_count += 1
        if building == "no":
            self.building_no_area_count += 1
            return

        osm_type = "way" if area.from_way() else "relation"
        osm_id = int(area.orig_id())
        self.tag_values[building] += 1
        self.by_osm_type[osm_type] += 1
        try:
            wkb = self.factory.create_multipolygon(area)
            geometry_wgs84 = from_wkb(bytes.fromhex(wkb))
            if geometry_wgs84.is_empty or not geometry_wgs84.is_valid:
                raise ValueError("OSM area geometry is empty or invalid")
            geometry_xy = self.net.project_geometry(geometry_wgs84)
            if not geometry_xy.intersects(self.net.search_roi_xy):
                self.outside_roi_area_count += 1
                return
        except (RuntimeError, ValueError, OverflowError):
            self.invalid_or_unavailable_geometry_count += 1
            self.invalid_ids.append(f"{osm_type}/{osm_id}")
            return

        self.features.append(
            {
                "osm_type": osm_type,
                "osm_id": osm_id,
                "building": building,
                "osm_tags": dict(sorted(tags.items())),
                "geometry_wgs84": geometry_wgs84,
                "geometry_sumo_xy": geometry_xy,
            }
        )


def _summarize_geometry_against_boundary(geometry: Any, boundary: Any) -> dict[str, Any]:
    intersects = geometry.intersects(boundary)
    intersection_area = geometry.intersection(boundary).area if intersects else 0.0
    tolerance = max(0.01, geometry.area * 1e-9)
    extends_outside = intersection_area > tolerance and (
        geometry.difference(boundary).area > tolerance
    )
    return {
        "intersects_retained_net_boundary": intersects,
        "crosses_or_extends_outside_retained_net_boundary": extends_outside,
        "fully_within_retained_net_boundary": boundary.covers(geometry),
        "touches_only_retained_net_boundary": intersects and intersection_area <= tolerance,
    }


def _road_qa(
    geometry: Any,
    lane_tree: STRtree | None,
    lane_corridors: list[Any],
    junction_tree: STRtree | None,
    junction_envelopes: list[Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "lane_corridor_overlap": False,
        "lane_corridor_overlap_area_m2": 0.0,
        "nearest_lane_corridor_distance_m": None,
        "junction_envelope_overlap": False,
        "junction_envelope_overlap_area_m2": 0.0,
        "nearest_junction_envelope_distance_m": None,
    }
    if lane_tree is not None:
        nearest_index = int(lane_tree.nearest(geometry))
        result["nearest_lane_corridor_distance_m"] = round(
            geometry.distance(lane_corridors[nearest_index]), 3
        )
        hits = lane_tree.query(geometry, predicate="intersects")
        if len(hits):
            hit_geometries = [lane_corridors[int(index)] for index in hits]
            overlap_area = geometry.intersection(unary_union(hit_geometries)).area
            result["lane_corridor_overlap_area_m2"] = round(overlap_area, 4)
            result["lane_corridor_overlap"] = overlap_area > 0.01
    if junction_tree is not None:
        nearest_index = int(junction_tree.nearest(geometry))
        result["nearest_junction_envelope_distance_m"] = round(
            geometry.distance(junction_envelopes[nearest_index]), 3
        )
        hits = junction_tree.query(geometry, predicate="intersects")
        if len(hits):
            hit_geometries = [junction_envelopes[int(index)] for index in hits]
            overlap_area = geometry.intersection(unary_union(hit_geometries)).area
            result["junction_envelope_overlap_area_m2"] = round(overlap_area, 4)
            result["junction_envelope_overlap"] = overlap_area > 0.01
    return result


def _load_pbf_header(source_path: Path) -> dict[str, str]:
    reader = osmium.io.Reader(str(source_path))
    try:
        header = reader.header()
        return {
            "generator": header.get("generator", ""),
            "replication_timestamp_utc": header.get("osmosis_replication_timestamp", ""),
            "replication_sequence_number": header.get("osmosis_replication_sequence_number", ""),
            "replication_base_url": header.get("osmosis_replication_base_url", ""),
            "pbf_dense_nodes": header.get("pbf_dense_nodes", ""),
            "sorting": header.get("sorting", ""),
            "header_bounds": str(header.box()),
        }
    finally:
        reader.close()


def _verify_md5(source_path: Path) -> tuple[str, str | None, str | None]:
    actual = _md5_file(source_path)
    checksum_path = source_path.with_name(source_path.name + ".md5")
    expected: str | None = None
    if checksum_path.is_file():
        match = re.search(r"\b([0-9a-fA-F]{32})\b", checksum_path.read_text(encoding="ascii"))
        if match is None:
            raise ValueError(f"could not read MD5 from checksum sidecar: {checksum_path}")
        expected = match.group(1).lower()
        if actual != expected:
            raise ValueError(
                f"PBF MD5 mismatch: expected {expected}, computed {actual} ({source_path})"
            )
    return actual, expected, _repo_path(checksum_path) if expected is not None else None


def _feature_layers(
    handler: BuildingAreaHandler,
    net: NetContext,
    lane_corridors: list[Any],
    junction_envelopes: list[Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lane_tree = STRtree(lane_corridors) if lane_corridors else None
    junction_tree = STRtree(junction_envelopes) if junction_envelopes else None
    wgs_features: list[dict[str, Any]] = []
    local_features: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    nearest_lane_distances: list[float] = []
    nearest_junction_distances: list[float] = []

    sorted_features = sorted(handler.features, key=lambda item: (item["osm_type"], item["osm_id"]))
    selected_type_counts: Counter[str] = Counter(item["osm_type"] for item in sorted_features)
    selected_building_values: Counter[str] = Counter(item["building"] for item in sorted_features)
    for item in sorted_features:
        geometry_wgs84 = item["geometry_wgs84"]
        geometry_xy = item["geometry_sumo_xy"]
        boundary_qa = _summarize_geometry_against_boundary(geometry_xy, net.net_boundary_xy)
        road_qa = _road_qa(
            geometry_xy,
            lane_tree,
            lane_corridors,
            junction_tree,
            junction_envelopes,
        )
        counts["features_intersecting_retained_net_boundary"] += int(
            boundary_qa["intersects_retained_net_boundary"]
        )
        counts["features_crossing_or_extending_beyond_retained_net_boundary"] += int(
            boundary_qa["crosses_or_extends_outside_retained_net_boundary"]
        )
        counts["features_fully_within_retained_net_boundary"] += int(
            boundary_qa["fully_within_retained_net_boundary"]
        )
        counts["features_touching_only_retained_net_boundary"] += int(
            boundary_qa["touches_only_retained_net_boundary"]
        )
        counts["features_in_margin_only"] += int(
            not boundary_qa["intersects_retained_net_boundary"]
        )
        counts["features_overlapping_lane_corridor"] += int(road_qa["lane_corridor_overlap"])
        counts["features_overlapping_junction_envelope"] += int(
            road_qa["junction_envelope_overlap"]
        )
        counts["features_overlapping_lane_or_junction_exclusion"] += int(
            road_qa["lane_corridor_overlap"] or road_qa["junction_envelope_overlap"]
        )
        counts["features_touching_lane_corridor_only"] += int(
            not road_qa["lane_corridor_overlap"]
            and road_qa["nearest_lane_corridor_distance_m"] == 0
        )
        lane_distance = road_qa["nearest_lane_corridor_distance_m"]
        if lane_distance is not None:
            nearest_lane_distances.append(float(lane_distance))
        junction_distance = road_qa["nearest_junction_envelope_distance_m"]
        if junction_distance is not None:
            nearest_junction_distances.append(float(junction_distance))

        source_id = f"{item['osm_type']}/{item['osm_id']}"
        properties = {
            "source_id": source_id,
            "osm_type": item["osm_type"],
            "osm_id": item["osm_id"],
            "building": item["building"],
            "osm_tags": item["osm_tags"],
            **boundary_qa,
            **road_qa,
        }
        wgs_features.append(
            {
                "type": "Feature",
                "id": source_id,
                "geometry": mapping(geometry_wgs84),
                "properties": properties,
            }
        )
        local_features.append(
            {
                "type": "Feature",
                "id": source_id,
                "geometry": mapping(geometry_xy),
                "properties": properties,
            }
        )

    wgs_layer = {
        "type": "FeatureCollection",
        "name": "district7_geofabrik_osm_building_footprints_wgs84",
        "coordinate_reference_system": "EPSG:4326",
        "roi_bbox_wgs84_wsen": list(net.search_bbox_wgs84),
        "features": wgs_features,
    }
    local_layer = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "name": "district7_geofabrik_osm_building_footprints_sumo_xy",
        "coordinate_system": "sumo_xy_meters",
        "coordinate_definition": (
            "UTM projection from retained net projParameter plus its netOffset; "
            "full OSM geometry, uncut"
        ),
        "roi_bbox_sumo_xy": [
            round(value, 3)
            for value in (
                net.search_roi_xy.bounds[0],
                net.search_roi_xy.bounds[1],
                net.search_roi_xy.bounds[2],
                net.search_roi_xy.bounds[3],
            )
        ],
        "features": local_features,
    }

    def distance_summary(values: list[float]) -> dict[str, float | None]:
        if not values:
            return {"minimum_m": None, "median_m": None, "p95_m": None}
        values.sort()
        p95_index = min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)
        median = (values[(len(values) - 1) // 2] + values[len(values) // 2]) / 2
        return {
            "minimum_m": round(values[0], 3),
            "median_m": round(median, 3),
            "p95_m": round(values[p95_index], 3),
        }

    return (
        wgs_layer,
        local_layer,
        {
            "boundary_counts": dict(sorted(counts.items())),
            "by_osm_element_type_in_selected_roi": dict(sorted(selected_type_counts.items())),
            "building_tag_values_in_selected_roi": dict(sorted(selected_building_values.items())),
            "nearest_lane_corridor_distance_m": distance_summary(nearest_lane_distances),
            "nearest_junction_envelope_distance_m": distance_summary(nearest_junction_distances),
        },
    )


def extract(
    *,
    source_path: Path,
    net_path: Path,
    output_dir: Path,
    margin_m: float = 500.0,
    lane_clearance_m: float = 0.5,
    junction_clearance_m: float = 2.0,
) -> dict[str, Any]:
    source_path = source_path.resolve(strict=True)
    net_path = net_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    if source_path.suffix.lower() != ".pbf":
        raise ValueError(f"expected an OSM PBF source, got: {source_path}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse existing output directory: {output_dir}")

    net = _load_net_context(net_path, margin_m)
    md5_actual, md5_expected, checksum_path = _verify_md5(source_path)
    pbf_header = _load_pbf_header(source_path)
    header_timestamp = pbf_header["replication_timestamp_utc"]
    if not header_timestamp:
        raise ValueError("PBF header has no OSM replication timestamp")

    lane_corridors, junction_envelopes, road_counts = _load_road_geometry(
        net_path, net.search_roi_xy, lane_clearance_m, junction_clearance_m
    )
    if not lane_corridors:
        raise ValueError("retained SUMO net has no lane corridor geometry in the selected ROI")
    if not junction_envelopes:
        raise ValueError("retained SUMO net has no junction shape geometry in the selected ROI")

    handler = BuildingAreaHandler(net)
    handler.apply_file(str(source_path), locations=True)
    if not handler.features:
        raise ValueError("PBF yielded no valid OSM building areas intersecting the selected ROI")

    wgs_layer, local_layer, geometry_qa = _feature_layers(
        handler, net, lane_corridors, junction_envelopes
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    _assert_absent([output_dir])
    output_dir.mkdir()
    wgs_path = output_dir / "district7_building_footprints_geofabrik_20260929.wgs84.geojson"
    local_path = output_dir / "district7_building_footprints_geofabrik_20260929.sumo_xy.json"
    qa_path = output_dir / "district7_building_footprints_geofabrik_20260929.qa.json"
    manifest_path = output_dir / "district7_building_footprints_geofabrik_20260929.manifest.json"

    _exclusive_json(wgs_path, wgs_layer)
    _exclusive_json(local_path, local_layer)
    wgs_sha256 = _sha256_file(wgs_path)
    local_sha256 = _sha256_file(local_path)
    source_sha256 = _sha256_file(source_path)
    net_sha256 = net.sha256
    overlap_count = geometry_qa["boundary_counts"][
        "features_overlapping_lane_or_junction_exclusion"
    ]
    invalid_lane_count = road_counts.get("invalid_lane_geometry_count", 0)
    missing_junction_shape_count = road_counts.get("junction_without_shape_count", 0)
    invalid_junction_shape_count = road_counts.get("invalid_junction_geometry_count", 0)
    unverified_junction_count = missing_junction_shape_count + invalid_junction_shape_count
    clearance_coverage_complete = invalid_lane_count == 0 and unverified_junction_count == 0
    if overlap_count and not clearance_coverage_complete:
        qa_status = "overlaps_detected_with_partial_clearance_geometry"
        road_qa_status = "overlaps_detected_but_clearance_incomplete"
    elif overlap_count:
        qa_status = "overlaps_detected"
        road_qa_status = "overlaps_detected"
    elif clearance_coverage_complete:
        qa_status = "no_overlaps_detected"
        road_qa_status = "no_conflicts_detected"
    else:
        qa_status = "clearance_geometry_incomplete"
        road_qa_status = "clearance_incomplete_no_conflicts_detected_in_analyzed_geometry"
    qa = {
        "schema_version": QA_SCHEMA_VERSION,
        "status": qa_status,
        "scope": {
            "selected_roi": "retained SUMO net origBoundary expanded by a 500 m projected buffer",
            "retained_net_origBoundary_lon_lat": list(net.original_bounds),
            "osm_query_bbox_lon_lat_wsen": list(net.search_bbox_wgs84),
            "footprint_geometries_clipped": False,
        },
        "counts": {
            "assembled_building_area_callback_count_in_source": (
                handler.building_area_callback_count
            ),
            "building_no_area_count_excluded": handler.building_no_area_count,
            "building_areas_outside_selected_roi": handler.outside_roi_area_count,
            "valid_building_area_features_in_selected_roi": len(handler.features),
            "by_osm_element_type_in_selected_roi": geometry_qa[
                "by_osm_element_type_in_selected_roi"
            ],
            "building_tag_values_in_selected_roi": geometry_qa[
                "building_tag_values_in_selected_roi"
            ],
            "building_tag_values_in_all_source_areas": dict(sorted(handler.tag_values.items())),
            "invalid_or_unavailable_area_geometry_count": (
                handler.invalid_or_unavailable_geometry_count
            ),
            **geometry_qa["boundary_counts"],
        },
        "road_clearance": {
            "status": road_qa_status,
            "clearance_fully_verified": clearance_coverage_complete,
            "clearance_coverage_gaps": {
                "invalid_lane_geometry_count_excluded": invalid_lane_count,
                "junction_shape_elements_missing": missing_junction_shape_count,
                "junction_shape_elements_invalid": invalid_junction_shape_count,
                "junction_shape_elements_unverified": unverified_junction_count,
                "valid_junction_envelopes_analyzed": road_counts.get(
                    "junction_envelope_count_in_roi", 0
                ),
                "total_junction_elements": road_counts.get("junction_elements", 0),
            },
            "lane_corridor_method": (
                "each SUMO lane shape buffered by half its lane width plus "
                f"{lane_clearance_m:g} m; geometries were only flagged, never clipped"
            ),
            "junction_envelope_method": (
                "SUMO junction shape buffered by "
                f"{junction_clearance_m:g} m; geometries were only flagged, never clipped"
            ),
            "lane_and_junction_geometry_counts": road_counts,
            "nearest_lane_corridor_distance_m": geometry_qa["nearest_lane_corridor_distance_m"],
            "nearest_junction_envelope_distance_m": geometry_qa[
                "nearest_junction_envelope_distance_m"
            ],
            "interpretation": (
                "Distances are footprint-to-SUMO lane corridor or junction envelope. "
                "They do not locate a building entrance and are a QA flag only. Invalid or "
                "missing source shapes remain unverified; no automatic topology repair was "
                "applied."
            ),
        },
        "geometry_handling": {
            "closed_way_and_multipolygon_relation_areas": (
                "assembled by pyosmium; full source geometry retained without ROI clipping"
            ),
            "invalid_or_unavailable_area_ids_sample": handler.invalid_ids[:25],
            "height_tags": (
                "source tags are preserved only; no building heights are inferred or verified"
            ),
        },
        "artifacts": {
            "wgs84_geojson": {"path": _repo_path(wgs_path), "sha256": wgs_sha256},
            "sumo_xy_json": {"path": _repo_path(local_path), "sha256": local_sha256},
        },
        "source_dependencies": {
            "source_pbf": {"path": _repo_path(source_path), "sha256": source_sha256},
            "retained_sumo_net": {"path": _repo_path(net.path), "sha256": net_sha256},
        },
        "limitations": [
            (
                "This counts valid OSM area geometries returned by libosmium area assembly; "
                "it is not a census of every element tagged building."
            ),
            (
                "Open, incomplete, or otherwise non-area building-tagged elements are not "
                "included in polygon outputs."
            ),
            (
                "OSM footprint mapping can be incomplete or stale; mapped geometry is not a "
                "survey of every building."
            ),
            (
                "SUMO lane and junction shapes are exclusion QA references, not authoritative "
                "property boundaries."
            ),
            (
                "No road, lane, junction, semantic overlay, demand file, or existing renderer "
                "placement was edited."
            ),
            (
                "No occupancy, capacity, trips, demand, public value, economic impact, or "
                "observed building height is assigned."
            ),
        ],
    }
    qa["artifacts"]["qa_report"] = {"path": _repo_path(qa_path)}
    _exclusive_json(qa_path, qa)
    qa_sha256 = _sha256_file(qa_path)

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "extract_id": "district7_building_footprints_geofabrik_20260929",
        "status": qa["status"],
        "purpose": "renderer_neutral_visual_building_geometry_candidate_layer",
        "source": {
            "provider": "OpenStreetMap via Geofabrik",
            "download_page": GEOfABRIK_PAGE,
            "source_file_url": "https://download.geofabrik.de/asia/vietnam-260701.osm.pbf",
            "source_pbf": _repo_path(source_path),
            "file_size_bytes": source_path.stat().st_size,
            "sha256": source_sha256,
            "md5": md5_actual,
            "md5_expected_from_sidecar": md5_expected,
            "md5_sidecar": checksum_path,
            "osm_replication_header": pbf_header,
            "license": "Open Database License 1.0 (ODbL-1.0)",
            "attribution": ODBL_ATTRIBUTION,
        },
        "roi": {
            "basis": "retained SUMO net location origBoundary, not the earlier Overpass bbox",
            "retained_net_origBoundary_order": "west_lon,south_lat,east_lon,north_lat",
            "retained_net_origBoundary": list(net.original_bounds),
            "margin_projected_m": margin_m,
            "projected_crs": net.projection,
            "sumo_net_offset_m": list(net.net_offset),
            "expanded_roi_sumo_xy_bounds_m": [
                round(value, 3) for value in net.search_roi_xy.bounds
            ],
            "expanded_roi_query_bbox_order": "west_lon,south_lat,east_lon,north_lat",
            "expanded_roi_query_bbox_wgs84": list(net.search_bbox_wgs84),
            "geometry_clipped_to_roi": False,
        },
        "previous_overpass_bbox_context": {
            "bbox_order": "south_lat,west_lon,north_lat,east_lon",
            "bbox": [10.705, 106.695, 10.775, 106.780],
            "relationship": (
                "The earlier Overpass bbox is not used as this extraction ROI; the retained "
                "net origBoundary is expanded by the stated projected margin."
            ),
        },
        "validator": {
            "script": _repo_path(Path(__file__).resolve()),
            "version": SCRIPT_VERSION,
            "sha256": _sha256_file(Path(__file__).resolve()),
            "runtime": {
                "python": platform.python_version(),
                "osmium": importlib.metadata.version("osmium"),
                "shapely": importlib.metadata.version("shapely"),
                "pyproj": importlib.metadata.version("pyproj"),
            },
        },
        "artifacts": {
            "wgs84_geojson": {"path": _repo_path(wgs_path), "sha256": wgs_sha256},
            "sumo_xy_json": {"path": _repo_path(local_path), "sha256": local_sha256},
            "qa_report": {"path": _repo_path(qa_path), "sha256": qa_sha256},
        },
        "summary": qa["counts"],
        "retained_net_dependency": {
            "path": _repo_path(net.path),
            "sha256": net.sha256,
            "boundary": list(net.original_bounds),
        },
        "method": {
            "areas": (
                "pyosmium area assembly with location index; building ways and "
                "multipolygon relations"
            ),
            "projection": "SUMO net projParameter with netOffset applied to local coordinates",
            "qa": "OSM polygon geometry checked against retained SUMO lane and junction shapes",
        },
        "reproducibility": {
            "command_powershell": (
                "uv run --no-project --python 3.12 --with osmium==4.3.1 "
                "--with shapely==2.1.2 --with pyproj==3.8.0 "
                "python scripts/maps/extract_building_footprints_geofabrik.py `\n"
                "  --source-pbf "
                "artifacts/tmp/district7_geofabrik_vietnam_260701/vietnam-260701.osm.pbf `\n"
                "  --retained-net simulation_projects/map_intake/02_prepared_sources/"
                "district7_osm_seed_20260702/district7_seed.net.xml `\n"
                "  --output-dir artifacts/tmp/district7_building_footprints_geofabrik_20260929 `\n"
                "  --margin-m 500 --lane-clearance-m 0.5 --junction-clearance-m 2"
            ),
            "output_policy": (
                "exclusive new versioned directory; refuses to overwrite any existing "
                "output directory"
            ),
        },
        "limitations": qa["limitations"],
    }
    manifest_path = output_dir / "district7_building_footprints_geofabrik_20260929.manifest.json"
    _exclusive_json(manifest_path, manifest)
    return {
        "output_dir": output_dir,
        "feature_count": len(handler.features),
        "way_count": geometry_qa["by_osm_element_type_in_selected_roi"].get("way", 0),
        "relation_count": geometry_qa["by_osm_element_type_in_selected_roi"].get("relation", 0),
        "conflict_count": geometry_qa["boundary_counts"][
            "features_overlapping_lane_or_junction_exclusion"
        ],
        "source_sha256": source_sha256,
        "qa": qa,
        "manifest": manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pbf", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--retained-net", type=Path, default=DEFAULT_NET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--margin-m", type=float, default=500.0)
    parser.add_argument("--lane-clearance-m", type=float, default=0.5)
    parser.add_argument("--junction-clearance-m", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = extract(
            source_path=args.source_pbf,
            net_path=args.retained_net,
            output_dir=args.output_dir,
            margin_m=args.margin_m,
            lane_clearance_m=args.lane_clearance_m,
            junction_clearance_m=args.junction_clearance_m,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] Geofabrik building footprint extraction: {exc}", file=sys.stderr)
        return 1
    print(
        "[OK] Geofabrik building footprints: "
        f"{result['feature_count']} geometries "
        f"({result['way_count']} ways, {result['relation_count']} relations); "
        f"{result['conflict_count']} overlap lane/junction exclusion; "
        f"{result['output_dir']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
