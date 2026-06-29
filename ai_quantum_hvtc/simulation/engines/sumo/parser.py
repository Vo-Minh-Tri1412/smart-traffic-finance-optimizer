from __future__ import annotations

import xml.etree.ElementTree as ET

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.engines.sumo.exporter import SumoExportPaths
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult


def parse_sumo_result(
    *,
    paths: SumoExportPaths,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    seed: int,
) -> SimulationResult:
    tripinfos = _tripinfo_rows(paths)
    waiting_times = [float(row.get("waitingTime", "0") or 0.0) for row in tripinfos]
    total_waiting = sum(waiting_times)
    total_vehicles = len(tripinfos)
    average_waiting = total_waiting / total_vehicles if total_vehicles else 0.0

    return SimulationResult(
        scenario_id=scenario_id,
        controller_id=controller_id,
        engine_id="sumo",
        seed=seed,
        total_vehicles=total_vehicles,
        throughput=total_vehicles,
        total_waiting_time_seconds=round(total_waiting, 3),
        average_waiting_time_seconds=round(average_waiting, 3),
        max_queue_vehicles=0.0,
        average_queue_vehicles=0.0,
        stopped_vehicles=sum(1 for value in waiting_times if value > 0),
        emergency_delay_seconds=_delay_for_type(tripinfos, "AMBULANCE"),
        bus_passenger_delay_seconds=_delay_for_types(
            tripinfos,
            {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"},
        ),
        truck_delay_seconds=_delay_for_types(tripinfos, {"LIGHT_TRUCK", "HEAVY_TRUCK"}),
        reroute_count=0,
        failed_route_count=0,
        intersections={
            intersection_id: IntersectionMetric(intersection_id=intersection_id)
            for intersection_id in spec.intersections
        },
    )


def _tripinfo_rows(paths: SumoExportPaths) -> list[dict[str, str]]:
    if not paths.tripinfo.is_file():
        return []
    tree = ET.parse(paths.tripinfo)
    return [dict(element.attrib) for element in tree.getroot().iter("tripinfo")]


def _delay_for_type(rows: list[dict[str, str]], vehicle_type_id: str) -> float:
    return _delay_for_types(rows, {vehicle_type_id})


def _delay_for_types(rows: list[dict[str, str]], vehicle_type_ids: set[str]) -> float:
    total = 0.0
    for row in rows:
        vehicle_id = row.get("id", "")
        if any(f"_{vehicle_type_id}." in vehicle_id for vehicle_type_id in vehicle_type_ids):
            total += float(row.get("waitingTime", "0") or 0.0)
    return round(total, 3)
