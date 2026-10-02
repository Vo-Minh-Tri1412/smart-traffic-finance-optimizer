from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.engines.sumo.config import resolve_sumo_binary
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.maps.overlay import SemanticOverlay, validate_semantic_overlay
from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError, SumoNetIndex


@dataclass(frozen=True)
class DemandGenerationResult:
    trips: Path
    routes: Path
    qa_json: Path
    attempted_trips: int
    routed_trips: int
    failed_trips: int
    intended_demand_ledger: Path | None = None


def generate_sumo_demand(
    *,
    overlay: SemanticOverlay,
    net_index: SumoNetIndex,
    net_path: Path,
    scenario_id: str,
    work_dir: Path,
    seed: int = 42,
    duarouter_binary: str = "duarouter",
) -> DemandGenerationResult:
    # A polygon inventory is valid map data, not evidence that any trips were supplied.
    validate_semantic_overlay(overlay, net_index)
    if not overlay.demand_flows:
        raise SumoMapSourceError(
            f"{overlay.overlay_id}: no demand_flows supplied; polygon inventory is not demand. "
            "Provide an explicit demand dataset before running SUMO."
        )
    unknown_types = {
        key for flow in overlay.demand_flows.values() for key in flow.vehicle_mix
    } - _vehicle_types().keys()
    if unknown_types:
        raise SumoMapSourceError(f"unsupported demand vehicle types: {sorted(unknown_types)}")
    if not any(
        round(flow.volume * flow.scenario_multipliers.get(scenario_id, 1.0) * share) > 0
        for flow in overlay.demand_flows.values()
        for share in flow.vehicle_mix.values()
    ):
        raise SumoMapSourceError(f"{scenario_id}: no trips requested by supplied demand_flows")
    work_dir.mkdir(parents=True, exist_ok=True)
    trips_path = work_dir / f"{scenario_id}.trips.xml"
    routes_path = work_dir / f"{scenario_id}.rou.xml"
    ledger_path = work_dir / f"{scenario_id}.intended_demand_ledger.json"
    qa_path = work_dir / f"{scenario_id}.demand_qa.json"
    trips = _write_trips(
        overlay=overlay,
        net_index=net_index,
        scenario_id=scenario_id,
        path=trips_path,
    )
    intended_ids = {trip["trip_id"] for trip in trips}
    if len(intended_ids) != len(trips):
        raise SumoMapSourceError("generated intended-demand ledger contains duplicate trip IDs")
    for trip in trips:
        trip["route_status"] = "routing_unverified"
        trip["failure_reason"] = None
        trip["failure_reason_source"] = None

    ledger: dict[str, Any] = {
        "schema_version": "intended_demand_ledger.v1",
        "scenario_id": scenario_id,
        "seed": seed,
        "overlay_id": overlay.overlay_id,
        "overlay_schema_version": overlay.schema_version,
        "count_unit": "requested_vehicle_trip",
        "demand_basis": "assumption_based_synthetic",
        "calibrated_field_demand": False,
        "demand_source": "explicit_overlay.demand_flows",
        "route_reconciliation": "exact_vehicle_id_match",
        "reconciliation_status": "pending",
        "trips": trips,
    }
    _persist_ledger_and_qa(ledger, ledger_path=ledger_path, qa_path=qa_path)
    try:
        _run_duarouter(
            duarouter_binary=duarouter_binary,
            net_path=net_path,
            trips_path=trips_path,
            routes_path=routes_path,
            seed=seed,
        )
        route_vehicle_ids = _route_vehicle_ids(routes_path)
        unexpected_ids = route_vehicle_ids - intended_ids
        if unexpected_ids:
            raise SumoMapSourceError(
                "duarouter route output contains vehicle IDs absent from intended-demand ledger: "
                f"{sorted(unexpected_ids)[:5]}"
            )
    except Exception:
        # Preserve intended demand without claiming route failures when routing could not
        # be reconciled. The pending ledger was already persisted before router startup.
        ledger["reconciliation_status"] = "unavailable"
        _persist_ledger_and_qa(ledger, ledger_path=ledger_path, qa_path=qa_path)
        raise

    for trip in trips:
        routed = trip["trip_id"] in route_vehicle_ids
        trip["route_status"] = "routed" if routed else "not_routed"
        trip["failure_reason"] = None if routed else "unknown"
        trip["failure_reason_source"] = None
    ledger["reconciliation_status"] = "reconciled"
    summary = _persist_ledger_and_qa(ledger, ledger_path=ledger_path, qa_path=qa_path)
    # DemandGenerationResult retains its historical non-null aggregate count fields;
    # a successful return only occurs with a fully reconciled ledger.
    assert summary["attempted_trips"] is not None
    assert summary["routed_trips"] is not None
    assert summary["not_routed_trips"] is not None
    return DemandGenerationResult(
        trips=trips_path,
        routes=routes_path,
        qa_json=qa_path,
        attempted_trips=summary["attempted_trips"],
        routed_trips=summary["routed_trips"],
        failed_trips=summary["not_routed_trips"],
        intended_demand_ledger=ledger_path,
    )


