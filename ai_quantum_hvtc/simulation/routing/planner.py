from __future__ import annotations

import heapq
from dataclasses import dataclass

from ai_quantum_hvtc.simulation.domain import DistrictSpec, Flow, Road, Scenario, VehicleType


class RouteNotFoundError(ValueError):
    """Raised when no route can be found for a flow/vehicle pair."""


@dataclass(frozen=True)
class Route:
    road_ids: tuple[str, ...]
    total_distance_km: float
    free_flow_seconds: float
    cost: float


class RoutePlanner:
    def __init__(self, spec: DistrictSpec) -> None:
        self._spec = spec
        self._outgoing: dict[str, list[Road]] = {}
        for road in spec.roads.values():
            self._outgoing.setdefault(road.from_intersection, []).append(road)

    def find_route(
        self,
        *,
        flow: Flow,
        vehicle_type: VehicleType,
        scenario: Scenario,
    ) -> Route:
        if flow.fixed_route and flow.route_policy == "FIXED_ROUTE":
            return self._fixed_route(flow, vehicle_type, scenario)

        origin = self._spec.zone_origin_intersection(flow.origin_zone)
        destination = self._spec.zone_destination_intersection(flow.destination_zone)
        return self._dijkstra(origin, destination, flow.route_policy, vehicle_type, scenario)

    def _fixed_route(self, flow: Flow, vehicle_type: VehicleType, scenario: Scenario) -> Route:
        roads = [self._spec.roads[road_id] for road_id in flow.fixed_route]
        for road in roads:
            if not self._road_allowed(road, vehicle_type, flow.route_policy, scenario):
                raise RouteNotFoundError(
                    f"{flow.flow_id}: fixed route contains unavailable road {road.road_id}"
                )
        return self._route_from_roads(roads, cost=sum(road.free_flow_seconds for road in roads))

    def _dijkstra(
        self,
        origin: str,
        destination: str,
        route_policy: str,
        vehicle_type: VehicleType,
        scenario: Scenario,
    ) -> Route:
        queue: list[tuple[float, str, tuple[str, ...]]] = [(0.0, origin, ())]
        best_cost: dict[str, float] = {origin: 0.0}

        while queue:
            cost, node, road_ids = heapq.heappop(queue)
            if node == destination:
                roads = [self._spec.roads[road_id] for road_id in road_ids]
                return self._route_from_roads(roads, cost=cost)
            if cost > best_cost.get(node, float("inf")):
                continue

            for road in self._outgoing.get(node, []):
                if not self._road_allowed(road, vehicle_type, route_policy, scenario):
                    continue
                next_cost = cost + self._road_cost(road, route_policy, vehicle_type, scenario)
                if next_cost < best_cost.get(road.to_intersection, float("inf")):
                    best_cost[road.to_intersection] = next_cost
                    heapq.heappush(
                        queue, (next_cost, road.to_intersection, (*road_ids, road.road_id))
                    )

        raise RouteNotFoundError(f"no route from {origin} to {destination}")

    def _road_allowed(
        self,
        road: Road,
        vehicle_type: VehicleType,
        route_policy: str,
        scenario: Scenario,
    ) -> bool:
        if road.road_id in scenario.closed_roads:
            return False
        if set(road.tags).intersection(vehicle_type.forbidden_road_tags):
            return False
        is_heavy_truck = vehicle_type.vehicle_type_id == "HEAVY_TRUCK"
        if route_policy == "TRUCK_LEGAL_ROUTE" or is_heavy_truck:
            return road.truck_allowed and "TRUCK_RESTRICTED" not in road.tags
        return True

    def _road_cost(
        self,
        road: Road,
        route_policy: str,
        vehicle_type: VehicleType,
        scenario: Scenario,
    ) -> float:
        capacity_multiplier = scenario.road_capacity_multipliers.get(road.road_id, 1.0)
        if capacity_multiplier <= 0:
            return float("inf")

        if route_policy == "SHORTEST_DISTANCE":
            return road.length_km

        cost = road.free_flow_seconds
        if route_policy == "CONGESTION_AWARE":
            cost *= 1.0 + max(0.0, 1.0 - capacity_multiplier)
            if "BOTTLENECK" in road.tags or "BRIDGE_OR_NARROW_LINK" in road.tags:
                cost *= 1.25
            if "LOCAL_STREET" in road.tags:
                cost *= 1.10
        elif route_policy == "PRIORITY_FASTEST":
            if "HOSPITAL_ACCESS" in road.tags:
                cost *= 0.75
        elif route_policy == "TRUCK_LEGAL_ROUTE":
            if "TRUCK_ROUTE" in road.tags:
                cost *= 0.85
            if vehicle_type.vehicle_type_id == "HEAVY_TRUCK" and "LOCAL_STREET" in road.tags:
                cost *= 1.8
        return cost

    @staticmethod
    def _route_from_roads(roads: list[Road], *, cost: float) -> Route:
        return Route(
            road_ids=tuple(road.road_id for road in roads),
            total_distance_km=sum(road.length_km for road in roads),
            free_flow_seconds=sum(road.free_flow_seconds for road in roads),
            cost=cost,
        )
