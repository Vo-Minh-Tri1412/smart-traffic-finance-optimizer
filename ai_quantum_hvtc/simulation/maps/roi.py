from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.engines.sumo.config import (
    SumoRuntimeConfig,
    resolve_sumo_binary,
)
from ai_quantum_hvtc.simulation.maps.source import SumoNetIndex, load_sumo_net_index

ROI_OVERLAY_SCHEMA_VERSION = "roi_semantic_overlay.v1"

ZONE_TYPES = {
    "neutral",
    "residential",
    "commercial",
    "market_retail",
    "education",
    "healthcare",
    "industrial",
    "port_logistics",
    "transport_hub",
    "public_service",
    "nightlife",
    "gateway",
    "mixed",
}
DEMAND_DISABLED_ZONE_TYPES = {"neutral"}
POINT_ZONE_RADIUS_M_BY_TYPE = {
    "healthcare": 110.0,
    "education": 95.0,
    "market_retail": 85.0,
    "transport_hub": 100.0,
    "nightlife": 70.0,
    "public_service": 80.0,
    "commercial": 85.0,
    "industrial": 130.0,
    "port_logistics": 160.0,
    "gateway": 130.0,
    "mixed": 70.0,
}

ROAD_KEEP_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}
ROAD_LOCAL_HIGHWAYS = {"residential", "living_street", "unclassified"}
ROAD_SERVICE_HIGHWAYS = {"service", "track"}
ROAD_PEDESTRIAN_HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "cycleway",
    "crossing",
    "bus_stop",
    "street_lamp",
}
ROAD_REVIEW_HIGHWAYS = {"construction", "proposed"}


class RoiPrepError(ValueError):
    """Raised when ROI map-prep config or source data is invalid."""


@dataclass(frozen=True)
class RoiPolygon:
    points: tuple[OsmPoint, ...]

    def contains(self, lon: float, lat: float) -> bool:
        return _point_in_polygon(OsmPoint(lon=lon, lat=lat), self.points)

    def netconvert_boundary(self) -> str:
        return " ".join(f"{point.lon},{point.lat}" for point in self.points)


@dataclass(frozen=True)
class RoiConfig:
    roi_id: str
    name: str
    polygon: RoiPolygon
    osm_path: Path
    source_net_path: Path | None = None
    output_profile: str = "review_only_v1"
    zoning_profile: str = "osm_tags_v1"
    road_cleanup_profile: str = "safe_review_v1"
    reviewer_notes: str = ""
    config_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OsmPoint:
    lon: float
    lat: float


@dataclass(frozen=True)
class OsmNode:
    node_id: str
    point: OsmPoint
    tags: dict[str, str]


@dataclass(frozen=True)
class OsmWay:
    way_id: str
    node_refs: tuple[str, ...]
    tags: dict[str, str]
    geometry: tuple[OsmPoint, ...]

    @property
    def centroid(self) -> OsmPoint:
        return centroid(self.geometry)


@dataclass(frozen=True)
class MicroZone:
    zone_id: str
    name: str
    zone_type: str
    subtype: str
    source_element_id: str
    source_element_kind: str
    source_tags: dict[str, str]
    confidence: float
    geometry: dict[str, Any]
    centroid: tuple[float, float]
    anchor_edges: tuple[str, ...] = ()
    anchor_junctions: tuple[str, ...] = ()
    manual_review_required: bool = False
    zone_group_id: str = ""


@dataclass(frozen=True)
class RoadFeature:
    road_id: str
    name: str
    highway: str
    source_tags: dict[str, str]
    geometry: dict[str, Any]
    centroid: tuple[float, float]
    classification: str
    reason: str
    inside_zone_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    review_required: bool = False


@dataclass(frozen=True)
class ZoneGroup:
    group_id: str
    zone_type: str
    zone_ids: tuple[str, ...]
    zone_count: int


@dataclass(frozen=True)
class RoiPrepResult:
    roi_id: str
    micro_zones: tuple[MicroZone, ...]
    zone_groups: tuple[ZoneGroup, ...]
    roads: tuple[RoadFeature, ...]
    warnings: tuple[str, ...]
    source_osm_path: Path
    source_net_path: Path | None
    prepared_net_path: Path | None = None

    @property
    def zone_count(self) -> int:
        return len(self.micro_zones)

    @property
    def road_count(self) -> int:
        return len(self.roads)


@dataclass(frozen=True)
class RoiArtifactPaths:
    output_root: Path
    semantic_overlay: Path
    road_review: Path
    godot_preview: Path
    qa_json: Path
    qa_markdown: Path
    prepared_net: Path | None = None