def _write_trips(
    *,
    overlay: SemanticOverlay,
    net_index: SumoNetIndex,
    scenario_id: str,
    path: Path,
) -> list[dict[str, Any]]:
    root = ET.Element("routes")
    vehicle_types = _vehicle_types()
    for vehicle_type_id, attrs in vehicle_types.items():
        ET.SubElement(root, "vType", {"id": vehicle_type_id, **attrs})

    trips: list[dict[str, Any]] = []
    for flow in sorted(overlay.demand_flows.values(), key=lambda item: item.flow_id):
        multiplier = flow.scenario_multipliers.get(scenario_id, 1.0)
        if multiplier <= 0:
            continue
        origin_zone = overlay.zones[flow.origin_zone]
        destination_zone = overlay.zones[flow.destination_zone]
        from_edges = [edge for edge in origin_zone.anchor_edges if net_index.contains_edge(edge)]
        to_edges = [edge for edge in destination_zone.anchor_edges if net_index.contains_edge(edge)]
        if not from_edges or not to_edges:
            raise SumoMapSourceError(f"{flow.flow_id}: missing routable anchor edges")
        for vehicle_type_id, share in sorted(flow.vehicle_mix.items()):
            count = int(round(flow.volume * multiplier * share))
            if count <= 0:
                continue
            depart_step = max(1.0, (flow.end - flow.begin) / count)
            for index in range(count):
                from_edge = from_edges[index % len(from_edges)]
                to_edge = to_edges[(index // max(1, len(from_edges))) % len(to_edges)]
                if from_edge == to_edge and len(to_edges) > 1:
                    to_edge = to_edges[(index + 1) % len(to_edges)]
                trip_id = f"{flow.flow_id}_{vehicle_type_id}.{index}"
                departure = f"{flow.begin + depart_step * index:.3f}"
                ET.SubElement(
                    root,
                    "trip",
                    {
                        "id": trip_id,
                        "type": vehicle_type_id,
                        "depart": departure,
                        "from": from_edge,
                        "to": to_edge,
                        "departLane": "best",
                        "departSpeed": "max",
                    },
                )
                trips.append(
                    {
                        "trip_id": trip_id,
                        "source_flow_id": flow.flow_id,
                        "trip_purpose": flow.trip_purpose,
                        "vehicle_type_id": vehicle_type_id,
                        "vehicle_class": vehicle_types[vehicle_type_id]["vClass"],
                        "intended_departure_seconds": float(departure),
                        "origin_zone_id": flow.origin_zone,
                        "destination_zone_id": flow.destination_zone,
                        "origin_edge_id": from_edge,
                        "destination_edge_id": to_edge,
                    }
                )
    _write_xml(root, path)
    return trips


def _run_duarouter(
    *,
    duarouter_binary: str,
    net_path: Path,
    trips_path: Path,
    routes_path: Path,
    seed: int,
) -> None:
    duarouter = resolve_sumo_binary(duarouter_binary)
    if duarouter is None:
        raise SumoRuntimeError(
            f"SUMO binary '{duarouter_binary}' was not found. Install SUMO or set SUMO_HOME."
        )
    command = [
        duarouter,
        "--net-file",
        str(net_path),
        "--route-files",
        str(trips_path),
        "--output-file",
        str(routes_path),
        "--ignore-errors",
        "true",
        "--seed",
        str(seed),
        "--no-warnings",
        "true",
    ]
    completed = subprocess.run(
        command,
        cwd=trips_path.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SumoRuntimeError(
            "duarouter failed:\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )


def _route_vehicle_ids(path: Path) -> set[str]:
    if not path.is_file():
        raise SumoMapSourceError(f"duarouter route output not found: {path}")
    vehicle_ids: set[str] = set()
    root_seen = False
    try:
        for event, element in ET.iterparse(path, events=("start", "end")):
            tag = element.tag.rsplit("}", 1)[-1]
            if event == "start" and not root_seen:
                root_seen = True
                if tag != "routes":
                    raise SumoMapSourceError(
                        f"invalid duarouter route output root {tag!r}; expected 'routes'"
                    )
            elif event == "end" and tag == "vehicle":
                vehicle_id = element.attrib.get("id", "")
                if not vehicle_id.strip() or vehicle_id != vehicle_id.strip():
                    raise SumoMapSourceError(
                        "malformed duarouter route output: vehicle has an empty "
                        "or whitespace-padded id"
                    )
                if not _vehicle_has_usable_inline_route(element):
                    raise SumoMapSourceError(
                        "malformed duarouter route output: vehicle has no usable inline route"
                    )
                if vehicle_id in vehicle_ids:
                    raise SumoMapSourceError(
                        f"malformed duarouter route output: duplicate vehicle id {vehicle_id!r}"
                    )
                vehicle_ids.add(vehicle_id)
                element.clear()
    except ET.ParseError as exc:
        raise SumoMapSourceError(f"malformed duarouter route output: {exc}") from exc
    return vehicle_ids


def _vehicle_has_usable_inline_route(vehicle: ET.Element) -> bool:
    # duarouter's observed output uses a nested <route edges="..."/> element.
    # An ID without those edges is not evidence that the requested trip was routed.
    return any(
        element.tag.rsplit("}", 1)[-1] == "route"
        and bool(element.attrib.get("edges", "").split())
        for element in vehicle.iter()
    )


def _summarize_ledger(ledger: dict[str, Any]) -> dict[str, int | None]:
    trips = ledger["trips"]
    if ledger.get("reconciliation_status") != "reconciled":
        return {
            "attempted_trips": len(trips),
            "routed_trips": None,
            "not_routed_trips": None,
        }
    routed_trips = sum(trip["route_status"] == "routed" for trip in trips)
    not_routed_trips = sum(trip["route_status"] == "not_routed" for trip in trips)
    return {
        "attempted_trips": len(trips),
        "routed_trips": routed_trips,
        "not_routed_trips": not_routed_trips,
    }


def _persist_ledger_and_qa(
    ledger: dict[str, Any], *, ledger_path: Path, qa_path: Path
) -> dict[str, int | None]:
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = _summarize_ledger(ledger)
    qa_path.write_text(
        json.dumps(
            {
                "schema_version": "demand_generation_qa.v1",
                "scenario_id": ledger["scenario_id"],
                "count_unit": ledger["count_unit"],
                "intended_demand_ledger": ledger_path.name,
                "route_reconciliation_status": ledger["reconciliation_status"],
                **summary,
                "failed_trips": summary["not_routed_trips"],
                "failed_trips_definition": (
                    "intended trips absent from valid route output; failure cause is unknown"
                ),
                "demand_type": "synthetic_policy_scenario",
                "demand_basis": ledger["demand_basis"],
                "calibrated_field_demand": ledger["calibrated_field_demand"],
                "evidence_scope": "synthetic_assumption_not_calibrated_field_demand",
                "caveat": (
                    "Assumption-based synthetic demand from explicit overlay demand_flows; "
                    "not calibrated field demand. Unrouted trip causes are unknown."
                ),
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def _vehicle_types() -> dict[str, dict[str, str]]:
    return {
        "MOTORBIKE": {
            "vClass": "motorcycle",
            "length": "2.0",
            "width": "0.7",
            "maxSpeed": "12.5",
            "accel": "3.0",
            "decel": "5.0",
            "minGap": "1.0",
            "color": "0,180,0",
        },
        "PRIVATE_CAR": {
            "vClass": "passenger",
            "length": "4.5",
            "width": "1.8",
            "maxSpeed": "13.9",
            "accel": "2.6",
            "decel": "4.5",
            "minGap": "2.5",
            "color": "255,255,255",
        },
        "BUS": {
            "vClass": "bus",
            "length": "12.0",
            "width": "2.5",
            "maxSpeed": "12.5",
            "accel": "1.2",
            "decel": "4.0",
            "minGap": "3.0",
            "color": "0,0,255",
        },
        "LIGHT_TRUCK": {
            "vClass": "truck",
            "length": "6.5",
            "width": "2.2",
            "maxSpeed": "13.9",
            "accel": "1.5",
            "decel": "3.5",
            "minGap": "3.0",
            "color": "255,140,0",
        },
        "AMBULANCE": {
            "vClass": "emergency",
            "length": "5.5",
            "width": "2.0",
            "maxSpeed": "19.4",
            "accel": "3.5",
            "decel": "5.5",
            "minGap": "2.0",
            "color": "255,0,0",
        },
    }


def _write_xml(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
