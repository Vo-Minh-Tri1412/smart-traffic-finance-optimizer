from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.profiles import (
    DEFAULT_SUMO_PROFILE,
    SumoSimulationProfile,
)
from ai_quantum_hvtc.simulation.routing import RouteNotFoundError, RoutePlanner
from ai_quantum_hvtc.simulation.vehicle_geometry import write_vehicle_geometry_catalog


@dataclass(frozen=True)
class SumoExportPaths:
    work_dir: Path
    nodes: Path
    edges: Path
    additional: Path
    routes: Path
    net: Path
    config: Path
    tripinfo: Path
    summary: Path
    edge_data: Path
    fcd: Path
    controller_log: Path
    vehicle_geometry_catalog: Path
    simulation_profile: SumoSimulationProfile


def export_sumo_project(
    *,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    seed: int,
    work_dir: Path,
    simulation_profile: SumoSimulationProfile = DEFAULT_SUMO_PROFILE,
) -> SumoExportPaths:
    if scenario_id not in spec.scenarios:
        raise SumoRuntimeError(f"unknown scenario_id for SUMO export: {scenario_id}")
    if controller_id not in spec.controllers:
        raise SumoRuntimeError(f"unknown controller_id for SUMO export: {controller_id}")

    work_dir.mkdir(parents=True, exist_ok=True)
    paths = SumoExportPaths(
        work_dir=work_dir,
        nodes=work_dir / "district.nod.xml",
        edges=work_dir / "district.edg.xml",
        additional=work_dir / "additional.xml",
        routes=work_dir / "district.rou.xml",
        net=work_dir / "district.net.xml",
        config=work_dir / "district.sumocfg",
        tripinfo=work_dir / "tripinfo.xml",
        summary=work_dir / "summary.xml",
        edge_data=work_dir / "edge_data.xml",
        fcd=work_dir / "fcd.xml",
        controller_log=work_dir / "controller_interventions.jsonl",
        vehicle_geometry_catalog=work_dir / "vehicle_geometry_catalog.v1.json",
        simulation_profile=simulation_profile,
    )
    _write_nodes(spec, paths.nodes)
    _write_edges(spec, paths.edges)
    _write_routes(spec, scenario_id, paths.routes)
    _write_additional(spec, paths)
    write_vehicle_geometry_catalog(spec, paths.vehicle_geometry_catalog)
    _write_config(spec, controller_id, seed, paths)
    return paths


def _write_nodes(spec: DistrictSpec, path: Path) -> None:
    root = ET.Element("nodes")
    for intersection in spec.intersections.values():
        ET.SubElement(
            root,
            "node",
            {
                "id": intersection.intersection_id,
                "x": str(intersection.x * 1000.0),
                "y": str(intersection.y * 1000.0),
                "type": "traffic_light" if intersection.signalized else "priority",
            },
        )
    _write_xml(root, path)


def _write_edges(spec: DistrictSpec, path: Path) -> None:
    root = ET.Element("edges")
    for road in spec.roads.values():
        attributes = {
            "id": road.road_id,
            "from": road.from_intersection,
            "to": road.to_intersection,
            "numLanes": str(road.lanes),
            "speed": f"{road.speed_kph / 3.6:.3f}",
            "length": f"{road.length_km * 1000.0:.3f}",
        }
        if road.shape_points:
            attributes["shape"] = " ".join(
                f"{x * 1000.0:.3f},{y * 1000.0:.3f}" for x, y in road.shape_points
            )
        ET.SubElement(root, "edge", attributes)
    _write_xml(root, path)


