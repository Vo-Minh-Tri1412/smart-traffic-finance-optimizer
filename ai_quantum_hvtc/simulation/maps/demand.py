from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from ai_quantum_hvtc.simulation.engines.sumo.config import resolve_sumo_binary
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.maps.overlay import SemanticOverlay
from ai_quantum_hvtc.simulation.maps.source import SumoNetIndex


@dataclass(frozen=True)
class DemandGenerationResult:
    trips: Path
    routes: Path
    qa_json: Path
    attempted_trips: int
    routed_trips: int
    failed_trips: int


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
    work_dir.mkdir(parents=True, exist_ok=True)
    trips_path = work_dir / f"{scenario_id}.trips.xml"
    routes_path = work_dir / f"{scenario_id}.rou.xml"
    qa_path = work_dir / f"{scenario_id}.demand_qa.json"
    attempted_trips = _write_trips(
        overlay=overlay,
        net_index=net_index,
        scenario_id=scenario_id,
        path=trips_path,
    )
    _run_duarouter(
        duarouter_binary=duarouter_binary,
        net_path=net_path,
        trips_path=trips_path,
        routes_path=routes_path,
        seed=seed,
    )
    routed_trips = _count_route_vehicles(routes_path)
    failed_trips = max(0, attempted_trips - routed_trips)
    qa_path.write_text(
        (
            "{\n"
            f'  "scenario_id": "{scenario_id}",\n'
            f'  "attempted_trips": {attempted_trips},\n'
            f'  "routed_trips": {routed_trips},\n'
            f'  "failed_trips": {failed_trips},\n'
            '  "demand_type": "synthetic_policy_scenario",\n'
            '  "caveat": "Synthetic OD demand from semantic overlay; not calibrated field data."\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    return DemandGenerationResult(
        trips=trips_path,
        routes=routes_path,
        qa_json=qa_path,
        attempted_trips=attempted_trips,
        routed_trips=routed_trips,
        failed_trips=failed_trips,
    )


def _write_trips(
    *,
    overlay: SemanticOverlay,
    net_index: SumoNetIndex,
    scenario_id: str,
    path: Path,
) -> int:
    root = ET.Element("routes")
    for vehicle_type_id, attrs in _vehicle_types().items():
        ET.SubElement(root, "vType", {"id": vehicle_type_id, **attrs})

    trip_count = 0
    for flow in sorted(overlay.demand_flows.values(), key=lambda item: item.flow_id):
        multiplier = flow.scenario_multipliers.get(scenario_id, 1.0)
        if multiplier <= 0:
            continue
        origin_zone = overlay.zones[flow.origin_zone]
        destination_zone = overlay.zones[flow.destination_zone]
        from_edges = [edge for edge in origin_zone.anchor_edges if net_index.contains_edge(edge)]
        to_edges = [edge for edge in destination_zone.anchor_edges if net_index.contains_edge(edge)]
        if not from_edges or not to_edges:
            continue
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
                ET.SubElement(
                    root,
                    "trip",
                    {
                        "id": f"{flow.flow_id}_{vehicle_type_id}.{index}",
                        "type": vehicle_type_id,
                        "depart": f"{flow.begin + depart_step * index:.3f}",
                        "from": from_edge,
                        "to": to_edge,
                        "departLane": "best",
                        "departSpeed": "max",
                    },
                )
                trip_count += 1
    _write_xml(root, path)
    return trip_count


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


def _count_route_vehicles(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for _event, element in ET.iterparse(path, events=("end",)):
        if element.tag == "vehicle":
            count += 1
        element.clear()
    return count


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
