from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError, SumoNetIndex

SEMANTIC_OVERLAY_SCHEMA_VERSION = "semantic_overlay.v1"


@dataclass(frozen=True)
class OverlayZone:
    zone_id: str
    name: str
    zone_type: str
    anchor_edges: tuple[str, ...]
    anchor_junctions: tuple[str, ...] = ()
    public_value_tags: tuple[str, ...] = ()
    notes: str = ""


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
    if schema_version != SEMANTIC_OVERLAY_SCHEMA_VERSION:
        raise SumoMapSourceError(
            f"{overlay_path}: unsupported semantic overlay schema_version {schema_version!r}"
        )
    overlay = SemanticOverlay(
        overlay_id=str(data["id"]),
        name=str(data["name"]),
        schema_version=schema_version,
        zones=_zones(data.get("zones", [])),
        candidates=_candidates(data.get("investment_candidates", [])),
        demand_flows=_demand_flows(data.get("demand_flows", [])),
        raw=data,
    )
    validate_semantic_overlay(overlay, net_index)
    return overlay


def validate_semantic_overlay(overlay: SemanticOverlay, net_index: SumoNetIndex) -> None:
    for zone in overlay.zones.values():
        if not zone.anchor_edges:
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
        if flow.end <= flow.begin:
            raise SumoMapSourceError(f"{flow.flow_id}: end must be after begin")
        if flow.volume < 0:
            raise SumoMapSourceError(f"{flow.flow_id}: volume must be non-negative")
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
            zone_id=str(item["id"]),
            name=str(item["name"]),
            zone_type=str(item["type"]),
            anchor_edges=_tuple_strings(item.get("anchor_edges", [])),
            anchor_junctions=_tuple_strings(item.get("anchor_junctions", [])),
            public_value_tags=_tuple_strings(item.get("public_value_tags", [])),
            notes=str(item.get("notes", "")),
        )
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
            candidate_id=str(item["id"]),
            junction_id=str(item["junction_id"]),
            label=str(item.get("label", item["id"])),
            public_value_tags=_tuple_strings(item.get("public_value_tags", [])),
            caveat=str(item.get("caveat", "placeholder")),
        )
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
            flow_id=str(item["id"]),
            origin_zone=str(item["origin_zone"]),
            destination_zone=str(item["destination_zone"]),
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
        flows[flow.flow_id] = flow
    return flows


def _tuple_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SumoMapSourceError("expected an array of strings")
    return tuple(str(item) for item in value)
