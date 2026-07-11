from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from typing import Any

from ai_quantum_hvtc.simulation.domain import DistrictSpec, VehicleType
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.exporter import SumoExportPaths
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.routing import RouteNotFoundError, RoutePlanner
from ai_quantum_hvtc.simulation.traces import (
    SIMULATION_TRACE_FRAME_SCHEMA_VERSION,
    VEHICLE_TRACE_SCHEMA_VERSION,
)
from ai_quantum_hvtc.simulation.vehicle_geometry import FRONT_BUMPER_REFERENCE_POINT


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


def parse_existing_sumo_net_result(
    *,
    paths: Any,
    district_id: str,
    scenario_id: str,
    controller_id: str,
    seed: int,
) -> SimulationResult:
    tripinfos = _tripinfo_rows(paths)
    waiting_times = [_float_attr(row, "waitingTime") for row in tripinfos]
    total_waiting = sum(waiting_times)
    total_vehicles = len(tripinfos)
    average_waiting = total_waiting / total_vehicles if total_vehicles else 0.0
    intersections: dict[str, IntersectionMetric] = {}

    emergency_delay = 0.0
    bus_passenger_delay = 0.0
    truck_delay = 0.0
    for row in tripinfos:
        vehicle_type_id = row.get("vType", "")
        waiting_time = _float_attr(row, "waitingTime")
        if vehicle_type_id == "AMBULANCE":
            emergency_delay += waiting_time
        if vehicle_type_id in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
            bus_passenger_delay += waiting_time * 20.0
        if vehicle_type_id in {"LIGHT_TRUCK", "HEAVY_TRUCK"}:
            truck_delay += waiting_time

    _apply_existing_edge_queue_metrics(paths=paths, intersections=intersections)
    queue_values = [metric.queue_vehicles for metric in intersections.values()]

    return SimulationResult(
        scenario_id=scenario_id,
        controller_id=controller_id,
        engine_id="sumo_net",
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
        vehicle_trace_frames=_existing_fcd_trace_frames(
            paths=paths,
            district_id=district_id,
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


def _apply_existing_edge_queue_metrics(
    *,
    paths: Any,
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
            edge_id = row.get("id", "")
            if not edge_id or edge_id.startswith(":"):
                continue
            metric = intersections.setdefault(
                edge_id,
                IntersectionMetric(intersection_id=edge_id),
            )
            waiting_time = _float_attr(row, "waitingTime")
            halting_proxy = _float_attr(row, "halting")
            queue_proxy = max(halting_proxy, waiting_time / period)
            metric.queue_vehicles = max(metric.queue_vehicles, queue_proxy)
            metric.delay_seconds += waiting_time
            if "sampledSeconds" in row:
                metric.vehicles += int(round(_float_attr(row, "sampledSeconds") / period))


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
    lane_elevation_shapes = _lane_elevation_shapes(paths.net)
    frames: list[dict[str, Any]] = []
    for frame_index, timestep in enumerate(tree.getroot().iter("timestep")):
        time_seconds = _float_attr(dict(timestep.attrib), "time")
        vehicles = []
        for vehicle in timestep.iter("vehicle"):
            row = dict(vehicle.attrib)
            lane_id = row.get("lane", "")
            vehicle_type_id = row.get("type", "")
            vehicle_type = spec.vehicle_types.get(vehicle_type_id)
            if vehicle_type is None:
                raise SumoRuntimeError(
                    "SUMO FCD vehicle cannot be emitted as vehicle_trace.v2 without a canonical "
                    f"vehicle type: id={row.get('id', '')!r}, type={vehicle_type_id!r}"
                )
            vehicles.append(
                _trace_vehicle_row(
                    row,
                    lane_id=lane_id,
                    vehicle_type=vehicle_type,
                    lane_elevation_shapes=lane_elevation_shapes,
                )
            )
        frames.append(
            {
                "schema_version": VEHICLE_TRACE_SCHEMA_VERSION,
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


def _existing_fcd_trace_frames(
    *,
    paths: Any,
    district_id: str,
    scenario_id: str,
    controller_id: str,
    seed: int,
) -> list[dict[str, Any]]:
    if not paths.fcd.is_file():
        return []
    tree = ET.parse(paths.fcd)
    route_vehicle_types = _vehicle_types_from_route_file(paths.routes)
    lane_elevation_shapes = _lane_elevation_shapes(paths.net)
    frames: list[dict[str, Any]] = []
    for frame_index, timestep in enumerate(tree.getroot().iter("timestep")):
        time_seconds = _float_attr(dict(timestep.attrib), "time")
        vehicles = []
        for vehicle in timestep.iter("vehicle"):
            row = dict(vehicle.attrib)
            lane_id = row.get("lane", "")
            vehicle_type_id = row.get("type", "")
            vehicles.append(
                _trace_vehicle_row(
                    row,
                    lane_id=lane_id,
                    vehicle_type=route_vehicle_types.get(vehicle_type_id),
                    lane_elevation_shapes=lane_elevation_shapes,
                )
            )
        has_canonical_geometry = all(_has_geometry_fields(vehicle) for vehicle in vehicles)
        frames.append(
            {
                "schema_version": (
                    VEHICLE_TRACE_SCHEMA_VERSION
                    if has_canonical_geometry
                    else SIMULATION_TRACE_FRAME_SCHEMA_VERSION
                ),
                "timestep": frame_index,
                "time_seconds": time_seconds,
                "district_id": district_id,
                "scenario_id": scenario_id,
                "controller_id": controller_id,
                "engine_id": "sumo_net",
                "seed": seed,
                "vehicles": vehicles,
            }
        )
    return frames


def _trace_vehicle_row(
    row: dict[str, str],
    *,
    lane_id: str,
    vehicle_type: VehicleType | None,
    lane_elevation_shapes: Mapping[str, tuple[tuple[float, float, float], ...]],
) -> dict[str, Any]:
    x = _float_attr(row, "x")
    y = _float_attr(row, "y")
    elevation_m, elevation_source = _vehicle_elevation(
        row,
        lane_id=lane_id,
        x=x,
        y=y,
        lane_elevation_shapes=lane_elevation_shapes,
    )
    vehicle = {
        "vehicle_id": row.get("id", ""),
        "vehicle_type": row.get("type", ""),
        "x": x,
        "y": y,
        "speed": _float_attr(row, "speed"),
        "angle": _float_attr(row, "angle"),
        "lane_id": lane_id,
        "road_id": _road_id_from_lane(lane_id),
        "pos_lat_m": _float_attr(row, "posLat"),
        "lateral_speed_mps": _float_attr(row, "speedLat"),
        "acceleration_mps2": _float_attr(row, "acceleration"),
        "elevation_m": elevation_m,
        "elevation_source": elevation_source,
    }
    if vehicle_type is None:
        return vehicle
    vehicle.update(
        {
            "length_m": vehicle_type.length_m,
            "width_m": vehicle_type.width_m,
            "height_m": vehicle_type.height_m,
            "ground_clearance_m": vehicle_type.ground_clearance_m,
            "reference_point": FRONT_BUMPER_REFERENCE_POINT,
        }
    )
    return vehicle


def _vehicle_types_from_route_file(path: Any) -> dict[str, VehicleType]:
    if not path.is_file():
        return {}
    tree = ET.parse(path)
    vehicle_types: dict[str, VehicleType] = {}
    for element in tree.getroot().iter("vType"):
        row = dict(element.attrib)
        vehicle_type_id = row.get("id", "")
        if not vehicle_type_id:
            continue
        if not {"length", "width", "height"}.issubset(row):
            continue
        vehicle_types[vehicle_type_id] = VehicleType(
            vehicle_type_id=vehicle_type_id,
            passenger_count=1.0,
            pcu=1.0,
            value_class="trace_only",
            length_m=_float_attr(row, "length", 4.5),
            width_m=_float_attr(row, "width", 1.8),
            height_m=_float_attr(row, "height", 1.5),
            ground_clearance_m=0.0,
            v_class=row.get("vClass", "passenger"),
            max_speed_kph=_float_attr(row, "maxSpeed") * 3.6,
            accel_mps2=_float_attr(row, "accel", 2.6),
            decel_mps2=_float_attr(row, "decel", 4.5),
            min_gap_m=_float_attr(row, "minGap", 2.5),
            tau_seconds=_float_attr(row, "tau", 1.2),
            emergency_decel_mps2=_float_attr(row, "emergencyDecel", 7.0),
            apparent_decel_mps2=_float_attr(row, "apparentDecel", 4.5),
            action_step_length_seconds=_float_attr(row, "actionStepLength", 1.0),
            max_speed_lat_mps=_float_attr(row, "maxSpeedLat"),
            min_gap_lat_m=_float_attr(row, "minGapLat"),
            lat_alignment=row.get("latAlignment", "center"),
            lc_sublane=_float_attr(row, "lcSublane"),
            lc_pushy=_float_attr(row, "lcPushy"),
        )
    return vehicle_types


def _has_geometry_fields(vehicle: dict[str, Any]) -> bool:
    return all(
        field in vehicle
        for field in (
            "length_m",
            "width_m",
            "height_m",
            "ground_clearance_m",
            "reference_point",
        )
    )


def _lane_elevation_shapes(path: Any) -> dict[str, tuple[tuple[float, float, float], ...]]:
    if not path.is_file():
        return {}
    tree = ET.parse(path)
    shapes: dict[str, tuple[tuple[float, float, float], ...]] = {}
    for lane in tree.getroot().iter("lane"):
        row = dict(lane.attrib)
        lane_id = row.get("id", "")
        points = _parse_shape_3d(row.get("shape", ""))
        if lane_id and points is not None:
            shapes[lane_id] = points
    return shapes


def _parse_shape_3d(value: str) -> tuple[tuple[float, float, float], ...] | None:
    points: list[tuple[float, float, float]] = []
    for token in value.split():
        values = token.split(",")
        if len(values) != 3:
            return None
        try:
            points.append((float(values[0]), float(values[1]), float(values[2])))
        except ValueError:
            return None
    return tuple(points) if len(points) >= 2 else None


def _vehicle_elevation(
    row: Mapping[str, str],
    *,
    lane_id: str,
    x: float,
    y: float,
    lane_elevation_shapes: Mapping[str, tuple[tuple[float, float, float], ...]],
) -> tuple[float, str]:
    if "z" in row:
        return _float_attr(dict(row), "z"), "fcd_z"
    shape = lane_elevation_shapes.get(lane_id)
    if shape is None:
        return 0.0, "flat_assumption"
    closest_z: float | None = None
    closest_distance = math.inf
    for start, end in zip(shape[:-1], shape[1:], strict=True):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        squared_length = dx * dx + dy * dy
        if squared_length <= 0:
            continue
        ratio = max(0.0, min(1.0, ((x - start[0]) * dx + (y - start[1]) * dy) / squared_length))
        closest_x = start[0] + ratio * dx
        closest_y = start[1] + ratio * dy
        distance = (x - closest_x) ** 2 + (y - closest_y) ** 2
        if distance < closest_distance:
            closest_distance = distance
            closest_z = start[2] + ratio * (end[2] - start[2])
    if closest_z is None:
        return 0.0, "flat_assumption"
    return closest_z, "lane_shape_3d"


def _road_id_from_lane(lane_id: str) -> str:
    if not lane_id or lane_id.startswith(":") or "_" not in lane_id:
        return ""
    return lane_id.rsplit("_", 1)[0]
