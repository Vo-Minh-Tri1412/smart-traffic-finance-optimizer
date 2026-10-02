"""Content-addressed map input snapshots; these are not experiment or safety certificates."""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .overlay import load_semantic_overlay
from .source import SumoMapSourceError, load_sumo_net_index, load_sumo_project, sha256_file

SNAPSHOT_SCHEMA = "sumo_project_snapshot.v1"


def _digest(payload: dict[str, Any]) -> str:
    data = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _xml_record(element: ET.Element) -> dict[str, Any]:
    return {
        "tag": element.tag,
        "attributes": dict(element.attrib),
        "children": [_xml_record(child) for child in element],
    }


def load_tls_inventory(net_path: Path) -> dict[str, Any]:
    """Index actual tlLogic IDs, preserving source attributes and controlled lane references."""
    try:
        return _load_tls_inventory(net_path)
    except (ET.ParseError, KeyError) as exc:
        raise SumoMapSourceError(f"invalid SUMO TLS source {net_path}: {exc}") from exc


def _load_tls_inventory(net_path: Path) -> dict[str, Any]:
    programs: dict[str, dict[str, dict[str, Any]]] = {}
    movements: dict[str, list[dict[str, str]]] = {}
    lanes: dict[tuple[str, str], list[str]] = {}
    lane_ids: set[str] = set()
    junction_ids: set[str] = set()
    for _, element in ET.iterparse(net_path, events=("end",)):
        if element.tag == "edge":
            for lane in element.findall("lane"):
                key = (element.attrib["id"], lane.attrib["index"])
                if lane.attrib["id"] in lane_ids:
                    raise SumoMapSourceError(f"duplicate lane id {lane.attrib['id']}")
                lanes.setdefault(key, []).append(lane.attrib["id"])
                lane_ids.add(lane.attrib["id"])
            element.clear()
        elif element.tag == "junction":
            junction_ids.add(element.attrib["id"])
            element.clear()
        elif element.tag == "tlLogic":
            tls_id = element.attrib.get("id", "")
            program_id = element.attrib.get("programID", "")
            if not tls_id or not program_id:
                raise SumoMapSourceError("tlLogic requires id and programID")
            by_id = programs.setdefault(tls_id, {})
            if program_id in by_id:
                raise SumoMapSourceError(f"{tls_id}: duplicate programID {program_id}")
            by_id[program_id] = _xml_record(element)
            element.clear()
        elif element.tag == "connection":
            if "tl" in element.attrib:
                movements.setdefault(element.attrib["tl"], []).append(dict(element.attrib))
            element.clear()

    if programs.keys() != movements.keys():
        raise SumoMapSourceError(
            "TLS program/movement mismatch: "
            f"without_program={sorted(movements.keys() - programs.keys())}, "
            f"without_movements={sorted(programs.keys() - movements.keys())}"
        )
    signals = []
    for tls_id in sorted(programs):
        links = movements[tls_id]
        indices = set()
        for link in links:
            try:
                index = int(link["linkIndex"])
                from_lanes = lanes[(link["from"], link["fromLane"])]
                to_lanes = lanes[(link["to"], link["toLane"])]
            except (KeyError, ValueError) as exc:
                raise SumoMapSourceError(f"{tls_id}: invalid controlled connection {link}") from exc
            if len(from_lanes) != 1 or len(to_lanes) != 1:
                raise SumoMapSourceError(f"{tls_id}: ambiguous controlled lane index: {link}")
            if index < 0 or (link.get("via") and link["via"] not in lane_ids):
                raise SumoMapSourceError(f"{tls_id}: invalid link index or via lane: {link}")
            indices.add(index)
            link["from_lane_id"] = from_lanes[0]
            link["to_lane_id"] = to_lanes[0]
        program_records = []
        for program_id, program in sorted(programs[tls_id].items()):
            phases = [child for child in program["children"] if child["tag"] == "phase"]
            if not phases:
                raise SumoMapSourceError(f"{tls_id}/{program_id}: program has no phases")
            widths = set()
            for phase in phases:
                attrs = phase["attributes"]
                try:
                    duration = float(attrs["duration"])
                    state = attrs["state"]
                except (KeyError, ValueError) as exc:
                    raise SumoMapSourceError(f"{tls_id}/{program_id}: invalid phase") from exc
                if not math.isfinite(duration) or duration <= 0 or max(indices) >= len(state):
                    raise SumoMapSourceError(
                        f"{tls_id}/{program_id}: invalid duration or phase/linkIndex width"
                    )
                widths.add(len(state))
            if len(widths) != 1:
                raise SumoMapSourceError(f"{tls_id}/{program_id}: inconsistent phase state widths")
            program_records.append(
                {
                    "program_id": program_id,
                    "source": program,
                    "unmapped_signal_indices": sorted(set(range(next(iter(widths)))) - indices),
                }
            )
        signals.append(
            {
                "tls_id": tls_id,
                # Joined traffic lights need not have a junction with the same ID.
                "same_id_junction": tls_id if tls_id in junction_ids else None,
                "programs": program_records,
                "movements": sorted(
                    links,
                    key=lambda row: (
                        int(row["linkIndex"]),
                        row["from_lane_id"],
                        row["to_lane_id"],
                        row.get("via", ""),
                    ),
                ),
                "control_review_status": "pending",
            }
        )
    return {
        "tls_count": len(signals),
        "program_count": sum(len(row["programs"]) for row in signals),
        "controlled_connection_count": sum(len(row["movements"]) for row in signals),
        "lane_index_ambiguities": [
            {"edge_id": edge, "index": index, "lane_ids": ids}
            for (edge, index), ids in sorted(lanes.items())
            if len(ids) > 1
        ],
        "signals": signals,
        "caveat": (
            "Structural source inventory only; no runtime safety or pilot eligibility approval."
        ),
    }


