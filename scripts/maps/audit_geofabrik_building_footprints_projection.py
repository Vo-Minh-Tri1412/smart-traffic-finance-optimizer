"""Audit projection and road-clearance samples for the existing footprint layer.

Reads the retained Overpass XML, v1 WGS84/SUMO-XY layers, their manifest, and the
retained SUMO net. It does not read or download the country PBF and never changes
the v1 layer, net, overlay, or demand inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pyproj import Geod, Transformer
from shapely import STRtree
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import transform, unary_union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_OSM = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "01_raw_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.osm"
)
DEFAULT_NET = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "02_prepared_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.net.xml"
)
DEFAULT_LAYER_DIR = (
    PROJECT_ROOT / "artifacts" / "tmp" / "district7_building_footprints_geofabrik_20260929"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "artifacts"
    / "tmp"
    / "district7_building_footprints_projection_audit_20260929_v2"
    / "projection_audit.json"
)
PROJECTION_TOLERANCE_M = 0.02
ROAD_TOLERANCE_M = 0.005


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite audit output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _read_net_context(net_path: Path) -> dict[str, Any]:
    root = ET.parse(net_path).getroot()
    location = root.find("location")
    if location is None:
        raise ValueError(f"SUMO net has no <location> header: {net_path}")
    original_bounds = tuple(float(part) for part in location.attrib["origBoundary"].split(","))
    conv_bounds = tuple(float(part) for part in location.attrib["convBoundary"].split(","))
    net_offset = tuple(float(part) for part in location.attrib["netOffset"].split(","))
    projection = location.attrib["projParameter"]
    forward = Transformer.from_crs("EPSG:4326", projection, always_xy=True)

    def project(x: Any, y: Any, z: Any = None) -> Any:
        east, north = forward.transform(x, y)
        return east + net_offset[0], north + net_offset[1]

    return {
        "original_bounds": original_bounds,
        "conv_bounds": conv_bounds,
        "net_offset": net_offset,
        "projection": projection,
        "forward": forward,
        "project": project,
        "root": root,
    }


def _raw_building_ways(
    source_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, tuple[float, float]]]:
    root = ET.parse(source_path).getroot()
    nodes = {
        node.attrib["id"]: (float(node.attrib["lon"]), float(node.attrib["lat"]))
        for node in root.findall("node")
    }
    ways: dict[str, Any] = {}
    invalid: Counter[str] = Counter()
    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib.get("v", "") for tag in way.findall("tag")}
        if "building" not in tags:
            continue
        way_id = way.attrib["id"]
        node_refs = [node.attrib.get("ref", "") for node in way.findall("nd")]
        if len(node_refs) < 4:
            invalid["too_short"] += 1
        elif node_refs[0] != node_refs[-1]:
            invalid["unclosed"] += 1
        elif any(node_ref not in nodes for node_ref in node_refs):
            invalid["missing_node"] += 1
        else:
            ways[way_id] = {
                "tags": tags,
                "coordinates": [nodes[node_ref] for node_ref in node_refs],
            }
    metadata = {
        "root_attributes": root.attrib,
        "osm_base_timestamp": (
            root.find("meta").attrib.get("osm_base") if root.find("meta") is not None else None
        ),
        "node_count": len(nodes),
        "building_way_count": sum(
            1
            for way in root.findall("way")
            if any(tag.attrib.get("k") == "building" for tag in way.findall("tag"))
        ),
        "valid_closed_building_way_count": len(ways),
        "invalid_building_way_counts": dict(sorted(invalid.items())),
    }
    return ways, metadata, nodes


def _all_ring_coordinates(geometry: Any) -> list[tuple[float, float]]:
    if geometry.geom_type == "Polygon":
        polygons = [geometry]
    elif geometry.geom_type == "MultiPolygon":
        polygons = list(geometry.geoms)
    else:
        return []
    return [
        (float(x), float(y))
        for polygon in polygons
        for ring in (polygon.exterior, *polygon.interiors)
        for x, y, *_ in ring.coords
    ]


def _summarize_shared_ways(
    raw_ways: dict[str, Any],
    wgs_features: dict[str, Any],
    xy_features: dict[str, Any],
    project: Any,
) -> dict[str, Any]:
    geod = Geod(ellps="WGS84")
    shared_ids = sorted(set(raw_ways) & set(wgs_features), key=int)
    rows: list[dict[str, Any]] = []
    max_raw_pbf_boundary_delta_m = 0.0
    max_independent_projection_error_m = 0.0
    all_vertex_sets_equal = True

    for way_id in shared_ids:
        raw_record = raw_ways[way_id]
        raw_geometry = Polygon(raw_record["coordinates"])
        wgs_feature = wgs_features[way_id]
        pbf_geometry = shape(wgs_feature["geometry"])
        local_geometry = shape(xy_features[way_id]["geometry"])
        projected_raw = transform(project, raw_geometry)
        projected_pbf = transform(project, pbf_geometry)
        boundary_delta_m = projected_raw.boundary.hausdorff_distance(projected_pbf.boundary)
        projection_error_m = projected_pbf.hausdorff_distance(local_geometry)
        _, _, centroid_delta_m = geod.inv(
            raw_geometry.centroid.x,
            raw_geometry.centroid.y,
            pbf_geometry.centroid.x,
            pbf_geometry.centroid.y,
        )
        raw_vertices = {(round(x, 7), round(y, 7)) for x, y in raw_record["coordinates"]}
        pbf_vertices = {(round(x, 7), round(y, 7)) for x, y in _all_ring_coordinates(pbf_geometry)}
        vertices_equal = raw_vertices == pbf_vertices
        all_vertex_sets_equal &= vertices_equal
        max_raw_pbf_boundary_delta_m = max(max_raw_pbf_boundary_delta_m, boundary_delta_m)
        max_independent_projection_error_m = max(
            max_independent_projection_error_m, projection_error_m
        )
        props = wgs_feature["properties"]
        rows.append(
            {
                "way_id": way_id,
                "building": raw_record["tags"].get("building", ""),
                "raw_vertex_count": len(raw_record["coordinates"]),
                "pbf_vertex_count": len(_all_ring_coordinates(pbf_geometry)),
                "raw_and_pbf_wgs84_vertex_sets_equal": vertices_equal,
                "raw_only_wgs84_vertex_count": len(raw_vertices - pbf_vertices),
                "pbf_only_wgs84_vertex_count": len(pbf_vertices - raw_vertices),
                "raw_to_pbf_boundary_hausdorff_m": round(boundary_delta_m, 6),
                "raw_to_pbf_centroid_geodesic_distance_m": round(centroid_delta_m, 6),
                "pbf_wgs84_to_local_sumo_xy_hausdorff_m": round(projection_error_m, 6),
                "lane_corridor_overlap": props["lane_corridor_overlap"],
                "junction_envelope_overlap": props["junction_envelope_overlap"],
            }
        )

    return {
        "raw_valid_closed_building_way_count": len(raw_ways),
        "pbf_building_way_feature_count": len(wgs_features),
        "shared_way_count": len(shared_ids),
        "shared_way_ids": shared_ids,
        "all_wgs84_vertex_sets_equal": all_vertex_sets_equal,
        "maximum_raw_to_pbf_boundary_delta_m": round(max_raw_pbf_boundary_delta_m, 6),
        "maximum_raw_to_pbf_centroid_delta_m": round(
            max((row["raw_to_pbf_centroid_geodesic_distance_m"] for row in rows), default=0.0),
            6,
        ),
        "maximum_independent_projection_error_m": round(max_independent_projection_error_m, 6),
        "projection_tolerance_m": PROJECTION_TOLERANCE_M,
        "projection_pass": max_independent_projection_error_m <= PROJECTION_TOLERANCE_M,
        "raw_vs_pbf_pass": (
            all_vertex_sets_equal and max_raw_pbf_boundary_delta_m <= PROJECTION_TOLERANCE_M
        ),
        "ways": rows,
    }


def _parse_sumo_shape(value: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for token in value.split():
        pair = token.split(",")
        if len(pair) < 2:
            continue
        try:
            x, y = float(pair[0]), float(pair[1])
        except ValueError:
            continue
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
    return points


def _node_to_junction_alignment(
    raw_nodes: dict[str, tuple[float, float]], net_path: Path, project: Any
) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    junction_count = 0
    for _, element in ET.iterparse(net_path, events=("end",)):
        if element.tag == "junction":
            junction_count += 1
            node_id = element.attrib.get("id", "")
            if node_id in raw_nodes:
                lon, lat = raw_nodes[node_id]
                projected_x, projected_y = project(lon, lat)
                junction_x = float(element.attrib["x"])
                junction_y = float(element.attrib["y"])
                residual = math.hypot(projected_x - junction_x, projected_y - junction_y)
                matched.append(
                    {
                        "osm_node_id": node_id,
                        "residual_m": residual,
                        "projected_xy_m": [projected_x, projected_y],
                        "sumo_junction_xy_m": [junction_x, junction_y],
                    }
                )
            element.clear()
        elif element.tag in {"edge", "net"}:
            element.clear()
    matched.sort(key=lambda item: item["residual_m"])
    residuals = [item["residual_m"] for item in matched]
    max_residual = max(residuals, default=math.inf)
    p95_index = min(len(residuals) - 1, math.ceil(0.95 * len(residuals)) - 1)
    return {
        "sumo_junction_element_count": junction_count,
        "raw_osm_node_ids_matched_to_sumo_junction_ids": len(matched),
        "matched_node_residual_tolerance_m": 0.02,
        "matched_nodes_within_tolerance": sum(residual <= 0.02 for residual in residuals),
        "minimum_residual_m": round(residuals[0], 9) if residuals else None,
        "median_residual_m": (round(residuals[len(residuals) // 2], 9) if residuals else None),
        "p95_residual_m": round(residuals[p95_index], 9) if residuals else None,
        "maximum_residual_m": round(max_residual, 9) if math.isfinite(max_residual) else None,
        "max_residual_examples": [
            {**item, "residual_m": round(item["residual_m"], 9)} for item in matched[-3:]
        ],
        "projection_pass": bool(matched) and max_residual <= 0.02,
        "interpretation": (
            "OSM node IDs directly shared by the retained source and SUMO junctions are projected "
            "using the net projParameter and netOffset, then compared with SUMO's stored x/y. "
            "The 2 cm tolerance allows for SUMO's 0.01 m coordinate serialization."
        ),
    }


def _road_geometries(
    net_path: Path, roi_xy: Any, lane_clearance_m: float, junction_clearance_m: float
) -> tuple[list[Any], list[Any], dict[str, int]]:
    lanes: list[Any] = []
    junctions: list[Any] = []
    counts = Counter()
    for _, element in ET.iterparse(net_path, events=("end",)):
        if element.tag == "lane":
            counts["lane_elements"] += 1
            points = _parse_sumo_shape(element.attrib.get("shape", ""))
            if len(points) >= 2:
                try:
                    line = LineString(points)
                    width = float(element.attrib.get("width", "3.2"))
                    if line.is_valid and line.length > 0 and width > 0 and math.isfinite(width):
                        corridor = line.buffer(
                            width / 2 + lane_clearance_m,
                            cap_style="flat",
                            join_style="mitre",
                        )
                        if corridor.intersects(roi_xy):
                            lanes.append(corridor)
                    else:
                        counts["invalid_lane_geometry_count"] += 1
                except (TypeError, ValueError):
                    counts["invalid_lane_geometry_count"] += 1
            else:
                counts["lane_without_shape_count"] += 1
            element.clear()
        elif element.tag == "junction":
            counts["junction_elements"] += 1
            points = _parse_sumo_shape(element.attrib.get("shape", ""))
            if len(points) >= 3:
                try:
                    polygon = Polygon(points)
                    if polygon.is_valid and polygon.area > 0:
                        envelope = polygon.buffer(junction_clearance_m)
                        if envelope.intersects(roi_xy):
                            junctions.append(envelope)
                            counts["junction_shapes_in_roi"] += 1
                    else:
                        counts["invalid_junction_geometry_count"] += 1
                except (TypeError, ValueError):
                    counts["invalid_junction_geometry_count"] += 1
            else:
                counts["junction_without_shape_count"] += 1
            element.clear()
        elif element.tag in {"edge", "net"}:
            element.clear()
    counts["lane_corridor_count_in_roi"] = len(lanes)
    counts["junction_envelope_count_in_roi"] = len(junctions)
    return lanes, junctions, dict(sorted(counts.items()))


def _independent_road_measure(
    geometry: Any,
    lane_tree: STRtree,
    lane_corridors: list[Any],
    junction_tree: STRtree,
    junction_envelopes: list[Any],
) -> dict[str, Any]:
    lane_index = int(lane_tree.nearest(geometry))
    junction_index = int(junction_tree.nearest(geometry))
    lane_hits = lane_tree.query(geometry, predicate="intersects")
    junction_hits = junction_tree.query(geometry, predicate="intersects")
    lane_overlap_area = (
        geometry.intersection(unary_union([lane_corridors[int(i)] for i in lane_hits])).area
        if len(lane_hits)
        else 0.0
    )
    junction_overlap_area = (
        geometry.intersection(unary_union([junction_envelopes[int(i)] for i in junction_hits])).area
        if len(junction_hits)
        else 0.0
    )
    return {
        "lane_corridor_overlap": lane_overlap_area > 0.01,
        "lane_corridor_overlap_area_m2": round(lane_overlap_area, 4),
        "nearest_lane_corridor_distance_m": round(geometry.distance(lane_corridors[lane_index]), 3),
        "junction_envelope_overlap": junction_overlap_area > 0.01,
        "junction_envelope_overlap_area_m2": round(junction_overlap_area, 4),
        "nearest_junction_envelope_distance_m": round(
            geometry.distance(junction_envelopes[junction_index]), 3
        ),
    }


def _tag_roi_histogram(features: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    conflict_counts = Counter()
    for feature in features:
        props = feature["properties"]
        tag = str(props.get("building", "")) or "(empty)"
        roi_class = (
            "retained_net_intersecting"
            if props["intersects_retained_net_boundary"]
            else "margin_only"
        )
        categories = ["all", roi_class]
        if props["crosses_or_extends_outside_retained_net_boundary"]:
            categories.append("crossing_or_extending")
        for category in categories:
            counter = groups[category][tag]
            counter["total"] += 1
            counter["lane"] += int(props["lane_corridor_overlap"])
            counter["junction"] += int(props["junction_envelope_overlap"])
            counter["either"] += int(
                props["lane_corridor_overlap"] or props["junction_envelope_overlap"]
            )
        conflict_counts["total"] += 1
        conflict_counts["lane"] += int(props["lane_corridor_overlap"])
        conflict_counts["junction"] += int(props["junction_envelope_overlap"])
        conflict_counts["either"] += int(
            props["lane_corridor_overlap"] or props["junction_envelope_overlap"]
        )

    result: dict[str, Any] = {"overall": dict(conflict_counts)}
    for category, tag_counts in groups.items():
        ordered = []
        for tag, counts in sorted(
            tag_counts.items(), key=lambda item: (-item[1]["total"], item[0])
        ):
            total = counts["total"]
            ordered.append(
                {
                    "building": tag,
                    **dict(counts),
                    "either_overlap_percent": round(100 * counts["either"] / total, 2),
                }
            )
        result[category] = ordered
    return result


def audit(
    *,
    raw_osm_path: Path,
    net_path: Path,
    wgs84_path: Path,
    sumo_xy_path: Path,
    source_manifest_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    raw_osm_path = raw_osm_path.resolve(strict=True)
    net_path = net_path.resolve(strict=True)
    wgs84_path = wgs84_path.resolve(strict=True)
    sumo_xy_path = sumo_xy_path.resolve(strict=True)
    source_manifest_path = source_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()

    raw_ways, raw_metadata, raw_nodes = _raw_building_ways(raw_osm_path)
    net = _read_net_context(net_path)
    wgs_layer = json.loads(wgs84_path.read_text(encoding="utf-8"))
    xy_layer = json.loads(sumo_xy_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    wgs_features = {
        str(feature["properties"]["osm_id"]): feature
        for feature in wgs_layer["features"]
        if feature["properties"]["osm_type"] == "way"
    }
    xy_features = {
        str(feature["properties"]["osm_id"]): feature
        for feature in xy_layer["features"]
        if feature["properties"]["osm_type"] == "way"
    }
    if set(wgs_features) != set(xy_features):
        raise ValueError("WGS84 and SUMO-XY v1 layers have different OSM way IDs")

    west, south, east, north = net["original_bounds"]
    roi_wgs84 = box(west, south, east, north)
    roi_xy = transform(net["project"], roi_wgs84).buffer(500, quad_segs=4)
    shared_ways = _summarize_shared_ways(raw_ways, wgs_features, xy_features, net["project"])
    node_alignment = _node_to_junction_alignment(raw_nodes, net_path, net["project"])

    source_conv_bounds = net["conv_bounds"]
    projected_boundary = transform(net["project"], roi_wgs84).bounds
    boundary_alignment_error_m = max(
        abs(actual - expected)
        for actual, expected in zip(projected_boundary, source_conv_bounds, strict=True)
    )

    lane_corridors, junction_envelopes, road_counts = _road_geometries(
        net_path, roi_xy, lane_clearance_m=0.5, junction_clearance_m=2.0
    )
    lane_tree = STRtree(lane_corridors)
    junction_tree = STRtree(junction_envelopes)
    sample_ids = ("188114147", "205798433", "263506611", "39514795", "263506639")
    sample_cases = []
    for way_id in sample_ids:
        if way_id not in raw_ways or way_id not in xy_features:
            continue
        raw_record = raw_ways[way_id]
        raw_geometry = Polygon(raw_record["coordinates"])
        local_geometry = shape(xy_features[way_id]["geometry"])
        independent = _independent_road_measure(
            transform(net["project"], raw_geometry),
            lane_tree,
            lane_corridors,
            junction_tree,
            junction_envelopes,
        )
        stored = xy_features[way_id]["properties"]
        sample_cases.append(
            {
                "way_id": way_id,
                "building": raw_record["tags"].get("building", ""),
                "raw_to_layer_projected_hausdorff_m": round(
                    transform(net["project"], raw_geometry).hausdorff_distance(local_geometry),
                    6,
                ),
                "independent_road_measure": independent,
                "stored_layer_road_measure": {
                    key: stored[key] for key in independent if key in stored
                },
                "road_measure_matches_stored": all(
                    independent[key] == stored[key]
                    for key in (
                        "lane_corridor_overlap",
                        "junction_envelope_overlap",
                        "nearest_lane_corridor_distance_m",
                        "nearest_junction_envelope_distance_m",
                    )
                ),
            }
        )

    all_features = wgs_layer["features"]
    histogram = _tag_roi_histogram(all_features)
    failed_samples = [
        case["way_id"] for case in sample_cases if not case["road_measure_matches_stored"]
    ]
    audit_result = {
        "schema_version": "district7_footprint_projection_audit.v2",
        "status": (
            "projection_and_sample_road_checks_passed"
            if shared_ways["projection_pass"]
            and node_alignment["projection_pass"]
            and shared_ways["raw_vs_pbf_pass"]
            and not failed_samples
            else "audit_mismatch_detected"
        ),
        "method": {
            "pbf_read": False,
            "wgs84_source_comparison": (
                "all closed building ways in retained Overpass XML matched to way IDs in v1; "
                "compare vertex sets, projected boundary Hausdorff distance, and WGS84 centroid"
            ),
            "projection_check": (
                "independently transform EPSG:4326 through the retained net projParameter, "
                "then add the retained netOffset and compare against v1 SUMO-XY geometry"
            ),
            "road_sample_check": (
                "rebuild lane corridors and valid junction envelopes from the retained net; "
                "recompute overlap and nearest-envelope distance for selected shared ways"
            ),
            "projection_tolerance_m": PROJECTION_TOLERANCE_M,
            "road_distance_tolerance_m": ROAD_TOLERANCE_M,
            "road_clearance_parameters": {
                "lane_buffer": "lane width / 2 + 0.5 m",
                "junction_buffer": "SUMO junction shape + 2 m",
            },
        },
        "inputs": {
            "retained_overpass_osm_xml": {
                "path": _repo_path(raw_osm_path),
                "sha256": _sha256_file(raw_osm_path),
                "metadata": raw_metadata,
            },
            "v1_wgs84_geojson": {
                "path": _repo_path(wgs84_path),
                "sha256": _sha256_file(wgs84_path),
            },
            "v1_sumo_xy_json": {
                "path": _repo_path(sumo_xy_path),
                "sha256": _sha256_file(sumo_xy_path),
            },
            "v1_source_manifest": {
                "path": _repo_path(source_manifest_path),
                "sha256": _sha256_file(source_manifest_path),
                "pbf_sha256_recorded_in_manifest": source_manifest["source"]["sha256"],
                "pbf_replication_timestamp_utc": source_manifest["source"][
                    "osm_replication_header"
                ]["replication_timestamp_utc"],
            },
            "retained_sumo_net": {
                "path": _repo_path(net_path),
                "sha256": _sha256_file(net_path),
            },
        },
        "net_coordinate_consistency": {
            "origBoundary_west_south_east_north": list(net["original_bounds"]),
            "convBoundary_minx_miny_maxx_maxy": list(source_conv_bounds),
            "transformed_origBoundary_bounds_sumo_xy": list(projected_boundary),
            "max_convBoundary_vs_transformed_origBoundary_delta_m": round(
                boundary_alignment_error_m, 6
            ),
            "bbox_comparison_interpretation": (
                "origBoundary describes source OSM extent while convBoundary describes the "
                "converted network extent; their bounds need not match. The bounding-box delta "
                "is descriptive only. Shared OSM-node/SUMO-junction residuals are the direct "
                "projection alignment check."
            ),
        },
        "shared_way_projection_audit": shared_ways,
        "shared_osm_node_to_sumo_junction_projection_audit": node_alignment,
        "v1_conflict_histogram_by_building_tag_and_roi": histogram,
        "independent_road_sample_cases": {
            "cases": sample_cases,
            "failed_sample_ids": failed_samples,
        },
        "clearance_coverage_limit": {
            "lane_geometry_counts": road_counts,
            "junction_elements_total": road_counts.get("junction_elements", 0),
            "valid_junction_envelopes_analyzed": road_counts.get(
                "junction_envelope_count_in_roi", 0
            ),
            "junction_without_shape_count": road_counts.get("junction_without_shape_count", 0),
            "invalid_junction_shape_count": road_counts.get("invalid_junction_geometry_count", 0),
            "invalid_shapes_repaired": False,
            "interpretation": (
                "A positive overlap is confirmed against the valid geometry analyzed. "
                "A non-overlap is not a complete clearance certificate where the net lacks "
                "a junction shape or provides an invalid one."
            ),
        },
        "conclusion": {
            "projection_bug_detected": not (
                shared_ways["projection_pass"] and node_alignment["projection_pass"]
            ),
            "raw_vs_pbf_geometry_mismatch_detected": not shared_ways["raw_vs_pbf_pass"],
            "sampled_road_qa_mismatch_detected": bool(failed_samples),
            "confirmed_overlaps_are_not_explained_by_a_shared_way_projection_offset": (
                shared_ways["projection_pass"]
                and node_alignment["projection_pass"]
                and shared_ways["raw_vs_pbf_pass"]
                and not failed_samples
            ),
            "caveat": (
                "This checks coordinate consistency and selected road intersections; it does "
                "not establish completeness or correctness of OSM footprint mapping."
            ),
        },
    }
    _json_exclusive(output_path, audit_result)
    audit_result["output"] = {
        "path": _repo_path(output_path),
        "sha256": _sha256_file(output_path),
    }
    return audit_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-osm", type=Path, default=DEFAULT_RAW_OSM)
    parser.add_argument("--retained-net", type=Path, default=DEFAULT_NET)
    parser.add_argument("--layer-dir", type=Path, default=DEFAULT_LAYER_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    layer_dir = args.layer_dir.resolve(strict=True)
    try:
        result = audit(
            raw_osm_path=args.raw_osm,
            net_path=args.retained_net,
            wgs84_path=layer_dir / "district7_building_footprints_geofabrik_20260929.wgs84.geojson",
            sumo_xy_path=layer_dir
            / "district7_building_footprints_geofabrik_20260929.sumo_xy.json",
            source_manifest_path=layer_dir
            / "district7_building_footprints_geofabrik_20260929.manifest.json",
            output_path=args.output,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"[FAIL] building footprint projection audit: {exc}", file=sys.stderr)
        return 1
    print(
        "[OK] footprint projection audit: "
        f"{result['shared_way_projection_audit']['shared_way_count']} common ways; "
        f"{result['status']}; {result['output']['path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