def load_roi_config(path: Path | str) -> RoiConfig:
    config_path = Path(path).resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RoiPrepError(f"{config_path}: ROI config must be a JSON object")
    source_data = _object(data, "source")
    base_dir = config_path.parent
    return RoiConfig(
        roi_id=str(data["id"]),
        name=str(data["name"]),
        polygon=_roi_polygon(data.get("polygon")),
        osm_path=_resolve(base_dir, str(source_data["osm_path"])),
        source_net_path=_resolve_optional(base_dir, source_data.get("sumo_net_path")),
        output_profile=str(data.get("output_profile", "review_only_v1")),
        zoning_profile=str(data.get("zoning_profile", "osm_tags_v1")),
        road_cleanup_profile=str(data.get("road_cleanup_profile", "safe_review_v1")),
        reviewer_notes=str(data.get("reviewer_notes", "")),
        config_path=config_path,
        raw=data,
    )


def validate_roi_config_shape(config: RoiConfig, *, require_sources: bool = True) -> None:
    if not config.roi_id.strip():
        raise RoiPrepError("ROI config id must not be empty")
    if len(config.polygon.points) < 3:
        raise RoiPrepError(f"{config.roi_id}: ROI polygon must contain at least 3 points")
    if require_sources and not config.osm_path.is_file():
        raise RoiPrepError(f"{config.roi_id}: OSM source not found: {config.osm_path}")
    if (
        require_sources
        and config.source_net_path is not None
        and not config.source_net_path.is_file()
    ):
        raise RoiPrepError(f"{config.roi_id}: SUMO net source not found: {config.source_net_path}")


def prepare_roi(
    config: RoiConfig,
    *,
    copy_source_net: bool = False,
    clip_sumo_net: bool = False,
    output_root: Path | None = None,
) -> RoiPrepResult:
    validate_roi_config_shape(config)
    nodes, ways = read_osm_roi(config.osm_path, config.polygon)
    if not nodes and not ways:
        raise RoiPrepError(f"{config.roi_id}: ROI selected no OSM nodes or ways")

    net_index = load_sumo_net_index(config.source_net_path) if config.source_net_path else None
    edge_ids_by_osm_id = _sumo_edges_by_osm_way_id(net_index) if net_index else {}
    zones_without_anchor: list[str] = []
    micro_zones = infer_micro_zones(
        roi_id=config.roi_id,
        roi_polygon=config.polygon,
        nodes=nodes,
        ways=ways,
        road_ways=[way for way in ways if "highway" in way.tags],
        edge_ids_by_osm_id=edge_ids_by_osm_id,
        zones_without_anchor=zones_without_anchor,
    )
    roads = classify_roi_roads(
        road_ways=[way for way in ways if "highway" in way.tags],
        zones=micro_zones,
        edge_ids_by_osm_id=edge_ids_by_osm_id,
    )
    zone_groups = group_micro_zones(micro_zones)
    warnings = roi_warnings(
        config=config, zones=micro_zones, roads=roads, zones_without_anchor=zones_without_anchor
    )
    prepared_net_path = None
    if clip_sumo_net:
        prepared_net_path = _clip_sumo_net_to_roi(config=config, output_root=output_root)
    elif copy_source_net and config.source_net_path and output_root:
        prepared_net_path = output_root / f"{config.roi_id}.prepared.net.xml"
        prepared_net_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.source_net_path, prepared_net_path)

    return RoiPrepResult(
        roi_id=config.roi_id,
        micro_zones=tuple(micro_zones),
        zone_groups=tuple(zone_groups),
        roads=tuple(roads),
        warnings=tuple(warnings),
        source_osm_path=config.osm_path,
        source_net_path=config.source_net_path,
        prepared_net_path=prepared_net_path,
    )