def build_project_snapshot(project_path: Path | str) -> dict[str, Any]:
    project_path = Path(project_path).resolve()
    descriptor_before = _file_record(project_path)
    project = load_sumo_project(project_path)
    paths = {
        "descriptor": project_path,
        "net": project.source.net_path,
        "overlay": project.overlay_path,
        "demand_config": project.demand_config_path,
    }
    before = {role: _file_record(path) for role, path in paths.items()}
    if before["descriptor"] != descriptor_before:
        raise SumoMapSourceError("project descriptor changed while loading")
    try:
        index = load_sumo_net_index(project.source.net_path)
    except ET.ParseError as exc:
        raise SumoMapSourceError(f"invalid SUMO net XML: {exc}") from exc
    overlay = load_semantic_overlay(project.overlay_path, index)
    inventory = load_tls_inventory(project.source.net_path)
    if {role: _file_record(path) for role, path in paths.items()} != before:
        raise SumoMapSourceError("project inputs changed while building snapshot")
    payload = {
        "schema_version": SNAPSHOT_SCHEMA,
        "project_id": project.project_id,
        "project_version": project.version,
        "inputs": before,
        "overlay_schema_version": overlay.schema_version,
        "overlay_zone_count": len(overlay.zones),
        "unanchored_zone_count": sum(not zone.anchor_edges for zone in overlay.zones.values()),
        "demand_flow_count": len(overlay.demand_flows),
        "net_counts": {
            "external_edges": index.edge_count,
            "external_lanes": index.lane_count,
            "external_junctions": index.junction_count,
            "traffic_light_junctions": index.traffic_light_count,
        },
        "tls_inventory": inventory,
        "scope": "map_input_snapshot_only",
    }
    return {**payload, "content_sha256": _digest(payload)}


def write_project_snapshot(project_path: Path | str, output: Path | str) -> dict[str, Any]:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"snapshot already exists; refusing overwrite: {output}")
    payload = build_project_snapshot(project_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return payload


def verify_project_snapshot(snapshot_path: Path | str, project_path: Path | str) -> dict[str, Any]:
    stored = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or stored.get("schema_version") != SNAPSHOT_SCHEMA:
        raise SumoMapSourceError("unsupported project snapshot schema")
    body = {key: value for key, value in stored.items() if key != "content_sha256"}
    if stored.get("content_sha256") != _digest(body):
        raise SumoMapSourceError("project snapshot content checksum mismatch")
    # Recompute inventory too: a checksum is identity evidence, not a trusted parser certificate.
    actual = build_project_snapshot(project_path)
    comparable = {key: value for key, value in actual.items() if key != "content_sha256"}
    # Explicit project rebinding permits a relocated checkout only when all source bytes agree.
    for role, record in comparable["inputs"].items():
        expected = body.get("inputs", {}).get(role, {})
        if record["sha256"] != expected.get("sha256") or record["bytes"] != expected.get("bytes"):
            raise SumoMapSourceError(f"project snapshot input mismatch: {role}")
        record["path"] = expected.get("path")
    if comparable != body:
        raise SumoMapSourceError("project snapshot inventory or metadata mismatch")
    return stored
