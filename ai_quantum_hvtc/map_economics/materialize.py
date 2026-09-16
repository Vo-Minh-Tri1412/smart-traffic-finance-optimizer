"""Materialize map-economic profiles from SUMO geometry and semantic entities."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.maps.source import load_sumo_net_index, load_sumo_project

from .models import MAP_ECONOMIC_PROFILE_SCHEMA_VERSION, MapEconomicProfile, MapEconomicProfileError
from .profile import map_economic_profile_from_mapping
from .resolution import audit_profile_coverage

MAP_ECONOMIC_ASSUMPTIONS_SCHEMA_VERSION = "map_economic_assumptions.v1"


def materialize_map_economic_profile(
    *,
    project_path: Path | str,
    assumptions_path: Path | str,
) -> MapEconomicProfile:
    """Join prepared-map entities to SUMO edges and reviewed economic inputs."""

    project = load_sumo_project(project_path)
    net = load_sumo_net_index(project.source.net_path)
    overlay = _load_object(project.overlay_path)
    assumptions = _load_object(Path(assumptions_path))
    if assumptions.get("schema_version") != MAP_ECONOMIC_ASSUMPTIONS_SCHEMA_VERSION:
        raise MapEconomicProfileError(
            f"{assumptions_path}: expected {MAP_ECONOMIC_ASSUMPTIONS_SCHEMA_VERSION}"
        )
    overlay_entities = overlay.get("zones", [])
    if not isinstance(overlay_entities, list):
        raise MapEconomicProfileError(f"{project.overlay_path}: zones must be an array")
    if any(not isinstance(row, dict) for row in overlay_entities):
        raise MapEconomicProfileError(f"{project.overlay_path}: zone row must be an object")

    spatial_index = _EdgeSpatialIndex(net.edge_shapes)
    max_distance = float(assumptions.get("maximum_nearest_edge_distance_m", 1000.0))
    if not math.isfinite(max_distance) or max_distance < 0:
        raise MapEconomicProfileError("maximum_nearest_edge_distance_m must be finite and >= 0")
    building_overrides = _string_mapping(assumptions.get("building_valuation_by_id", {}))
    zone_valuations = _string_mapping(assumptions.get("zone_valuation_by_type", {}))

    buildings: list[dict[str, Any]] = []
    zone_buildings: dict[str, list[str]] = defaultdict(list)
    zone_edges: dict[str, set[str]] = defaultdict(set)
    zone_types: dict[str, str] = {}
    edge_buildings: dict[str, list[str]] = defaultdict(list)
    for raw in sorted(overlay_entities, key=lambda row: str(row.get("id", ""))):
        if not isinstance(raw, dict):
            raise MapEconomicProfileError(f"{project.overlay_path}: zone row must be an object")
        building_id = str(raw.get("id", ""))
        if not building_id:
            raise MapEconomicProfileError(f"{project.overlay_path}: entity id is missing")
        zone_type = str(raw.get("type", "neutral"))
        zone_id = str(raw.get("zone_group_id", f"ZG_{zone_type.upper()}"))
        zone_types[zone_id] = zone_type
        centroid = _centroid(raw)
        raw_anchors = tuple(
            edge_id
            for edge_id in _strings(raw.get("anchor_edges", []), "anchor_edges")
            if edge_id in net.edge_ids
        )
        nearest_distance: float | None = None
        if raw_anchors:
            edge_ids = raw_anchors
            method = "exact_anchor"
        elif centroid is not None:
            nearest_edge, nearest_distance = spatial_index.nearest(*centroid)
            if nearest_edge and nearest_distance <= max_distance:
                edge_ids = (nearest_edge,)
                method = "derived_nearest_edge"
            else:
                edge_ids = ()
                method = "unmapped"
        else:
            edge_ids = ()
            method = "unmapped"
        demand_enabled = bool(raw.get("demand_enabled", zone_type != "neutral"))
        building = {
            "building_id": building_id,
            "name": str(raw.get("name", building_id)),
            "entity_kind": str(raw.get("subtype", raw.get("source_element_kind", "entity"))),
            "zone_id": zone_id,
            "edge_ids": list(edge_ids),
            "mapping_method": method,
            "nearest_edge_distance_m": (
                None
                if nearest_distance is None or not math.isfinite(nearest_distance)
                else round(nearest_distance, 6)
            ),
            "demand_enabled": demand_enabled,
            "source_element_id": str(raw.get("source_element_id", "")),
            "confidence": raw.get("confidence"),
            "valuation_id": building_overrides.get(building_id, ""),
            "source_tags": _flat_string_mapping(raw.get("source_tags", {})),
        }
        buildings.append(building)
        zone_buildings[zone_id].append(building_id)
        for edge_id in edge_ids:
            zone_edges[zone_id].add(edge_id)
            edge_buildings[edge_id].append(building_id)

    corridors_raw = assumptions.get("corridors", [])
    if not isinstance(corridors_raw, list):
        raise MapEconomicProfileError("assumptions.corridors must be an array")
    edge_corridors: dict[str, list[str]] = defaultdict(list)
    corridors: list[dict[str, Any]] = []
    for row in corridors_raw:
        if not isinstance(row, dict):
            raise MapEconomicProfileError("assumptions.corridors rows must be objects")
        corridor = dict(row)
        corridor_id = str(corridor.get("corridor_id", ""))
        for edge_id in _strings(corridor.get("edge_ids", []), "corridor.edge_ids"):
            edge_corridors[edge_id].append(corridor_id)
        corridors.append(corridor)

    zones = [
        {
            "zone_id": zone_id,
            "name": zone_id,
            "zone_type": zone_types[zone_id],
            "building_ids": sorted(zone_buildings[zone_id]),
            "edge_ids": sorted(zone_edges[zone_id]),
            "valuation_id": zone_valuations.get(zone_types[zone_id], ""),
        }
        for zone_id in sorted(zone_buildings)
    ]
    building_zone = {row["building_id"]: row["zone_id"] for row in buildings}
    edges = []
    for edge_id in sorted(net.edge_ids):
        attached_buildings = sorted(edge_buildings.get(edge_id, []))
        edges.append(
            {
                "edge_id": edge_id,
                "zone_ids": sorted({building_zone[item] for item in attached_buildings}),
                "building_ids": attached_buildings,
                "corridor_ids": sorted(edge_corridors.get(edge_id, [])),
            }
        )

    metadata_input = _object(assumptions, "metadata")
    overlay_caveats = overlay.get("caveats", [])
    if not isinstance(overlay_caveats, list):
        overlay_caveats = []
    configured_caveats = metadata_input.get("caveats", [])
    if not isinstance(configured_caveats, list):
        raise MapEconomicProfileError("assumptions.metadata.caveats must be an array")
    profile_data: dict[str, Any] = {
        "schema_version": MAP_ECONOMIC_PROFILE_SCHEMA_VERSION,
        "metadata": {
            **metadata_input,
            "map_project_id": project.project_id,
            "source_net_sha256": _sha256(project.source.net_path),
            "semantic_overlay_sha256": _sha256(project.overlay_path),
            "caveats": [
                *[str(item) for item in configured_caveats],
                *[str(item) for item in overlay_caveats],
                "Prepared-map entities are not all verified physical buildings.",
                "Empty anchor_edges were joined by deterministic nearest-edge geometry; "
                "this is derived structural coverage, not exact economic calibration.",
            ],
        },
        "sources": assumptions.get("sources", []),
        "valuations": assumptions.get("valuations", []),
        "global_valuation_id": assumptions.get("global_valuation_id", ""),
        "buildings": buildings,
        "zones": zones,
        "edges": edges,
        "corridors": corridors,
        "od_pairs": assumptions.get("od_pairs", []),
        "investment_candidates": assumptions.get("investment_candidates", []),
        "reward_policy": assumptions.get("reward_policy", {}),
        "coverage_policy": assumptions.get("coverage_policy", {}),
        "coverage": None,
    }
    profile = map_economic_profile_from_mapping(
        profile_data, source=f"materialized from {project_path}"
    )
    return replace(profile, coverage=audit_profile_coverage(profile))


def coverage_payload(profile: MapEconomicProfile) -> dict[str, Any]:
    report = profile.coverage or audit_profile_coverage(profile)
    return {
        "schema_version": "map_economic_coverage.v1",
        "profile_id": profile.metadata.profile_id,
        "map_project_id": profile.metadata.map_project_id,
        "coverage": report.to_dict(),
        "notes": [
            "Structural edge coverage includes explicitly labelled derived nearest-edge joins.",
            "Economic calibration coverage counts source-backed numeric records separately.",
            "Demand-weighted coverage is unavailable until reviewed OD demand weights exist.",
        ],
    }


@dataclass(frozen=True)
class _Segment:
    edge_id: str
    ax: float
    ay: float
    bx: float
    by: float


class _EdgeSpatialIndex:
    def __init__(
        self,
        edge_shapes: dict[str, tuple[tuple[float, float], ...]],
        *,
        cell_size: float = 250.0,
    ) -> None:
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list[_Segment]] = defaultdict(list)
        self.max_radius = 0
        for edge_id in sorted(edge_shapes):
            points = edge_shapes[edge_id]
            for left, right in zip(points, points[1:], strict=False):
                segment = _Segment(edge_id, left[0], left[1], right[0], right[1])
                min_x = math.floor(min(left[0], right[0]) / cell_size)
                max_x = math.floor(max(left[0], right[0]) / cell_size)
                min_y = math.floor(min(left[1], right[1]) / cell_size)
                max_y = math.floor(max(left[1], right[1]) / cell_size)
                for cell_x in range(min_x, max_x + 1):
                    for cell_y in range(min_y, max_y + 1):
                        self.cells[(cell_x, cell_y)].append(segment)
        if self.cells:
            xs = [cell[0] for cell in self.cells]
            ys = [cell[1] for cell in self.cells]
            self.max_radius = max(max(xs) - min(xs), max(ys) - min(ys)) + 2

    def nearest(self, x: float, y: float) -> tuple[str, float]:
        if not self.cells:
            return "", math.inf
        origin = (math.floor(x / self.cell_size), math.floor(y / self.cell_size))
        best_edge = ""
        best_distance = math.inf
        seen: set[_Segment] = set()
        for radius in range(self.max_radius + 1):
            for cell in _ring(origin, radius):
                for segment in self.cells.get(cell, []):
                    if segment in seen:
                        continue
                    seen.add(segment)
                    distance = _point_segment_distance(x, y, segment)
                    if distance < best_distance or (
                        distance == best_distance and segment.edge_id < best_edge
                    ):
                        best_edge = segment.edge_id
                        best_distance = distance
            if math.isfinite(best_distance):
                required_radius = math.ceil(best_distance / self.cell_size) + 2
                if radius >= required_radius:
                    break
        return best_edge, best_distance


def _ring(origin: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    if radius == 0:
        return [origin]
    left, bottom = origin[0] - radius, origin[1] - radius
    right, top = origin[0] + radius, origin[1] + radius
    result = [(x, bottom) for x in range(left, right + 1)]
    result.extend((x, top) for x in range(left, right + 1))
    result.extend((left, y) for y in range(bottom + 1, top))
    result.extend((right, y) for y in range(bottom + 1, top))
    return result


def _point_segment_distance(x: float, y: float, segment: _Segment) -> float:
    dx = segment.bx - segment.ax
    dy = segment.by - segment.ay
    squared_length = dx * dx + dy * dy
    if squared_length == 0:
        return math.hypot(x - segment.ax, y - segment.ay)
    projection = ((x - segment.ax) * dx + (y - segment.ay) * dy) / squared_length
    projection = min(1.0, max(0.0, projection))
    return math.hypot(x - (segment.ax + projection * dx), y - (segment.ay + projection * dy))


def _centroid(row: dict[str, Any]) -> tuple[float, float] | None:
    value = row.get("centroid")
    if isinstance(value, list) and len(value) >= 2:
        return float(value[0]), float(value[1])
    geometry = row.get("geometry")
    if not isinstance(geometry, dict):
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        return None
    points = [item for item in coordinates if isinstance(item, list) and len(item) >= 2]
    if not points:
        return None
    return (
        sum(float(point[0]) for point in points) / len(points),
        sum(float(point[1]) for point in points) / len(points),
    )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MapEconomicProfileError(f"{path}: cannot read JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise MapEconomicProfileError(f"{path}: root value must be an object")
    return value


def _object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise MapEconomicProfileError(f"assumptions.{key} must be an object")
    return dict(value)


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MapEconomicProfileError(f"{name} must be an array of strings")
    return tuple(value)


def _string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise MapEconomicProfileError("expected an object mapping strings to strings")
    return {str(key): str(item) for key, item in value.items()}


def _flat_string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        for key, item in value.items()
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