def _write_routes(spec: DistrictSpec, scenario_id: str, path: Path) -> None:
    root = ET.Element("routes")
    scenario = spec.scenarios[scenario_id]
    planner = RoutePlanner(spec)

    for vehicle_type in spec.vehicle_types.values():
        ET.SubElement(
            root,
            "vType",
            {
                "id": vehicle_type.vehicle_type_id,
                "vClass": vehicle_type.v_class,
                "personCapacity": str(max(1, int(round(vehicle_type.passenger_count)))),
                "color": _vehicle_color(vehicle_type.vehicle_type_id),
                "length": f"{vehicle_type.length_m:.3f}",
                "width": f"{vehicle_type.width_m:.3f}",
                "height": f"{vehicle_type.height_m:.3f}",
                "maxSpeed": f"{vehicle_type.max_speed_kph / 3.6:.3f}",
                "accel": f"{vehicle_type.accel_mps2:.3f}",
                "decel": f"{vehicle_type.decel_mps2:.3f}",
                "emergencyDecel": f"{vehicle_type.emergency_decel_mps2:.3f}",
                "apparentDecel": f"{vehicle_type.apparent_decel_mps2:.3f}",
                "minGap": f"{vehicle_type.min_gap_m:.3f}",
                "tau": f"{vehicle_type.tau_seconds:.3f}",
                "actionStepLength": f"{vehicle_type.action_step_length_seconds:.3f}",
                "maxSpeedLat": f"{vehicle_type.max_speed_lat_mps:.3f}",
                "minGapLat": f"{vehicle_type.min_gap_lat_m:.3f}",
                "latAlignment": vehicle_type.lat_alignment,
                "lcSublane": f"{vehicle_type.lc_sublane:.3f}",
                "lcPushy": f"{vehicle_type.lc_pushy:.3f}",
            },
        )

    for flow in sorted(spec.flows.values(), key=lambda item: (item.departure_start, item.flow_id)):
        route_by_type: dict[str, tuple[str, ...]] = {}
        for vehicle_type_id in flow.vehicle_mix:
            vehicle_type = spec.vehicle_types[vehicle_type_id]
            try:
                route = planner.find_route(flow=flow, vehicle_type=vehicle_type, scenario=scenario)
            except RouteNotFoundError as exc:
                raise SumoRuntimeError(
                    f"{flow.flow_id}: cannot export route to SUMO: {exc}"
                ) from exc
            route_by_type[vehicle_type_id] = route.road_ids

        for vehicle_type_id, share in sorted(flow.vehicle_mix.items()):
            count = int(
                round(flow.base_volume * scenario.flow_multipliers.get(flow.flow_id, 1.0) * share)
            )
            if count <= 0:
                continue
            route_id = f"{flow.flow_id}_{vehicle_type_id}_route"
            ET.SubElement(
                root,
                "route",
                {
                    "id": route_id,
                    "edges": " ".join(route_by_type[vehicle_type_id]),
                },
            )
            ET.SubElement(
                root,
                "flow",
                {
                    "id": f"{flow.flow_id}_{vehicle_type_id}",
                    "type": vehicle_type_id,
                    "route": route_id,
                    "begin": str(flow.departure_start),
                    "end": str(flow.departure_end),
                    "number": str(count),
                    "departLane": "best",
                    "departSpeed": "max",
                },
            )
    _write_xml(root, path)


def _write_additional(spec: DistrictSpec, paths: SumoExportPaths) -> None:
    root = ET.Element("additional")
    ET.SubElement(
        root,
        "edgeData",
        {
            "id": "edge_metrics",
            "file": paths.edge_data.name,
            "period": str(spec.metadata.time_step_seconds),
            "excludeEmpty": "true",
        },
    )
    _write_xml(root, paths.additional)


def _write_config(
    spec: DistrictSpec,
    controller_id: str,
    seed: int,
    paths: SumoExportPaths,
) -> None:
    root = ET.Element("configuration")
    input_node = ET.SubElement(root, "input")
    ET.SubElement(input_node, "net-file", {"value": paths.net.name})
    ET.SubElement(input_node, "route-files", {"value": paths.routes.name})
    ET.SubElement(input_node, "additional-files", {"value": paths.additional.name})

    output_node = ET.SubElement(root, "output")
    ET.SubElement(output_node, "tripinfo-output", {"value": paths.tripinfo.name})
    ET.SubElement(output_node, "tripinfo-output.write-unfinished", {"value": "true"})
    ET.SubElement(output_node, "summary-output", {"value": paths.summary.name})
    ET.SubElement(output_node, "fcd-output", {"value": paths.fcd.name})
    ET.SubElement(output_node, "fcd-output.skip-empty", {"value": "true"})
    ET.SubElement(
        output_node,
        "fcd-output.attributes",
        {"value": "location,posLat,speedLat,acceleration"},
    )

    time_node = ET.SubElement(root, "time")
    ET.SubElement(time_node, "begin", {"value": "0"})
    ET.SubElement(time_node, "end", {"value": str(spec.metadata.horizon_seconds)})
    ET.SubElement(
        time_node,
        "step-length",
        {"value": f"{paths.simulation_profile.step_length_seconds:g}"},
    )

    processing_node = ET.SubElement(root, "processing")
    ET.SubElement(processing_node, "ignore-route-errors", {"value": "true"})
    ET.SubElement(processing_node, "time-to-teleport", {"value": "300"})

    random_node = ET.SubElement(root, "random_number")
    ET.SubElement(random_node, "seed", {"value": str(seed)})
    _write_xml(root, paths.config)


def _write_xml(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _vehicle_color(vehicle_type_id: str) -> str:
    colors = {
        "AMBULANCE": "255,0,0",
        "BUS": "0,0,255",
        "SCHOOL_BUS": "255,215,0",
        "WORKER_SHUTTLE": "0,200,255",
        "LIGHT_TRUCK": "255,140,0",
        "HEAVY_TRUCK": "165,42,42",
        "MOTORBIKE": "0,180,0",
    }
    return colors.get(vehicle_type_id, "255,255,255")
