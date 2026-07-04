from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_OSM_PATH = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "01_raw_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.osm"
)
DEFAULT_NET_PATH = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "02_prepared_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.net.xml"
)

ZONE_COLORS = {
    "neutral": "#eeeeee",
    "residential": "#81c784",
    "commercial": "#fdb462",
    "market_retail": "#ffb74d",
    "education": "#64b5f6",
    "healthcare": "#ef5350",
    "industrial": "#8d6e63",
    "port_logistics": "#ab47bc",
    "transport_hub": "#4dd0e1",
    "public_service": "#b39ddb",
    "nightlife": "#ff80ab",
    "leisure_tourism": "#9ccc65",
    "mixed": "#b0bec5",
}

ZONE_LABELS = {
    "neutral": "Neutral / untagged buildable land",
    "residential": "Residential",
    "commercial": "Commercial",
    "market_retail": "Market / retail",
    "education": "Education",
    "healthcare": "Healthcare",
    "industrial": "Industrial",
    "port_logistics": "Port / logistics",
    "transport_hub": "Transport hub",
    "public_service": "Public service",
    "nightlife": "Nightlife",
    "leisure_tourism": "Leisure / tourism",
    "mixed": "Mixed / uncertain",
}

ZONE_DRAW_ORDER = [
    "neutral",
    "mixed",
    "leisure_tourism",
    "residential",
    "commercial",
    "market_retail",
    "industrial",
    "port_logistics",
    "transport_hub",
    "education",
    "healthcare",
    "public_service",
    "nightlife",
]


@dataclass(frozen=True)
class NetTransform:
    conv_min_x: float
    conv_min_y: float
    conv_max_x: float
    conv_max_y: float
    orig_min_lon: float
    orig_min_lat: float
    orig_max_lon: float
    orig_max_lat: float

    def lonlat_to_xy(self, lon: float, lat: float) -> tuple[float, float]:
        x_ratio = (lon - self.orig_min_lon) / (self.orig_max_lon - self.orig_min_lon)
        y_ratio = (lat - self.orig_min_lat) / (self.orig_max_lat - self.orig_min_lat)
        x = self.conv_min_x + x_ratio * (self.conv_max_x - self.conv_min_x)
        y = self.conv_min_y + y_ratio * (self.conv_max_y - self.conv_min_y)
        return x, y


@dataclass(frozen=True)
class OsmWayRecord:
    way_id: str
    node_refs: tuple[str, ...]
    tags: dict[str, str]


@dataclass(frozen=True)
class ZonePolygon:
    zone_id: str
    zone_type: str
    source_tags: dict[str, str]
    geometry: Polygon | MultiPolygon


