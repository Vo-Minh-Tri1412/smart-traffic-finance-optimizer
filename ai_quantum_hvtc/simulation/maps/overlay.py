from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError, SumoNetIndex

SEMANTIC_OVERLAY_SCHEMA_VERSION = "semantic_overlay.v1"
ROI_POLYGON_OVERLAY_SCHEMA_VERSION = "roi_semantic_overlay.v2"


@dataclass(frozen=True)
class OverlayZone:
    zone_id: str
    name: str
    zone_type: str
    anchor_edges: tuple[str, ...]
    anchor_junctions: tuple[str, ...] = ()
    public_value_tags: tuple[str, ...] = ()
    notes: str = ""
    demand_enabled: bool = True
    geometry: dict[str, Any] = field(default_factory=dict)
    source_element_id: str = ""
    source_element_kind: str = ""
    source_tags: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OverlayCandidate:
    candidate_id: str
    junction_id: str
    label: str
    public_value_tags: tuple[str, ...] = ()
    caveat: str = "placeholder"


@dataclass(frozen=True)
class DemandFlowProfile:
    flow_id: str
    origin_zone: str
    destination_zone: str
    trip_purpose: str
    begin: int
    end: int
    volume: int
    vehicle_mix: dict[str, float]
    scenario_multipliers: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticOverlay:
    overlay_id: str
    name: str
    schema_version: str
    zones: dict[str, OverlayZone]
    candidates: dict[str, OverlayCandidate]
    demand_flows: dict[str, DemandFlowProfile]
    raw: dict[str, Any] = field(default_factory=dict)


def load_semantic_overlay(path: Path | str, net_index: SumoNetIndex) -> SemanticOverlay:
    overlay_path = Path(path)
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SumoMapSourceError(f"{overlay_path}: semantic overlay must be a JSON object")
    schema_version = str(data.get("schema_version", ""))
    if schema_version not in {SEMANTIC_OVERLAY_SCHEMA_VERSION, ROI_POLYGON_OVERLAY_SCHEMA_VERSION}:
        raise SumoMapSourceError(
            f"{overlay_path}: unsupported semantic overlay schema_version {schema_version!r}"
        )
    if schema_version == ROI_POLYGON_OVERLAY_SCHEMA_VERSION:
        _validate_roi_polygon_payload(data)
    overlay = SemanticOverlay(
        overlay_id=_required_string(data, "id"),
        name=_required_string(data, "name"),
        schema_version=schema_version,
        zones=_zones(data.get("zones")),
        candidates=_candidates(data.get("investment_candidates", [])),
        demand_flows=_demand_flows(data.get("demand_flows", [])),
        raw=data,
    )
    validate_semantic_overlay(overlay, net_index)
    return overlay


def validate_semantic_overlay(overlay: SemanticOverlay, net_index: SumoNetIndex) -> None:
    for zone in overlay.zones.values():
        if not zone.anchor_edges and overlay.schema_version == SEMANTIC_OVERLAY_SCHEMA_VERSION:
            raise SumoMapSourceError(f"{zone.zone_id}: zone must list at least one anchor edge")
        for edge_id in zone.anchor_edges:
            if not net_index.contains_edge(edge_id):
                raise SumoMapSourceError(f"{zone.zone_id}: unknown SUMO edge_id {edge_id}")
        for junction_id in zone.anchor_junctions:
            if not net_index.contains_junction(junction_id):
                raise SumoMapSourceError(f"{zone.zone_id}: unknown SUMO junction_id {junction_id}")

    for candidate in overlay.candidates.values():
        if not net_index.contains_junction(candidate.junction_id):
            raise SumoMapSourceError(
                f"{candidate.candidate_id}: unknown SUMO junction_id {candidate.junction_id}"
            )

    for flow in overlay.demand_flows.values():
        if flow.origin_zone not in overlay.zones:
            raise SumoMapSourceError(f"{flow.flow_id}: unknown origin_zone {flow.origin_zone}")
        if flow.destination_zone not in overlay.zones:
            raise SumoMapSourceError(
                f"{flow.flow_id}: unknown destination_zone {flow.destination_zone}"
            )
        for zone_id in (flow.origin_zone, flow.destination_zone):
            zone = overlay.zones[zone_id]
            if not zone.demand_enabled:
                raise SumoMapSourceError(f"{flow.flow_id}: demand disabled for zone {zone_id}")
            if not zone.anchor_edges:
                raise SumoMapSourceError(f"{flow.flow_id}: zone {zone_id} has no anchor edges")
        if flow.begin < 0:
            raise SumoMapSourceError(f"{flow.flow_id}: begin must be non-negative")
        if flow.end <= flow.begin:
            raise SumoMapSourceError(f"{flow.flow_id}: end must be after begin")
        if flow.volume < 0:
            raise SumoMapSourceError(f"{flow.flow_id}: volume must be non-negative")
        if any(not math.isfinite(v) or v < 0 for v in flow.vehicle_mix.values()):
            raise SumoMapSourceError(f"{flow.flow_id}: vehicle_mix must be finite and non-negative")
        if any(not math.isfinite(v) or v < 0 for v in flow.scenario_multipliers.values()):
            raise SumoMapSourceError(
                f"{flow.flow_id}: scenario_multipliers must be finite and non-negative"
            )
        mix_total = sum(flow.vehicle_mix.values())
        if abs(mix_total - 1.0) > 0.001:
            raise SumoMapSourceError(
                f"{flow.flow_id}: vehicle_mix shares must sum to 1.0, got {mix_total:.3f}"
            )


