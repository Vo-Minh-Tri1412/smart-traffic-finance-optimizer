from __future__ import annotations

from dataclasses import dataclass
from random import Random

from ai_quantum_hvtc.simulation.controllers import controller_profile
from ai_quantum_hvtc.simulation.domain import DistrictSpec, Flow, Road, Scenario, VehicleType
from ai_quantum_hvtc.simulation.engines.base import SimulationEngine
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.routing import Route, RouteNotFoundError, RoutePlanner


@dataclass(frozen=True)
class PlannedMovement:
    flow: Flow
    vehicle_type: VehicleType
    count: int
    route: Route


class ReferenceGraphEngine(SimulationEngine):
    engine_id = "reference"

    def run(
        self,
        *,
        spec: DistrictSpec,
        scenario_id: str,
        controller_id: str,
        seed: int,
    ) -> SimulationResult:
        if scenario_id not in spec.scenarios:
            raise ValueError(f"unknown scenario_id: {scenario_id}")
        if controller_id not in spec.controllers:
            raise ValueError(f"unknown controller_id: {controller_id}")

        scenario = spec.scenarios[scenario_id]
        controller = controller_profile(controller_id)
        planner = RoutePlanner(spec)
        rng = Random(seed)

        planned: list[PlannedMovement] = []
        failed_route_count = 0
        total_vehicles = 0
        road_load_pcu = {road_id: 0.0 for road_id in spec.roads}

        for flow in spec.flows.values():
            multiplier = scenario.flow_multipliers.get(flow.flow_id, 1.0)
            flow_volume = max(0, int(round(flow.base_volume * multiplier)))
            for vehicle_type_id, share in sorted(flow.vehicle_mix.items()):
                vehicle_type = spec.vehicle_types[vehicle_type_id]
                count = int(round(flow_volume * share))
                if count <= 0:
                    continue
                total_vehicles += count
                try:
                    route = planner.find_route(
                        flow=flow,
                        vehicle_type=vehicle_type,
                        scenario=scenario,
                    )
                except RouteNotFoundError:
                    failed_route_count += count
                    continue
                planned.append(
                    PlannedMovement(flow=flow, vehicle_type=vehicle_type, count=count, route=route)
                )
                for road_id in route.road_ids:
                    road_load_pcu[road_id] += count * vehicle_type.pcu

        intersections = {
            intersection_id: IntersectionMetric(intersection_id=intersection_id)
            for intersection_id in spec.intersections
        }

        road_queue = {
            road_id: self._road_queue(spec.roads[road_id], scenario, road_load)
            for road_id, road_load in road_load_pcu.items()
        }

        total_waiting_time_seconds = 0.0
        stopped_vehicles = 0
        emergency_delay_seconds = 0.0
        bus_passenger_delay_seconds = 0.0
        truck_delay_seconds = 0.0

        for movement in planned:
            max_route_load_ratio = max(
                self._load_ratio(spec.roads[road_id], scenario, road_load_pcu[road_id])
                for road_id in movement.route.road_ids
            )
            if max_route_load_ratio > 1.0:
                stopped_vehicles += int(
                    round(movement.count * min(max_route_load_ratio - 1.0, 1.0))
                )

            for road_id in movement.route.road_ids:
                road = spec.roads[road_id]
                load_ratio = self._load_ratio(road, scenario, road_load_pcu[road_id])
                delay_per_vehicle = self._delay_per_vehicle_seconds(road, load_ratio, rng)
                delay = (
                    delay_per_vehicle
                    * movement.count
                    * controller.delay_multiplier(vehicle_type=movement.vehicle_type, road=road)
                )
                total_waiting_time_seconds += delay

                intersection_metric = intersections[road.to_intersection]
                intersection_metric.delay_seconds += delay
                intersection_metric.vehicles += movement.count
                queue_value = road_queue[road_id] * controller.queue_multiplier
                intersection_metric.queue_vehicles = max(
                    intersection_metric.queue_vehicles,
                    queue_value,
                )

                if movement.vehicle_type.vehicle_type_id == "AMBULANCE":
                    emergency_delay_seconds += delay
                    intersection_metric.emergency_delay_seconds += delay
                if movement.vehicle_type.vehicle_type_id in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
                    passenger_delay = delay * movement.vehicle_type.passenger_count
                    bus_passenger_delay_seconds += passenger_delay
                    assert intersection_metric.bus_passenger_delay_seconds is not None
                    intersection_metric.bus_passenger_delay_seconds += passenger_delay
                if movement.vehicle_type.vehicle_type_id in {"HEAVY_TRUCK", "LIGHT_TRUCK"}:
                    truck_delay_seconds += delay
                    intersection_metric.truck_delay_seconds += delay

        queue_values = list(road_queue.values())
        throughput = max(0, total_vehicles - failed_route_count - stopped_vehicles)
        average_waiting = total_waiting_time_seconds / total_vehicles if total_vehicles else 0.0

        return SimulationResult(
            scenario_id=scenario_id,
            controller_id=controller_id,
            engine_id=self.engine_id,
            seed=seed,
            total_vehicles=total_vehicles,
            throughput=throughput,
            total_waiting_time_seconds=round(total_waiting_time_seconds, 3),
            average_waiting_time_seconds=round(average_waiting, 3),
            max_queue_vehicles=round(
                max(queue_values, default=0.0) * controller.queue_multiplier, 3
            ),
            average_queue_vehicles=round(
                (sum(queue_values) / len(queue_values) if queue_values else 0.0)
                * controller.queue_multiplier,
                3,
            ),
            stopped_vehicles=stopped_vehicles,
            emergency_delay_seconds=round(emergency_delay_seconds, 3),
            bus_passenger_delay_seconds=round(bus_passenger_delay_seconds, 3),
            truck_delay_seconds=round(truck_delay_seconds, 3),
            reroute_count=0,
            failed_route_count=failed_route_count,
            intersections=intersections,
        )

    @staticmethod
    def _effective_capacity(road: Road, scenario: Scenario) -> float:
        return road.capacity * scenario.road_capacity_multipliers.get(road.road_id, 1.0)

    def _load_ratio(self, road: Road, scenario: Scenario, load_pcu: float) -> float:
        effective_capacity = self._effective_capacity(road, scenario)
        if effective_capacity <= 0:
            return float("inf")
        return load_pcu / effective_capacity

    def _road_queue(self, road: Road, scenario: Scenario, load_pcu: float) -> float:
        effective_capacity = self._effective_capacity(road, scenario)
        return max(0.0, load_pcu - effective_capacity)

    @staticmethod
    def _delay_per_vehicle_seconds(road: Road, load_ratio: float, rng: Random) -> float:
        signal_delay = 8.0 + 18.0 * min(load_ratio, 2.5)
        spillback_delay = max(0.0, load_ratio - 0.80) * road.free_flow_seconds * 1.8
        jitter = rng.uniform(0.98, 1.02)
        return (signal_delay + spillback_delay) * jitter
