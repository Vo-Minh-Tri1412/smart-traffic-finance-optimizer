from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from typing import Any

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.engines.sumo.exporter import SumoExportPaths
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.routing import RouteNotFoundError, RoutePlanner


def parse_sumo_result(
    *,
    paths: SumoExportPaths,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    seed: int,
) -> SimulationResult:
    tripinfos = _tripinfo_rows(paths)
    waiting_times = [_float_attr(row, "waitingTime") for row in tripinfos]
    total_waiting = sum(waiting_times)
    total_vehicles = len(tripinfos)
    average_waiting = total_waiting / total_vehicles if total_vehicles else 0.0
    intersections = {
        intersection_id: IntersectionMetric(intersection_id=intersection_id)
        for intersection_id in spec.intersections
    }
    route_by_prefix = _route_edges_by_vehicle_prefix(spec, scenario_id)

    emergency_delay = 0.0
    bus_passenger_delay = 0.0
    truck_delay = 0.0

    for row in tripinfos:
        vehicle_id = row.get("id", "")
        vehicle_type_id = row.get("vType") or _vehicle_type_from_id(vehicle_id, spec.vehicle_types)
        waiting_time = _float_attr(row, "waitingTime")
        route = _matched_route(vehicle_id, route_by_prefix)
        if route:
            per_road_delay = waiting_time / len(route)
            for road_id in route:
                road = spec.roads.get(road_id)
                if road is None:
                    continue
                metric = intersections[road.to_intersection]
                metric.delay_seconds += per_road_delay
                metric.vehicles += 1
                if vehicle_type_id == "AMBULANCE":
                    metric.emergency_delay_seconds += per_road_delay
                if vehicle_type_id in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
                    passenger_delay = (
                        per_road_delay * spec.vehicle_types[vehicle_type_id].passenger_count
                    )
                    metric.bus_passenger_delay_seconds += passenger_delay
                if vehicle_type_id in {"LIGHT_TRUCK", "HEAVY_TRUCK"}:
                    metric.truck_delay_seconds += per_road_delay

        if vehicle_type_id == "AMBULANCE":
            emergency_delay += waiting_time
        if vehicle_type_id in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
            bus_passenger_delay += (
                waiting_time * spec.vehicle_types[vehicle_type_id].passenger_count
            )
        if vehicle_type_id in {"LIGHT_TRUCK", "HEAVY_TRUCK"}:
            truck_delay += waiting_time

    _apply_edge_queue_metrics(paths=paths, spec=spec, intersections=intersections)
    queue_values = [metric.queue_vehicles for metric in intersections.values()]

    return SimulationResult(
        scenario_id=scenario_id,
        controller_id=controller_id,
        engine_id="sumo",
        seed=seed,
        total_vehicles=total_vehicles,
        throughput=sum(1 for row in tripinfos if _arrived(row)),
        total_waiting_time_seconds=round(total_waiting, 3),
        average_waiting_time_seconds=round(average_waiting, 3),
        max_queue_vehicles=round(max(queue_values, default=0.0), 3),
        average_queue_vehicles=round(
            sum(queue_values) / len(queue_values) if queue_values else 0.0,
            3,
        ),
        stopped_vehicles=sum(1 for value in waiting_times if value > 0),
        emergency_delay_seconds=round(emergency_delay, 3),
        bus_passenger_delay_seconds=round(bus_passenger_delay, 3),
        truck_delay_seconds=round(truck_delay, 3),
        reroute_count=0,
        failed_route_count=0,
        controller_interventions=_controller_intervention_count(paths),
        intersections=intersections,
        vehicle_trace_frames=_fcd_trace_frames(
            paths=paths,
            spec=spec,
            scenario_id=scenario_id,
            controller_id=controller_id,
            seed=seed,
        ),
    )


def _tripinfo_rows(paths: SumoExportPaths) -> list[dict[str, str]]:
    if not paths.tripinfo.is_file():
        return []
    tree = ET.parse(paths.tripinfo)
    return [dict(element.attrib) for element in tree.getroot().iter("tripinfo")]


def _controller_intervention_count(paths: SumoExportPaths) -> int:
    if not paths.controller_log.is_file():
        return 0
    with paths.controller_log.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _float_attr(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, "") or default)
    except ValueError:
        return default