def _zones(items: object) -> dict[str, OverlayZone]:
    zones: dict[str, OverlayZone] = {}
    if not isinstance(items, list):
        raise SumoMapSourceError("zones must be an array")
    for item in items:
        if not isinstance(item, dict):
            raise SumoMapSourceError("zone rows must be objects")
        zone = OverlayZone(
            zone_id=_required_string(item, "id"),
            name=_required_string(item, "name"),
            zone_type=_required_string(item, "type"),
            anchor_edges=_tuple_strings(item.get("anchor_edges", [])),
            anchor_junctions=_tuple_strings(item.get("anchor_junctions", [])),
            public_value_tags=_tuple_strings(item.get("public_value_tags", [])),
            notes=str(item.get("notes", "")),
            demand_enabled=_boolean(item, "demand_enabled", default=True),
            geometry=item.get("geometry", {}),
            source_element_id=str(item.get("source_element_id", "")),
            source_element_kind=str(item.get("source_element_kind", "")),
            source_tags=item.get("source_tags", {}),
            raw=item,
        )
        if zone.zone_id in zones:
            raise SumoMapSourceError(f"duplicate zone id {zone.zone_id}")
        zones[zone.zone_id] = zone
    return zones


def _candidates(items: object) -> dict[str, OverlayCandidate]:
    candidates: dict[str, OverlayCandidate] = {}
    if not isinstance(items, list):
        raise SumoMapSourceError("investment_candidates must be an array")
    for item in items:
        if not isinstance(item, dict):
            raise SumoMapSourceError("investment candidate rows must be objects")
        candidate = OverlayCandidate(
            candidate_id=_required_string(item, "id"),
            junction_id=_required_string(item, "junction_id"),
            label=str(item.get("label", item["id"])),
            public_value_tags=_tuple_strings(item.get("public_value_tags", [])),
            caveat=str(item.get("caveat", "placeholder")),
        )
        if candidate.candidate_id in candidates:
            raise SumoMapSourceError(f"duplicate candidate id {candidate.candidate_id}")
        candidates[candidate.candidate_id] = candidate
    return candidates


def _demand_flows(items: object) -> dict[str, DemandFlowProfile]:
    flows: dict[str, DemandFlowProfile] = {}
    if not isinstance(items, list):
        raise SumoMapSourceError("demand_flows must be an array")
    for item in items:
        if not isinstance(item, dict):
            raise SumoMapSourceError("demand flow rows must be objects")
        flow = DemandFlowProfile(
            flow_id=_required_string(item, "id"),
            origin_zone=_required_string(item, "origin_zone"),
            destination_zone=_required_string(item, "destination_zone"),
            trip_purpose=str(item.get("trip_purpose", "")),
            begin=int(item["begin"]),
            end=int(item["end"]),
            volume=int(item["volume"]),
            vehicle_mix={str(key): float(value) for key, value in item["vehicle_mix"].items()},
            scenario_multipliers={
                str(key): float(value)
                for key, value in item.get("scenario_multipliers", {}).items()
            },
        )
        if flow.flow_id in flows:
            raise SumoMapSourceError(f"duplicate flow id {flow.flow_id}")
        flows[flow.flow_id] = flow
    return flows


def _tuple_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise SumoMapSourceError("expected an array of strings")
    return tuple(value)


def _required_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SumoMapSourceError(f"{key} must be a non-empty string")
    return value


def _boolean(item: dict[str, Any], key: str, *, default: bool) -> bool:
    value = item.get(key, default)
    if not isinstance(value, bool):
        raise SumoMapSourceError(f"{key} must be a boolean")
    return value


def _xy_point(value: object, *, label: str) -> tuple[float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in value
        )
    ):
        raise SumoMapSourceError(f"{label}: expected a finite [x, y] point")
    return float(value[0]), float(value[1])


def _validate_roi_polygon_payload(data: dict[str, Any]) -> None:
    """Retain ROI semantics, without fabricating routing anchors or activity demand."""
    if data.get("coordinate_system") != "sumo_xy":
        raise SumoMapSourceError("roi_semantic_overlay.v2 requires coordinate_system sumo_xy")
    items = data.get("zones")
    if not isinstance(items, list) or not items:
        raise SumoMapSourceError("roi_semantic_overlay.v2 requires a non-empty zones array")
    for item in items:
        if not isinstance(item, dict):
            raise SumoMapSourceError("zone rows must be objects")
        zone_id = _required_string(item, "id")
        _required_string(item, "source_element_id")
        _required_string(item, "source_element_kind")
        tags = item.get("source_tags")
        if not isinstance(tags, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in tags.items()
        ):
            raise SumoMapSourceError(f"{zone_id}: source_tags must be a string mapping")
        if "demand_enabled" not in item:
            raise SumoMapSourceError(f"{zone_id}: demand_enabled must be explicit")
        _boolean(item, "demand_enabled", default=False)
        _xy_point(item.get("centroid"), label=f"{zone_id}.centroid")
        geometry = item.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "polygon":
            raise SumoMapSourceError(f"{zone_id}: geometry must be a polygon")
        if geometry.get("coordinate_system") != "sumo_xy":
            raise SumoMapSourceError(f"{zone_id}: geometry coordinate_system must be sumo_xy")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list):
            raise SumoMapSourceError(f"{zone_id}: polygon coordinates must be an array")
        points = [_xy_point(p, label=f"{zone_id}.geometry") for p in coordinates]
        if len(set(points)) < 3:
            raise SumoMapSourceError(f"{zone_id}: polygon needs at least 3 distinct points")
        area_twice = sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(points, points[1:] + points[:1], strict=True)
        )
        if not math.isfinite(area_twice) or area_twice == 0:
            raise SumoMapSourceError(f"{zone_id}: polygon must have finite non-zero area")