def _clip_sumo_net_to_roi(*, config: RoiConfig, output_root: Path | None) -> Path:
    if output_root is None:
        raise RoiPrepError(f"{config.roi_id}: output_root is required to clip SUMO net")
    if config.source_net_path is None:
        raise RoiPrepError(f"{config.roi_id}: source.sumo_net_path is required to clip SUMO net")
    netconvert = resolve_sumo_binary(SumoRuntimeConfig().netconvert_binary)
    if netconvert is None:
        raise RoiPrepError(
            f"{config.roi_id}: netconvert was not found. Install SUMO or set SUMO_HOME."
        )
    output_root.mkdir(parents=True, exist_ok=True)
    prepared_net_path = output_root / f"{config.roi_id}.prepared.net.xml"
    boundary = config.polygon.netconvert_boundary()
    command = [
        netconvert,
        "-s",
        str(config.source_net_path.resolve()),
        "--keep-edges.in-geo-boundary",
        boundary,
        "--keep-edges.components",
        "1",
        "--output-file",
        str(prepared_net_path.resolve()),
        "--no-turnarounds",
        "true",
    ]
    completed = subprocess.run(
        command,
        cwd=output_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RoiPrepError(
            f"{config.roi_id}: netconvert ROI clip failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )
    if not prepared_net_path.is_file() or prepared_net_path.stat().st_size <= 0:
        raise RoiPrepError(
            f"{config.roi_id}: netconvert did not produce a prepared ROI net at "
            f"{prepared_net_path}"
        )
    return prepared_net_path


def read_osm_roi(path: Path, polygon: RoiPolygon) -> tuple[dict[str, OsmNode], list[OsmWay]]:
    all_nodes: dict[str, OsmNode] = {}
    selected_node_ids: set[str] = set()
    for _event, element in ET.iterparse(path, events=("end",)):
        tag = _strip_namespace(element.tag)
        if tag == "node":
            node_id = str(element.attrib.get("id", ""))
            lon = float(element.attrib.get("lon", "0"))
            lat = float(element.attrib.get("lat", "0"))
            tags = _tags(element)
            node = OsmNode(node_id=node_id, point=OsmPoint(lon=lon, lat=lat), tags=tags)
            all_nodes[node_id] = node
            if polygon.contains(lon, lat):
                selected_node_ids.add(node_id)
            element.clear()

    selected_ways: list[OsmWay] = []
    for _event, element in ET.iterparse(path, events=("end",)):
        tag = _strip_namespace(element.tag)
        if tag == "way":
            way_id = str(element.attrib.get("id", ""))
            node_refs = tuple(str(nd.attrib.get("ref", "")) for nd in element.findall("nd"))
            geometry = tuple(all_nodes[ref].point for ref in node_refs if ref in all_nodes)
            tags = _tags(element)
            if _way_intersects_roi(node_refs, geometry, selected_node_ids, polygon) and tags:
                selected_ways.append(
                    OsmWay(way_id=way_id, node_refs=node_refs, tags=tags, geometry=geometry)
                )
            element.clear()

    selected_nodes = {node_id: all_nodes[node_id] for node_id in selected_node_ids}
    for node in all_nodes.values():
        if node.tags and polygon.contains(node.point.lon, node.point.lat):
            selected_nodes[node.node_id] = node
    return selected_nodes, selected_ways


def infer_micro_zones(
    *,
    roi_id: str,
    roi_polygon: RoiPolygon,
    nodes: dict[str, OsmNode],
    ways: list[OsmWay],
    road_ways: list[OsmWay],
    edge_ids_by_osm_id: dict[str, tuple[str, ...]],
    zones_without_anchor: list[str],
) -> list[MicroZone]:
    zones: list[MicroZone] = []
    for way in ways:
        classification = classify_zone_tags(way.tags)
        if classification is None:
            continue
        zone_type, subtype, confidence = classification
        if zone_type not in ZONE_TYPES:
            zone_type = "mixed"
        geometry = _geometry_for_points(way.geometry)
        center = centroid(way.geometry)
        anchor_edges = _anchor_edges_for_zone(
            center=center,
            road_ways=road_ways,
            edge_ids_by_osm_id=edge_ids_by_osm_id,
        )
        manual_review_required = not anchor_edges
        zone_id = _zone_id(zone_type, "way", way.way_id)
        if manual_review_required:
            zones_without_anchor.append(zone_id)
        zones.append(
            MicroZone(
                zone_id=zone_id,
                name=_display_name(way.tags, zone_id),
                zone_type=zone_type,
                subtype=subtype,
                source_element_id=way.way_id,
                source_element_kind="way",
                source_tags=_relevant_tags(way.tags),
                confidence=confidence,
                geometry=geometry,
                centroid=(center.lon, center.lat),
                anchor_edges=anchor_edges,
                manual_review_required=manual_review_required,
                zone_group_id=f"ZG_{zone_type.upper()}",
            )
        )

    for node in nodes.values():
        classification = classify_zone_tags(node.tags)
        if classification is None:
            continue
        zone_type, subtype, confidence = classification
        center = node.point
        anchor_edges = _anchor_edges_for_zone(
            center=center,
            road_ways=road_ways,
            edge_ids_by_osm_id=edge_ids_by_osm_id,
        )
        manual_review_required = not anchor_edges
        zone_id = _zone_id(zone_type, "node", node.node_id)
        if manual_review_required:
            zones_without_anchor.append(zone_id)
        zones.append(
            MicroZone(
                zone_id=zone_id,
                name=_display_name(node.tags, zone_id),
                zone_type=zone_type,
                subtype=subtype,
                source_element_id=node.node_id,
                source_element_kind="node",
                source_tags=_relevant_tags(node.tags),
                confidence=confidence,
                geometry=_point_buffer_geometry(center, zone_type),
                centroid=(center.lon, center.lat),
                anchor_edges=anchor_edges,
                manual_review_required=manual_review_required,
                zone_group_id=f"ZG_{zone_type.upper()}",
            )
        )
    zones.append(_neutral_fill_zone(roi_id=roi_id, roi_polygon=roi_polygon))
    return zones


def classify_zone_tags(tags: dict[str, str]) -> tuple[str, str, float] | None:
    landuse = tags.get("landuse", "")
    amenity = tags.get("amenity", "")
    building = tags.get("building", "")
    industrial = tags.get("industrial", "")
    public_transport = tags.get("public_transport", "")
    shop = tags.get("shop", "")
    office = tags.get("office", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")
    emergency = tags.get("emergency", "")
    railway = tags.get("railway", "")

    if industrial in {"port", "depot"} or "port" in (tags.get("name", "").lower()):
        return "port_logistics", industrial or "port", 0.88
    if industrial:
        return "industrial", industrial, 0.84
    if building in {"industrial", "warehouse", "factory"}:
        return "industrial", building, 0.76
    if building in {"apartments", "residential", "house", "detached", "dormitory"}:
        return "residential", building, 0.72
    if building in {"commercial", "retail", "office"}:
        return "commercial", building, 0.70
    if building in {"school", "university", "college", "kindergarten"}:
        return "education", building, 0.76
    if building in {"hospital", "clinic"}:
        return "healthcare", building, 0.78
    if building in {"civic", "government", "public"}:
        return "public_service", building, 0.68
    if landuse == "industrial":
        return "industrial", landuse, 0.86
    if landuse == "residential":
        return "residential", landuse, 0.86
    if landuse == "commercial":
        return "commercial", landuse, 0.84
    if landuse == "retail":
        return "market_retail", landuse, 0.82
    if landuse in {"port", "depot"}:
        return "port_logistics", landuse, 0.82
    if landuse in {"education", "school"}:
        return "education", landuse, 0.78
    if landuse in {"institutional", "public", "government", "military"}:
        return "public_service", landuse, 0.70
    if landuse in {"recreation_ground", "grass", "village_green", "cemetery"}:
        return "mixed", landuse, 0.54
    if amenity in {"school", "university", "college", "language_school", "kindergarten"}:
        return "education", amenity, 0.90
    if amenity in {"hospital", "clinic"} or healthcare in {"hospital", "clinic"}:
        return "healthcare", amenity or healthcare, 0.90
    if amenity in {"marketplace"} or shop in {
        "mall",
        "department_store",
        "supermarket",
        "convenience",
        "bakery",
        "butcher",
        "clothes",
        "electronics",
        "hardware",
    }:
        return "market_retail", amenity or shop, 0.86
    if amenity in {"bus_station", "fuel", "parking", "taxi"} or public_transport in {
        "station",
        "platform",
        "stop_position",
    }:
        return "transport_hub", amenity or public_transport, 0.78
    if railway in {"station", "subway_entrance"}:
        return "transport_hub", railway, 0.76
    if amenity in {
        "police",
        "fire_station",
        "townhall",
        "courthouse",
        "post_office",
        "library",
        "community_centre",
        "place_of_worship",
        "bank",
        "atm",
    } or emergency:
        return "public_service", amenity or emergency, 0.82
    if amenity in {"bar", "pub", "nightclub", "restaurant", "cafe", "fast_food"}:
        return "nightlife", amenity, 0.74
    if shop:
        return "market_retail", shop, 0.70
    if office:
        return "commercial", office, 0.66
    if tourism in {"hotel", "hostel", "guest_house"}:
        return "commercial", tourism, 0.64
    if tourism or leisure:
        return "mixed", tourism or leisure, 0.58
    return None


def classify_roi_roads(
    *,
    road_ways: list[OsmWay],
    zones: list[MicroZone],
    edge_ids_by_osm_id: dict[str, tuple[str, ...]],
) -> list[RoadFeature]:
    roads: list[RoadFeature] = []
    polygon_zones = [
        zone
        for zone in zones
        if zone.zone_type != "neutral" and zone.geometry.get("type") == "polygon"
    ]
    for way in road_ways:
        center = way.centroid
        inside_zone_ids = tuple(
            zone.zone_id
            for zone in polygon_zones
            if _point_in_polygon(center, _coordinates_to_points(zone.geometry["coordinates"]))
        )
        highway = way.tags.get("highway", "")
        classification, reason, review_required = classify_road_tags(
            tags=way.tags,
            inside_zone=bool(inside_zone_ids),
        )
        roads.append(
            RoadFeature(
                road_id=way.way_id,
                name=_display_name(way.tags, f"road_{way.way_id}"),
                highway=highway,
                source_tags=_relevant_tags(way.tags),
                geometry=_geometry_for_points(way.geometry),
                centroid=(center.lon, center.lat),
                classification=classification,
                reason=reason,
                inside_zone_ids=inside_zone_ids,
                edge_ids=edge_ids_by_osm_id.get(way.way_id, ()),
                review_required=review_required,
            )
        )
    return roads


def classify_road_tags(*, tags: dict[str, str], inside_zone: bool) -> tuple[str, str, bool]:
    highway = tags.get("highway", "")
    if tags.get("junction") == "roundabout":
        return "keep_simulation", "roundabout should remain routable", False
    if highway in ROAD_KEEP_HIGHWAYS:
        return "keep_simulation", f"major road class {highway}", False
    if tags.get("bus") in {"yes", "designated"} or tags.get("hgv") in {"yes", "designated"}:
        return "keep_simulation", "public transport or truck access tag", False
    if highway in ROAD_PEDESTRIAN_HIGHWAYS:
        return "pedestrian_only", f"non-motorized road class {highway}", True
    if highway in ROAD_REVIEW_HIGHWAYS:
        return "review_required", f"unstable road class {highway}", True
    if inside_zone and highway in ROAD_SERVICE_HIGHWAYS:
        return "zone_internal_service", f"small service road inside inferred zone ({highway})", True
    if inside_zone and highway in ROAD_LOCAL_HIGHWAYS:
        return "review_required", f"local road inside inferred zone ({highway})", True
    if highway in ROAD_SERVICE_HIGHWAYS:
        return "keep_render_only", f"service road outside zone ({highway})", True
    if highway in ROAD_LOCAL_HIGHWAYS:
        return "keep_simulation", f"local access road ({highway})", False
    return "review_required", f"unhandled road class {highway or 'missing'}", True


def group_micro_zones(zones: list[MicroZone]) -> list[ZoneGroup]:
    zone_ids_by_type: dict[str, list[str]] = {}
    for zone in zones:
        zone_ids_by_type.setdefault(zone.zone_type, []).append(zone.zone_id)
    return [
        ZoneGroup(
            group_id=f"ZG_{zone_type.upper()}",
            zone_type=zone_type,
            zone_ids=tuple(sorted(zone_ids)),
            zone_count=len(zone_ids),
        )
        for zone_type, zone_ids in sorted(zone_ids_by_type.items())
    ]


def roi_warnings(
    *,
    config: RoiConfig,
    zones: list[MicroZone],
    roads: list[RoadFeature],
    zones_without_anchor: list[str],
) -> list[str]:
    warnings: list[str] = []
    if len(zones) < 6:
        warnings.append(
            f"{config.roi_id}: inferred only {len(zones)} micro-zones; "
            "ROI may be too small or OSM tags too sparse"
        )
    if zones_without_anchor:
        warnings.append(
            f"{config.roi_id}: {len(zones_without_anchor)} zones need manual access-road review"
        )
    flagged_roads = [road for road in roads if road.review_required]
    if flagged_roads:
        warnings.append(f"{config.roi_id}: {len(flagged_roads)} roads require cleanup/review")
    if not any(road.classification == "keep_simulation" for road in roads):
        warnings.append(f"{config.roi_id}: no routable simulation roads were classified")
    return warnings


def write_roi_artifacts(result: RoiPrepResult, output_root: Path) -> RoiArtifactPaths:
    output_root.mkdir(parents=True, exist_ok=True)
    paths = RoiArtifactPaths(
        output_root=output_root,
        semantic_overlay=output_root / "semantic_overlay.generated.json",
        road_review=output_root / "road_review.generated.json",
        godot_preview=output_root / "godot_preview.generated.json",
        qa_json=output_root / "qa_report.json",
        qa_markdown=output_root / "qa_report.md",
        prepared_net=result.prepared_net_path,
    )
    _write_json(paths.semantic_overlay, semantic_overlay_payload(result))
    _write_json(paths.road_review, road_review_payload(result))
    _write_json(paths.godot_preview, godot_preview_payload(result))
    qa = qa_payload(result, paths)
    _write_json(paths.qa_json, qa)
    paths.qa_markdown.write_text(qa_markdown(result, qa), encoding="utf-8")
    return paths


def semantic_overlay_payload(result: RoiPrepResult) -> dict[str, Any]:
    return {
        "schema_version": ROI_OVERLAY_SCHEMA_VERSION,
        "id": f"{result.roi_id}_auto_overlay",
        "name": f"{result.roi_id} auto-generated ROI overlay",
        "zones": [_zone_payload(zone) for zone in result.micro_zones],
        "zone_groups": [asdict(group) for group in result.zone_groups],
        "caveats": [
            "Auto-generated from OSM tags and ROI config.",
            "Neutral fill zones are visual/semantic background only and must not generate demand.",
            "Point POI tags are expanded into approximate local polygon buffers for rendering, "
            "flow anchoring, and public-finance interpretation.",
            "Manual review should confirm access roads, public-value interpretation, "
            "and zone boundaries.",
            "Building visuals should be symbolic zone assets, not imported real building geometry.",
        ],
    }


def road_review_payload(result: RoiPrepResult) -> dict[str, Any]:
    return {
        "schema_version": "roi_road_review.v1",
        "roi_id": result.roi_id,
        "roads": [asdict(road) for road in result.roads],
        "summary": _road_classification_counts(result.roads),
    }


def godot_preview_payload(result: RoiPrepResult) -> dict[str, Any]:
    return {
        "schema_version": "godot_roi_preview.v1",
        "roi_id": result.roi_id,
        "geometry_source": {
            "sumo_net_path": str(result.prepared_net_path or result.source_net_path or ""),
            "source_of_truth": "prepared_sumo_net"
            if result.prepared_net_path
            else "source_sumo_net",
        },
        "zones": [_zone_payload(zone) for zone in result.micro_zones],
        "roads": [
            {
                "id": road.road_id,
                "name": road.name,
                "classification": road.classification,
                "geometry": road.geometry,
                "render_hint": "muted" if road.classification != "keep_simulation" else "primary",
            }
            for road in result.roads
        ],
    }


def qa_payload(result: RoiPrepResult, paths: RoiArtifactPaths) -> dict[str, Any]:
    return {
        "schema_version": "roi_prep_qa.v1",
        "roi_id": result.roi_id,
        "source_osm_path": str(result.source_osm_path),
        "source_net_path": str(result.source_net_path or ""),
        "prepared_net_path": str(result.prepared_net_path or ""),
        "counts": {
            "micro_zones": len(result.micro_zones),
            "zone_groups": len(result.zone_groups),
            "roads": len(result.roads),
            "roads_by_classification": _road_classification_counts(result.roads),
            "zones_without_anchor_edges": sum(
                1 for zone in result.micro_zones if not zone.anchor_edges
            ),
        },
        "warnings": list(result.warnings),
        "artifacts": {
            "semantic_overlay": str(paths.semantic_overlay),
            "road_review": str(paths.road_review),
            "godot_preview": str(paths.godot_preview),
        },
    }


def qa_markdown(result: RoiPrepResult, qa: dict[str, Any]) -> str:
    counts = qa["counts"]
    lines = [
        f"# ROI prep QA — {result.roi_id}",
        "",
        f"- Micro-zones: {counts['micro_zones']}",
        f"- Zone groups: {counts['zone_groups']}",
        f"- Roads reviewed: {counts['roads']}",
        f"- Zones without anchor edges: {counts['zones_without_anchor_edges']}",
        "",
        "## Road classifications",
    ]
    for key, value in sorted(counts["roads_by_classification"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Warnings"])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "This is an auto-generated ROI preparation report. "
            "It must be reviewed before policy claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def _zone_payload(zone: MicroZone) -> dict[str, Any]:
    demand_enabled = zone.zone_type not in DEMAND_DISABLED_ZONE_TYPES
    return {
        "id": zone.zone_id,
        "name": zone.name,
        "type": zone.zone_type,
        "subtype": zone.subtype,
        "source_element_id": zone.source_element_id,
        "source_element_kind": zone.source_element_kind,
        "source_tags": zone.source_tags,
        "confidence": zone.confidence,
        "geometry": zone.geometry,
        "centroid": list(zone.centroid),
        "anchor_edges": list(zone.anchor_edges),
        "anchor_junctions": list(zone.anchor_junctions),
        "manual_review_required": zone.manual_review_required,
        "zone_group_id": zone.zone_group_id,
        "demand_enabled": demand_enabled,
        "traffic_role": _traffic_role_for_zone(zone.zone_type),
        "economic_role": _economic_role_for_zone(zone.zone_type),
    }


def _road_classification_counts(
    roads: tuple[RoadFeature, ...] | list[RoadFeature],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for road in roads:
        counts[road.classification] = counts.get(road.classification, 0) + 1
    return counts


def _traffic_role_for_zone(zone_type: str) -> str:
    return {
        "neutral": "background_no_demand",
        "residential": "origin_commute",
        "commercial": "destination_service_jobs",
        "market_retail": "destination_retail_delivery",
        "education": "time_window_school_commute",
        "healthcare": "emergency_priority_destination",
        "industrial": "worker_and_truck_flow",
        "port_logistics": "truck_and_logistics_flow",
        "transport_hub": "bus_taxi_transfer_flow",
        "public_service": "public_service_access",
        "nightlife": "evening_demand_spike",
        "gateway": "external_entry_exit",
        "mixed": "mixed_low_confidence_flow",
    }.get(zone_type, "mixed_low_confidence_flow")


def _economic_role_for_zone(zone_type: str) -> str:
    return {
        "neutral": "visual_background_only",
        "residential": "household_time_and_access",
        "commercial": "service_economy_access",
        "market_retail": "retail_delivery_and_local_trade",
        "education": "student_family_time_access",
        "healthcare": "emergency_delay_and_health_access",
        "industrial": "labor_productivity_and_freight_delay",
        "port_logistics": "freight_throughput_and_supply_chain_delay",
        "transport_hub": "public_transport_reliability",
        "public_service": "public_service_access",
        "nightlife": "evening_local_economy_and_safety",
        "gateway": "network_access_and_external_flow",
        "mixed": "mixed_uncertain_public_value",
    }.get(zone_type, "mixed_uncertain_public_value")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tags(element: ET.Element) -> dict[str, str]:
    return {
        str(tag.attrib.get("k", "")): str(tag.attrib.get("v", ""))
        for tag in element.findall("tag")
        if tag.attrib.get("k")
    }


def _way_intersects_roi(
    node_refs: tuple[str, ...],
    geometry: tuple[OsmPoint, ...],
    selected_node_ids: set[str],
    polygon: RoiPolygon,
) -> bool:
    if any(ref in selected_node_ids for ref in node_refs):
        return True
    if geometry:
        center = centroid(geometry)
        return polygon.contains(center.lon, center.lat)
    return False


def centroid(points: tuple[OsmPoint, ...]) -> OsmPoint:
    if not points:
        return OsmPoint(lon=0.0, lat=0.0)
    return OsmPoint(
        lon=sum(point.lon for point in points) / len(points),
        lat=sum(point.lat for point in points) / len(points),
    )


def _geometry_for_points(points: tuple[OsmPoint, ...]) -> dict[str, Any]:
    coordinates = [[point.lon, point.lat] for point in points]
    if len(points) >= 3 and points[0] == points[-1]:
        return {"type": "polygon", "coordinates": coordinates}
    if len(points) >= 2:
        return {"type": "line", "coordinates": coordinates}
    return {"type": "point", "coordinates": coordinates[0] if coordinates else []}


def _neutral_fill_zone(*, roi_id: str, roi_polygon: RoiPolygon) -> MicroZone:
    center = centroid(roi_polygon.points)
    return MicroZone(
        zone_id=f"Z_NEUTRAL_ROI_FILL_{_safe_id(roi_id).upper()}",
        name="Neutral background zone",
        zone_type="neutral",
        subtype="roi_fill",
        source_element_id=roi_id,
        source_element_kind="roi_fill",
        source_tags={
            "synthetic": "neutral_fill",
            "demand_enabled": "false",
            "purpose": "visual_and_semantic_background",
        },
        confidence=0.25,
        geometry=_geometry_for_points(roi_polygon.points),
        centroid=(center.lon, center.lat),
        manual_review_required=False,
        zone_group_id="ZG_NEUTRAL",
    )


def _point_buffer_geometry(center: OsmPoint, zone_type: str) -> dict[str, Any]:
    radius_m = POINT_ZONE_RADIUS_M_BY_TYPE.get(zone_type, 70.0)
    coordinates: list[list[float]] = []
    for index in range(12):
        angle = math.tau * float(index) / 12.0
        point = _offset_point_m(
            center,
            east_m=radius_m * math.cos(angle),
            north_m=radius_m * math.sin(angle),
        )
        coordinates.append([point.lon, point.lat])
    return {"type": "polygon", "coordinates": coordinates}


def _offset_point_m(center: OsmPoint, *, east_m: float, north_m: float) -> OsmPoint:
    lat_degree_m = 111_320.0
    lon_degree_m = max(1.0, 111_320.0 * math.cos(math.radians(center.lat)))
    return OsmPoint(
        lon=center.lon + east_m / lon_degree_m,
        lat=center.lat + north_m / lat_degree_m,
    )


def _coordinates_to_points(coordinates: object) -> tuple[OsmPoint, ...]:
    if not isinstance(coordinates, list):
        return ()
    points: list[OsmPoint] = []
    for item in coordinates:
        if isinstance(item, list) and len(item) >= 2:
            points.append(OsmPoint(lon=float(item[0]), lat=float(item[1])))
    return tuple(points)


def _point_in_polygon(point: OsmPoint, polygon: tuple[OsmPoint, ...]) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i, poly_point in enumerate(polygon):
        prev = polygon[j]
        intersects = (poly_point.lat > point.lat) != (prev.lat > point.lat) and point.lon < (
            (prev.lon - poly_point.lon)
            * (point.lat - poly_point.lat)
            / ((prev.lat - poly_point.lat) or 1e-12)
            + poly_point.lon
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _anchor_edges_for_zone(
    *,
    center: OsmPoint,
    road_ways: list[OsmWay],
    edge_ids_by_osm_id: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    candidates = [
        way
        for way in road_ways
        if way.way_id in edge_ids_by_osm_id
        and classify_road_tags(tags=way.tags, inside_zone=False)[0] == "keep_simulation"
    ]
    if not candidates:
        return ()
    candidates.sort(key=lambda way: distance_sq(center, way.centroid))
    edges: list[str] = []
    for way in candidates[:2]:
        edges.extend(edge_ids_by_osm_id.get(way.way_id, ())[:2])
    return tuple(dict.fromkeys(edges))


def distance_sq(a: OsmPoint, b: OsmPoint) -> float:
    return (a.lon - b.lon) ** 2 + (a.lat - b.lat) ** 2


def _sumo_edges_by_osm_way_id(net_index: SumoNetIndex | None) -> dict[str, tuple[str, ...]]:
    if net_index is None:
        return {}
    mutable: dict[str, list[str]] = {}
    for edge_id in sorted(net_index.edge_ids):
        base = _edge_base_osm_id(edge_id)
        if base:
            mutable.setdefault(base, []).append(edge_id)
    return {key: tuple(value) for key, value in mutable.items()}


def _edge_base_osm_id(edge_id: str) -> str:
    value = edge_id.lstrip("-")
    value = value.split("#", 1)[0]
    value = value.split("_", 1)[0]
    match = re.match(r"(\d+)", value)
    return match.group(1) if match else ""


def _display_name(tags: dict[str, str], fallback: str) -> str:
    return tags.get("name") or tags.get("name:vi") or tags.get("operator") or fallback


def _zone_id(zone_type: str, element_kind: str, element_id: str) -> str:
    return f"Z_{zone_type.upper()}_{element_kind.upper()}_{_safe_id(element_id)}"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def _relevant_tags(tags: dict[str, str]) -> dict[str, str]:
    keep_keys = {
        "name",
        "name:vi",
        "landuse",
        "amenity",
        "shop",
        "office",
        "tourism",
        "leisure",
        "public_transport",
        "railway",
        "industrial",
        "healthcare",
        "emergency",
        "highway",
        "junction",
        "bus",
        "hgv",
    }
    return {key: value for key, value in tags.items() if key in keep_keys}


def _object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise RoiPrepError(f"{key} must be an object")
    return value


def _roi_polygon(value: object) -> RoiPolygon:
    if not isinstance(value, list):
        raise RoiPrepError("ROI config must define polygon as [[lon, lat], ...]")
    points: list[OsmPoint] = []
    for index, item in enumerate(value):
        if not isinstance(item, list | tuple) or len(item) < 2:
            raise RoiPrepError(f"ROI polygon point #{index + 1} must be [lon, lat]")
        points.append(OsmPoint(lon=float(item[0]), lat=float(item[1])))
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        raise RoiPrepError("ROI polygon must contain at least 3 unique points")
    return RoiPolygon(points=tuple(points))


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _resolve_optional(base_dir: Path, value: object) -> Path | None:
    if value is None or str(value) == "":
        return None
    return _resolve(base_dir, str(value))


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