@dataclass(frozen=True)
class SumoRoadLayer:
    road_lines: tuple[LineString, ...]
    road_mask: Polygon | MultiPolygon
    map_boundary: Polygon | MultiPolygon
    traffic_light_points: tuple[Point, ...]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a static buildable-zone heatmap: true OSM zone polygons minus SUMO road "
            "mask, plus neutral buildable land for untagged non-road areas."
        )
    )
    parser.add_argument(
        "--osm",
        type=Path,
        default=DEFAULT_OSM_PATH,
    )
    parser.add_argument(
        "--net",
        type=Path,
        default=DEFAULT_NET_PATH,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "render/outputs/zone_map_diagnostics",
    )
    parser.add_argument(
        "--prefix",
        default="full_map",
        help="Filename prefix for generated PNG/JSON files.",
    )
    parser.add_argument(
        "--road-buffer-m",
        type=float,
        default=7.0,
        help="Minimum no-building road mask radius around SUMO lane centerlines.",
    )
    parser.add_argument(
        "--road-neighborhood-buffer-m",
        type=float,
        default=120.0,
        help=(
            "Neutral-zone boundary is derived from the road network buffered by this distance. "
            "This avoids a fake rectangular full-map fill when no administrative boundary exists."
        ),
    )
    parser.add_argument(
        "--boundary-ratio",
        type=float,
        default=0.08,
        help="Concave-hull ratio for road-network map boundary; lower is tighter.",
    )
    parser.add_argument(
        "--min-polygon-area-m2",
        type=float,
        default=45.0,
        help="Drop tiny buildable polygon slivers below this area.",
    )
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    transform, roads = load_sumo_road_layer(
        args.net,
        road_buffer_m=args.road_buffer_m,
        road_neighborhood_buffer_m=args.road_neighborhood_buffer_m,
        boundary_ratio=args.boundary_ratio,
    )
    raw_zones = load_osm_zone_polygons(args.osm, transform)
    buildable_zones = subtract_road_mask(raw_zones, roads.road_mask, args.min_polygon_area_m2)
    neutral_geometry = build_neutral_geometry(
        map_boundary=roads.map_boundary,
        road_mask=roads.road_mask,
        buildable_zones=buildable_zones,
        min_polygon_area_m2=args.min_polygon_area_m2,
    )

    png_path = args.output_root / f"{args.prefix}_buildable_zone_heatmap_no_road_overlap.png"
    summary_path = args.output_root / f"{args.prefix}_buildable_zone_heatmap_summary.json"
    overlay_path = args.output_root / f"{args.prefix}_buildable_semantic_overlay.generated.json"
    render_heatmap(
        png_path,
        roads=roads,
        zones=buildable_zones,
        neutral_geometry=neutral_geometry,
        title="Buildable zone heatmap: OSM zones clipped away from SUMO roads",
    )
    summary = summarize(
        osm_path=args.osm,
        net_path=args.net,
        roads=roads,
        raw_zones=raw_zones,
        buildable_zones=buildable_zones,
        neutral_geometry=neutral_geometry,
        road_buffer_m=args.road_buffer_m,
        road_neighborhood_buffer_m=args.road_neighborhood_buffer_m,
        boundary_ratio=args.boundary_ratio,
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    overlay = build_semantic_overlay_payload(
        overlay_id=f"{args.prefix}_buildable_overlay",
        zones=buildable_zones,
        neutral_geometry=neutral_geometry,
    )
    overlay_path.write_text(
        json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[OK] heatmap={png_path}")
    print(f"[OK] summary={summary_path}")
    print(f"[OK] overlay={overlay_path}")
    return 0


def load_sumo_road_layer(
    net_path: Path,
    *,
    road_buffer_m: float,
    road_neighborhood_buffer_m: float,
    boundary_ratio: float,
) -> tuple[NetTransform, SumoRoadLayer]:
    tree = ET.parse(net_path)
    root = tree.getroot()
    location = root.find("location")
    if location is None:
        raise ValueError(f"{net_path}: missing SUMO <location>")
    conv = [float(value) for value in location.attrib["convBoundary"].split(",")]
    orig = [float(value) for value in location.attrib["origBoundary"].split(",")]
    transform = NetTransform(
        conv_min_x=conv[0],
        conv_min_y=conv[1],
        conv_max_x=conv[2],
        conv_max_y=conv[3],
        orig_min_lon=orig[0],
        orig_min_lat=orig[1],
        orig_max_lon=orig[2],
        orig_max_lat=orig[3],
    )

    road_lines: list[LineString] = []
    road_buffers = []
    for edge in root.findall("edge"):
        if edge.attrib.get("function") == "internal":
            continue
        edge_type = edge.attrib.get("type", "")
        buffer_m = max(road_buffer_m, _road_buffer_for_edge_type(edge_type))
        shape = edge.attrib.get("shape")
        if not shape:
            lane = edge.find("lane")
            shape = lane.attrib.get("shape") if lane is not None else None
        if not shape:
            continue
        coords = _shape_to_xy(shape)
        if len(coords) < 2:
            continue
        line = LineString(coords).simplify(0.5, preserve_topology=False)
        if line.length <= 0:
            continue
        road_lines.append(line)
        road_buffers.append(
            line.buffer(buffer_m, quad_segs=1, cap_style="flat", join_style="mitre")
        )

    if not road_lines:
        raise ValueError(f"{net_path}: no non-internal SUMO lanes with shape found")

    road_mask = _clean_geometry(unary_union(road_buffers))
    # We intentionally derive the map fill boundary from SUMO roads instead of a bbox.
    # It is not an administrative boundary; it is a "renderable urban footprint"
    # around actual routable geometry. This keeps neutral zones from becoming a fake rectangle.
    map_boundary = _clean_geometry(
        road_mask.buffer(
            road_neighborhood_buffer_m,
            quad_segs=2,
            cap_style="round",
            join_style="round",
        ).simplify(8.0, preserve_topology=True)
    )

    traffic_lights = []
    for junction in root.findall("junction"):
        if junction.attrib.get("type") != "traffic_light":
            continue
        traffic_lights.append(Point(float(junction.attrib["x"]), float(junction.attrib["y"])))

    return transform, SumoRoadLayer(
        road_lines=tuple(road_lines),
        road_mask=road_mask,
        map_boundary=map_boundary,
        traffic_light_points=tuple(traffic_lights),
    )


def _road_buffer_for_edge_type(edge_type: str) -> float:
    if "motorway" in edge_type or "trunk" in edge_type:
        return 14.0
    if "primary" in edge_type or "secondary" in edge_type:
        return 10.0
    if "tertiary" in edge_type:
        return 8.0
    if "service" in edge_type or "path" in edge_type or "footway" in edge_type:
        return 4.5
    return 6.0


def _shape_to_xy(shape: str) -> list[tuple[float, float]]:
    coords = []
    for pair in shape.split():
        x_raw, y_raw = pair.split(",")[:2]
        coords.append((float(x_raw), float(y_raw)))
    return coords


def load_osm_zone_polygons(osm_path: Path, transform: NetTransform) -> tuple[ZonePolygon, ...]:
    root = ET.parse(osm_path).getroot()
    nodes: dict[str, tuple[float, float]] = {}
    ways: dict[str, OsmWayRecord] = {}
    for node in root.findall("node"):
        nodes[node.attrib["id"]] = transform.lonlat_to_xy(
            float(node.attrib["lon"]),
            float(node.attrib["lat"]),
        )
    for way in root.findall("way"):
        ways[way.attrib["id"]] = OsmWayRecord(
            way_id=way.attrib["id"],
            node_refs=tuple(nd.attrib["ref"] for nd in way.findall("nd")),
            tags=_tags(way),
        )

    zones: list[ZonePolygon] = []
    for way in ways.values():
        classification = classify_zone_tags(way.tags)
        if classification is None or not _is_closed_way(way):
            continue
        polygon = _polygon_from_way(way, nodes)
        if polygon is None:
            continue
        zone_type = classification[0]
        zones.append(
            ZonePolygon(
                zone_id=f"way/{way.way_id}",
                zone_type=zone_type,
                source_tags=_relevant_zone_tags(way.tags),
                geometry=polygon,
            )
        )

    for relation in root.findall("relation"):
        relation_tags = _tags(relation)
        classification = classify_zone_tags(relation_tags)
        if classification is None:
            continue
        zone_type = classification[0]
        outer_polygons: list[Polygon | MultiPolygon] = []
        for member in relation.findall("member"):
            if member.attrib.get("type") != "way" or member.attrib.get("role", "") not in {
                "",
                "outer",
            }:
                continue
            way = ways.get(member.attrib.get("ref", ""))
            if way is None or not _is_closed_way(way):
                continue
            polygon = _polygon_from_way(way, nodes)
            if polygon is None:
                continue
            outer_polygons.append(polygon)
        if outer_polygons:
            zones.append(
                ZonePolygon(
                    zone_id=f"relation/{relation.attrib['id']}",
                    zone_type=zone_type,
                    source_tags=_relevant_zone_tags(relation_tags),
                    geometry=_clean_geometry(unary_union(outer_polygons)),
                )
            )
    return tuple(zones)


def classify_zone_tags(tags: dict[str, str]) -> tuple[str, str, float] | None:
    landuse = tags.get("landuse", "")
    amenity = tags.get("amenity", "")
    building = tags.get("building", "")
    industrial = tags.get("industrial", "")
    public_transport = tags.get("public_transport", "")
    railway = tags.get("railway", "")
    shop = tags.get("shop", "")
    office = tags.get("office", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")

    if industrial in {"port", "depot", "warehouse"} or "port" in tags.get("name", "").lower():
        return "port_logistics", industrial or "port", 0.88
    if landuse == "industrial" or industrial or building in {"industrial", "warehouse", "factory"}:
        return "industrial", industrial or landuse or building, 0.84
    if (
        amenity in {"hospital", "clinic", "doctors"}
        or healthcare
        or building in {"hospital", "clinic"}
    ):
        return "healthcare", amenity or healthcare or building, 0.86
    if amenity in {"school", "university", "college", "kindergarten", "library"} or building in {
        "school",
        "university",
        "college",
        "kindergarten",
    }:
        return "education", amenity or building, 0.84
    if public_transport or railway in {"station", "halt", "tram_stop"} or amenity == "bus_station":
        return "transport_hub", public_transport or railway or amenity, 0.78
    if landuse == "retail" or amenity == "marketplace":
        return "market_retail", landuse or amenity, 0.82
    if landuse == "commercial" or shop or office or building in {"commercial", "retail", "office"}:
        return "commercial", landuse or shop or office or building, 0.80
    if landuse == "residential" or building in {
        "apartments",
        "residential",
        "house",
        "detached",
        "dormitory",
    }:
        return "residential", landuse or building, 0.80
    if amenity in {"police", "fire_station", "townhall", "post_office", "courthouse"}:
        return "public_service", amenity, 0.72
    if amenity in {"bar", "pub", "nightclub", "biergarten"}:
        return "nightlife", amenity, 0.72
    if tourism or leisure:
        return "leisure_tourism", tourism or leisure, 0.65
    return None


def subtract_road_mask(
    zones: tuple[ZonePolygon, ...],
    road_mask: Polygon | MultiPolygon,
    min_polygon_area_m2: float,
) -> tuple[ZonePolygon, ...]:
    clipped: list[ZonePolygon] = []
    for zone in zones:
        buildable = _clean_geometry(zone.geometry.difference(road_mask))
        buildable = _drop_small_polygons(buildable, min_polygon_area_m2)
        if buildable.is_empty:
            continue
        clipped.append(
            ZonePolygon(
                zone_id=zone.zone_id,
                zone_type=zone.zone_type,
                source_tags=zone.source_tags,
                geometry=buildable,
            )
        )
    return tuple(clipped)


def build_neutral_geometry(
    *,
    map_boundary: Polygon | MultiPolygon,
    road_mask: Polygon | MultiPolygon,
    buildable_zones: tuple[ZonePolygon, ...],
    min_polygon_area_m2: float,
) -> Polygon | MultiPolygon | GeometryCollection:
    semantic_union = (
        unary_union([zone.geometry for zone in buildable_zones])
        if buildable_zones
        else GeometryCollection()
    )
    neutral = _clean_geometry(map_boundary.difference(road_mask).difference(semantic_union))
    return _drop_small_polygons(neutral, max(min_polygon_area_m2, 350.0))


def render_heatmap(
    path: Path,
    *,
    roads: SumoRoadLayer,
    zones: tuple[ZonePolygon, ...],
    neutral_geometry: Polygon | MultiPolygon | GeometryCollection,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(18, 14), dpi=180)
    _draw_geometry(
        ax,
        neutral_geometry,
        facecolor=ZONE_COLORS["neutral"],
        edgecolor="#d6d6d6",
        alpha=0.55,
        zorder=1,
    )

    for zone_type in ZONE_DRAW_ORDER:
        if zone_type == "neutral":
            continue
        for zone in [candidate for candidate in zones if candidate.zone_type == zone_type]:
            _draw_geometry(
                ax,
                zone.geometry,
                facecolor=ZONE_COLORS.get(zone_type, ZONE_COLORS["mixed"]),
                edgecolor=ZONE_COLORS.get(zone_type, ZONE_COLORS["mixed"]),
                alpha=0.58,
                zorder=2,
            )

    for line in roads.road_lines:
        xs, ys = line.xy
        ax.plot(xs, ys, color="#202020", linewidth=0.55, alpha=0.70, zorder=4)

    if roads.traffic_light_points:
        ax.scatter(
            [point.x for point in roads.traffic_light_points],
            [point.y for point in roads.traffic_light_points],
            marker="x",
            color="#101010",
            s=9,
            linewidths=0.65,
            zorder=5,
        )

    counts = count_zones(zones)
    handles = [
        Patch(facecolor=ZONE_COLORS["neutral"], edgecolor="#d6d6d6", label="Neutral buildable land")
    ]
    for zone_type in ZONE_DRAW_ORDER:
        if zone_type == "neutral" or not counts.get(zone_type):
            continue
        handles.append(
            Patch(
                facecolor=ZONE_COLORS.get(zone_type, ZONE_COLORS["mixed"]),
                edgecolor=ZONE_COLORS.get(zone_type, ZONE_COLORS["mixed"]),
                label=f"{ZONE_LABELS.get(zone_type, zone_type)} ({counts[zone_type]})",
            )
        )
    handles.append(
        Patch(
            facecolor="#202020",
            edgecolor="#202020",
            label=f"SUMO roads / no-build mask ({len(roads.road_lines)} lanes)",
        )
    )
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=True)

    minx, miny, maxx, maxy = roads.map_boundary.bounds
    pad_x = (maxx - minx) * 0.03
    pad_y = (maxy - miny) * 0.03
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("SUMO x / meters")
    ax.set_ylabel("SUMO y / meters")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def summarize(
    *,
    osm_path: Path,
    net_path: Path,
    roads: SumoRoadLayer,
    raw_zones: tuple[ZonePolygon, ...],
    buildable_zones: tuple[ZonePolygon, ...],
    neutral_geometry: Polygon | MultiPolygon | GeometryCollection,
    road_buffer_m: float,
    road_neighborhood_buffer_m: float,
    boundary_ratio: float,
) -> dict[str, Any]:
    raw_counts = count_zones(raw_zones)
    buildable_counts = count_zones(buildable_zones)
    return {
        "source_osm": str(osm_path),
        "source_sumo_net": str(net_path),
        "road_buffer_m": road_buffer_m,
        "road_neighborhood_buffer_m": road_neighborhood_buffer_m,
        "boundary_ratio": boundary_ratio,
        "road_lane_line_count": len(roads.road_lines),
        "traffic_light_count": len(roads.traffic_light_points),
        "raw_zone_polygon_count": len(raw_zones),
        "buildable_zone_polygon_count": len(buildable_zones),
        "raw_zone_counts": raw_counts,
        "buildable_zone_counts": buildable_counts,
        "area_m2": {
            "map_boundary": round(roads.map_boundary.area, 2),
            "road_no_build_mask": round(roads.road_mask.area, 2),
            "raw_semantic_zones": round(sum(zone.geometry.area for zone in raw_zones), 2),
            "buildable_semantic_zones": round(
                sum(zone.geometry.area for zone in buildable_zones), 2
            ),
            "neutral_buildable": round(neutral_geometry.area, 2),
        },
        "note": (
            "Semantic zone polygons are true closed OSM geometry clipped by the SUMO road "
            "no-build mask. Neutral is the remaining road-neighborhood map boundary minus "
            "roads and semantic buildable zones; it is for generic visual fill and should not "
            "generate economic demand by default."
        ),
    }


def build_semantic_overlay_payload(
    *,
    overlay_id: str,
    zones: tuple[ZonePolygon, ...],
    neutral_geometry: Polygon | MultiPolygon | GeometryCollection,
) -> dict[str, Any]:
    payload_zones: list[dict[str, Any]] = []
    for zone in zones:
        for part_index, polygon in enumerate(_iter_polygons(zone.geometry)):
            payload_zones.append(
                _zone_overlay_payload(
                    zone_id=f"{_safe_id(zone.zone_id)}_P{part_index + 1}",
                    name=_display_zone_name(zone.zone_type, zone.source_tags, zone.zone_id),
                    zone_type=zone.zone_type,
                    source_element_id=zone.zone_id,
                    source_tags=zone.source_tags,
                    geometry=polygon,
                    confidence=0.82,
                    demand_enabled=True,
                )
            )
    for part_index, polygon in enumerate(_iter_polygons(neutral_geometry)):
        payload_zones.append(
            _zone_overlay_payload(
                zone_id=f"Z_NEUTRAL_BUILDABLE_{part_index + 1:04d}",
                name="Neutral buildable land",
                zone_type="neutral",
                source_element_id="neutral_buildable",
                source_tags={
                    "synthetic": "true",
                    "demand_enabled": "false",
                    "source": "map_boundary_minus_roads_and_semantic_zones",
                },
                geometry=polygon,
                confidence=0.35,
                demand_enabled=False,
            )
        )
    return {
        "schema_version": "roi_semantic_overlay.v2",
        "id": overlay_id,
        "name": "Buildable semantic overlay clipped away from SUMO roads",
        "coordinate_system": "sumo_xy",
        "zones": payload_zones,
        "caveats": [
            "Zone geometry is in SUMO x/y meters, not lon/lat.",
            "Semantic zones are true OSM polygons after subtracting a SUMO road no-build mask.",
            "Neutral zones are visual background only and must not generate demand by default.",
            "Building assets should spawn inside these buildable polygons, never raw OSM polygons.",
        ],
    }


def _zone_overlay_payload(
    *,
    zone_id: str,
    name: str,
    zone_type: str,
    source_element_id: str,
    source_tags: dict[str, str],
    geometry: Polygon,
    confidence: float,
    demand_enabled: bool,
) -> dict[str, Any]:
    centroid = geometry.centroid
    return {
        "id": zone_id,
        "name": name,
        "type": zone_type,
        "subtype": "buildable_polygon",
        "source_element_id": source_element_id,
        "source_element_kind": "buildable_geometry",
        "source_tags": source_tags,
        "confidence": confidence,
        "geometry": {
            "type": "polygon",
            "coordinate_system": "sumo_xy",
            "coordinates": _polygon_exterior_coordinates(geometry),
        },
        "centroid": [centroid.x, centroid.y],
        "anchor_edges": [],
        "anchor_junctions": [],
        "manual_review_required": False,
        "zone_group_id": f"ZG_{zone_type.upper()}",
        "demand_enabled": demand_enabled,
        "traffic_role": (
            "background_no_demand" if zone_type == "neutral" else "semantic_zone_flow_anchor"
        ),
        "economic_role": (
            "visual_background_only" if zone_type == "neutral" else "semantic_public_value_zone"
        ),
    }


def _polygon_exterior_coordinates(polygon: Polygon) -> list[list[float]]:
    return [[round(float(x), 3), round(float(y), 3)] for x, y in polygon.exterior.coords]


def _display_zone_name(zone_type: str, tags: dict[str, str], fallback: str) -> str:
    return tags.get("name") or tags.get("name:vi") or ZONE_LABELS.get(zone_type, fallback)


def _safe_id(value: str) -> str:
    output = []
    for character in value:
        if character.isalnum():
            output.append(character)
        else:
            output.append("_")
    return "".join(output).strip("_") or "ZONE"


def count_zones(zones: tuple[ZonePolygon, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for zone in zones:
        counts[zone.zone_type] = counts.get(zone.zone_type, 0) + 1
    return dict(sorted(counts.items()))


def _draw_geometry(
    ax: Any,
    geometry: Polygon | MultiPolygon | GeometryCollection,
    *,
    facecolor: str,
    edgecolor: str,
    alpha: float,
    zorder: int,
) -> None:
    for polygon in _iter_polygons(geometry):
        coords = list(polygon.exterior.coords)
        patch = MplPolygon(
            coords,
            closed=True,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=0.18,
            alpha=alpha,
            zorder=zorder,
        )
        ax.add_patch(patch)


def _iter_polygons(geometry: Polygon | MultiPolygon | GeometryCollection):
    if geometry.is_empty:
        return
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _iter_polygons(part)


def _polygon_from_way(
    way: OsmWayRecord,
    nodes: dict[str, tuple[float, float]],
) -> Polygon | MultiPolygon | None:
    coords = [nodes[ref] for ref in way.node_refs if ref in nodes]
    if len(coords) < 4:
        return None
    polygon = Polygon(coords)
    if polygon.area <= 0:
        return None
    valid = _clean_geometry(polygon)
    if valid.is_empty or not isinstance(valid, Polygon | MultiPolygon):
        return None
    return valid


def _is_closed_way(way: OsmWayRecord) -> bool:
    return len(way.node_refs) >= 4 and way.node_refs[0] == way.node_refs[-1]


def _drop_small_polygons(
    geometry: Polygon | MultiPolygon | GeometryCollection,
    min_area: float,
) -> Polygon | MultiPolygon | GeometryCollection:
    polygons = [polygon for polygon in _iter_polygons(geometry) if polygon.area >= min_area]
    if not polygons:
        return GeometryCollection()
    return _clean_geometry(unary_union(polygons))


def _clean_geometry(geometry: Any) -> Any:
    if geometry.is_empty:
        return geometry
    valid = make_valid(geometry)
    if valid.is_empty:
        return valid
    return valid.buffer(0)


def _tags(element: ET.Element) -> dict[str, str]:
    return {
        str(tag.attrib.get("k", "")): str(tag.attrib.get("v", ""))
        for tag in element.findall("tag")
        if tag.attrib.get("k")
    }


def _relevant_zone_tags(tags: dict[str, str]) -> dict[str, str]:
    keep = {
        "name",
        "name:vi",
        "landuse",
        "amenity",
        "building",
        "industrial",
        "public_transport",
        "railway",
        "shop",
        "office",
        "tourism",
        "leisure",
        "healthcare",
    }
    return {key: value for key, value in tags.items() if key in keep}


if __name__ == "__main__":
    raise SystemExit(main())