def _arrived(row: dict[str, str]) -> bool:
    arrival = row.get("arrival")
    if arrival is None:
        return True
    return _float_attr(row, "arrival", default=-1.0) >= 0.0


def _route_edges_by_vehicle_prefix(
    spec: DistrictSpec,
    scenario_id: str,
) -> list[tuple[str, str, tuple[str, ...]]]:
    if scenario_id not in spec.scenarios:
        return []
    scenario = spec.scenarios[scenario_id]
    planner = RoutePlanner(spec)
    routes: list[tuple[str, str, tuple[str, ...]]] = []
    for flow in spec.flows.values():
        for vehicle_type_id in flow.vehicle_mix:
            vehicle_type = spec.vehicle_types[vehicle_type_id]
            try:
                route = planner.find_route(flow=flow, vehicle_type=vehicle_type, scenario=scenario)
            except RouteNotFoundError:
                continue
            routes.append((f"{flow.flow_id}_{vehicle_type_id}.", vehicle_type_id, route.road_ids))
    return sorted(routes, key=lambda item: len(item[0]), reverse=True)


def _matched_route(
    vehicle_id: str,
    route_by_prefix: Iterable[tuple[str, str, tuple[str, ...]]],
) -> tuple[str, ...]:
    for prefix, _vehicle_type_id, route in route_by_prefix:
        if vehicle_id.startswith(prefix):
            return route
    return ()


def _vehicle_type_from_id(vehicle_id: str, vehicle_types: Mapping[str, object]) -> str:
    for vehicle_type_id in sorted(vehicle_types, key=len, reverse=True):
        if f"_{vehicle_type_id}." in vehicle_id:
            return vehicle_type_id
    return ""


def _apply_edge_queue_metrics(
    *,
    paths: SumoExportPaths,
    spec: DistrictSpec,
    intersections: dict[str, IntersectionMetric],
) -> None:
    if not paths.edge_data.is_file():
        return
    tree = ET.parse(paths.edge_data)
    for interval in tree.getroot().iter("interval"):
        begin = _float_attr(dict(interval.attrib), "begin")
        end = _float_attr(dict(interval.attrib), "end")
        period = max(1.0, end - begin)
        for edge in interval.iter("edge"):
            row = dict(edge.attrib)
            road = spec.roads.get(row.get("id", ""))
            if road is None:
                continue
            metric = intersections[road.to_intersection]
            waiting_time = _float_attr(row, "waitingTime")
            halting_proxy = _float_attr(row, "halting")
            queue_proxy = max(halting_proxy, waiting_time / period)
            metric.queue_vehicles = max(metric.queue_vehicles, queue_proxy)


def _fcd_trace_frames(
    *,
    paths: SumoExportPaths,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    seed: int,
) -> list[dict[str, Any]]:
    if not paths.fcd.is_file():
        return []
    tree = ET.parse(paths.fcd)
    frames: list[dict[str, Any]] = []
    for frame_index, timestep in enumerate(tree.getroot().iter("timestep")):
        time_seconds = _float_attr(dict(timestep.attrib), "time")
        vehicles = []
        for vehicle in timestep.iter("vehicle"):
            row = dict(vehicle.attrib)
            lane_id = row.get("lane", "")
            vehicles.append(
                {
                    "vehicle_id": row.get("id", ""),
                    "vehicle_type": row.get("type", ""),
                    "x": _float_attr(row, "x"),
                    "y": _float_attr(row, "y"),
                    "speed": _float_attr(row, "speed"),
                    "angle": _float_attr(row, "angle"),
                    "lane_id": lane_id,
                    "road_id": _road_id_from_lane(lane_id),
                }
            )
        frames.append(
            {
                "timestep": frame_index,
                "time_seconds": time_seconds,
                "district_id": spec.metadata.district_id,
                "scenario_id": scenario_id,
                "controller_id": controller_id,
                "engine_id": "sumo",
                "seed": seed,
                "vehicles": vehicles,
            }
        )
    return frames


def _road_id_from_lane(lane_id: str) -> str:
    if not lane_id or lane_id.startswith(":") or "_" not in lane_id:
        return ""
    return lane_id.rsplit("_", 1)[0]
