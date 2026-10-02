"""Extract a provenance-preserving visual building layer from a local OSM XML extract.

This command deliberately does not edit the SUMO net, semantic overlay, demand files, or
existing renderer placement inputs.  It creates a renderer-neutral GeoJSON candidate layer and
small QA/provenance manifests.  The source extract may contain only incidental building ways;
the manifest records that limitation instead of treating the output as complete coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "visual_building_footprints_intake.v1"
QUERY_VERSION = "building_footprints_overpassql.v1"
VALIDATOR_VERSION = "prepare_building_footprints_intake.v1"
DEFAULT_BBOX = (10.705, 106.695, 10.775, 106.780)
HASH_CHUNK_SIZE = 1024 * 1024
EXPANSION_PROBE = {
    "attempted_at_utc": "2026-09-28T14:20:12Z",
    "query": "count-only way[building] over the existing bbox",
    "endpoint": "https://overpass-api.de/api/interpreter",
    "result": "HTTP 504 GatewayTimeout; no building response downloaded",
    "alternate_endpoint": "https://overpass.kumi.systems/api/interpreter",
    "alternate_result": "request timeout; no building response downloaded",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
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


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _bbox_contains(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    south, west, north, east = bbox
    return south <= lat <= north and west <= lon <= east


def _parse_source(
    source_path: Path, bbox: tuple[float, float, float, float]
) -> tuple[dict[str, Any], dict[str, Any]]:
    tree = ET.parse(source_path)
    root = tree.getroot()
    nodes: dict[str, tuple[float, float]] = {}
    for node in root.findall("node"):
        try:
            nodes[node.attrib["id"]] = (float(node.attrib["lat"]), float(node.attrib["lon"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid OSM node in {source_path}: {node.attrib}") from exc

    building_values: Counter[str] = Counter()
    features: list[dict[str, Any]] = []
    candidate_count = 0
    missing_node_way_count = 0
    unclosed_way_count = 0
    too_short_way_count = 0
    outside_bbox_vertex_count = 0
    ways_with_outside_vertices = 0

    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib.get("v", "") for tag in way.findall("tag")}
        if "building" not in tags:
            continue
        candidate_count += 1
        building_values[tags["building"]] += 1
        refs = [node.attrib.get("ref", "") for node in way.findall("nd")]
        if len(refs) < 4:
            too_short_way_count += 1
            continue
        if refs[0] != refs[-1]:
            unclosed_way_count += 1
            continue
        missing = [ref for ref in refs if ref not in nodes]
        if missing:
            missing_node_way_count += 1
            continue
        coordinates_lat_lon = [nodes[ref] for ref in refs]
        outside = sum(not _bbox_contains(lat, lon, bbox) for lat, lon in coordinates_lat_lon)
        outside_bbox_vertex_count += outside
        if outside:
            ways_with_outside_vertices += 1
        # GeoJSON uses [longitude, latitude], preserving OSM coordinates without projection.
        coordinates = [[lon, lat] for lat, lon in coordinates_lat_lon]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coordinates]},
                "properties": {
                    "osm_type": "way",
                    "osm_id": way.attrib["id"],
                    "building": tags["building"],
                    "osm_tags": tags,
                },
            }
        )

    features.sort(key=lambda feature: int(feature["properties"]["osm_id"]))
    meta = root.find("meta")
    source_meta = {
        "osm_generator": root.attrib.get("generator"),
        "osm_version": root.attrib.get("version"),
        "osm_base_timestamp": meta.attrib.get("osm_base") if meta is not None else None,
    }
    qa = {
        "source_element_counts": {
            "nodes": len(root.findall("node")),
            "ways": len(root.findall("way")),
            "relations": len(root.findall("relation")),
        },
        "building_way_count": candidate_count,
        "valid_closed_polygon_count": len(features),
        "missing_node_way_count": missing_node_way_count,
        "unclosed_way_count": unclosed_way_count,
        "too_short_way_count": too_short_way_count,
        "outside_bbox_vertex_count": outside_bbox_vertex_count,
        "ways_with_outside_bbox_vertices": ways_with_outside_vertices,
        "building_tag_values": dict(sorted(building_values.items())),
        "source_meta": source_meta,
    }
    return {
        "type": "FeatureCollection",
        "name": "district7_osm_building_footprints_baseline",
        "bbox": [bbox[1], bbox[0], bbox[3], bbox[2]],
        "features": features,
    }, qa


def _load_optional_placement_stats(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    placements = data.get("placements")
    if not isinstance(placements, list):
        raise ValueError(f"placement input has no placements array: {path}")
    return {
        "path": _repo_path(path),
        "sha256": _sha256_file(path),
        "declared_placement_count": data.get("placement_count"),
        "placement_count": len(placements),
        "building_tag_placement_count": sum(
            bool(row.get("source_has_building_tag")) for row in placements
        ),
        "zone_count": data.get("zone_count"),
    }


def build_intake(
    *,
    source_path: Path,
    query_path: Path,
    output_path: Path,
    qa_path: Path,
    manifest_path: Path,
    placement_path: Path | None,
    retained_net_path: Path | None,
    overlay_path: Path | None,
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
) -> dict[str, Any]:
    source_path = source_path.resolve(strict=True)
    query_path = query_path.resolve(strict=True)
    if output_path.exists() or qa_path.exists() or manifest_path.exists():
        existing = [path for path in (output_path, qa_path, manifest_path) if path.exists()]
        raise FileExistsError(
            "refusing to overwrite existing artifact(s): " + ", ".join(map(str, existing))
        )

    geojson, source_qa = _parse_source(source_path, bbox)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    output_sha256 = _sha256_file(output_path)
    placement_stats = _load_optional_placement_stats(placement_path)
    dependency_hashes = {}
    for label, path in (("retained_net", retained_net_path), ("semantic_overlay", overlay_path)):
        if path is not None:
            path = path.resolve(strict=True)
            dependency_hashes[label] = {"path": _repo_path(path), "sha256": _sha256_file(path)}

    qa = {
        "schema_version": "visual_building_footprints_qa.v1",
        "status": "baseline_partial",
        "validator_version": VALIDATOR_VERSION,
        "source": {
            "path": _repo_path(source_path),
            "sha256": _sha256_file(source_path),
            "bbox_south_west_north_east": list(bbox),
        },
        "artifact": {"path": _repo_path(output_path), "sha256": output_sha256},
        "query": {
            "path": _repo_path(query_path),
            "sha256": _sha256_file(query_path),
            "query_version": QUERY_VERSION,
        },
        "counts": source_qa,
        "existing_visual_placements": placement_stats,
        "retained_dependencies": dependency_hashes,
        "coverage": {
            "source_layer": "existing Overpass OSM extract",
            "generic_building_query_executed": False,
            "generic_building_coverage": "unknown; baseline extract query excluded way[building]",
            "interpretation": "visual geometry candidates only",
            "expansion_probe": EXPANSION_PROBE,
        },
        "exclusions": [
            "No SUMO net or semantic overlay mutation",
            "No facility capacity, occupancy, demand, trip, or economic value inference",
            "No claim that the 28 ways cover all buildings in the bbox or ROI",
        ],
    }
    _write_exclusive(qa_path, qa)
    qa_sha256 = _sha256_file(qa_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "intake_id": "district7_osm_building_footprints_baseline_20260928",
        "status": "baseline_partial",
        "purpose": "renderer_neutral_visual_building_geometry_candidate_layer",
        "source": {
            "provider": "OpenStreetMap",
            "acquisition": "existing local Overpass extract; no broad new download",
            "endpoint": "https://overpass-api.de/api/interpreter",
            "query_file": _repo_path(query_path),
            "query_sha256": _sha256_file(query_path),
            "query_version": QUERY_VERSION,
            "expansion_probe": EXPANSION_PROBE,
            "raw_osm_file": _repo_path(source_path),
            "raw_osm_sha256": _sha256_file(source_path),
            "license": "ODbL-1.0",
            "attribution": "© OpenStreetMap contributors",
            "bbox_south_west_north_east": list(bbox),
            "osm_base_timestamp": source_qa["source_meta"]["osm_base_timestamp"],
        },
        "validator": {
            "script": _repo_path(Path(__file__)),
            "version": VALIDATOR_VERSION,
            "sha256": _sha256_file(Path(__file__).resolve()),
        },
        "artifacts": {
            "geojson": {"path": _repo_path(output_path), "sha256": output_sha256},
            "qa_report": {"path": _repo_path(qa_path), "sha256": qa_sha256},
        },
        "qa_summary": {
            "source_elements": source_qa["source_element_counts"],
            "building_way_count": source_qa["building_way_count"],
            "valid_closed_polygon_count": source_qa["valid_closed_polygon_count"],
            "invalid_geometry_count": (
                source_qa["missing_node_way_count"]
                + source_qa["unclosed_way_count"]
                + source_qa["too_short_way_count"]
            ),
            "outside_bbox_vertex_count": source_qa["outside_bbox_vertex_count"],
        },
        "existing_visual_placements": placement_stats,
        "retained_dependencies": dependency_hashes,
        "limitations": [
            (
                "The baseline Overpass query selected highways, selected amenities and landuse; "
                "it did not request generic building ways."
            ),
            (
                "The 28 building ways are incidental tagged features, not complete bbox/ROI "
                "footprint coverage."
            ),
            (
                "A full building-only Overpass query was specified but not downloaded after "
                "gateway timeouts; rerun only with a bounded/tiled plan and preserved hashes."
            ),
            (
                "GeoJSON is WGS84 lon/lat and must be projected and clearance-checked before "
                "visual placement."
            ),
        ],
        "consumption_contract": {
            "allowed": ["visual context and renderer candidate geometry"],
            "forbidden": [
                "road or lane geometry replacement",
                "semantic overlay replacement",
                "capacity, occupancy, demand, trip or economic inference",
            ],
        },
    }
    _write_exclusive(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-osm", type=Path, required=True)
    parser.add_argument("--query-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--placements", type=Path)
    parser.add_argument("--retained-net", type=Path)
    parser.add_argument("--overlay", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_intake(
            source_path=args.source_osm,
            query_path=args.query_file,
            output_path=args.output,
            qa_path=args.qa,
            manifest_path=args.manifest,
            placement_path=args.placements,
            retained_net_path=args.retained_net,
            overlay_path=args.overlay,
        )
    except (ET.ParseError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] building footprint intake: {exc}", file=sys.stderr)
        return 1
    print(
        "[OK] building footprint intake: "
        f"{result['qa_summary']['valid_closed_polygon_count']} valid polygons; "
        f"manifest {result['artifacts']['qa_report']['path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
