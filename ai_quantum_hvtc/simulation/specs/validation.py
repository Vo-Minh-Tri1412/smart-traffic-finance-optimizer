from __future__ import annotations

from collections.abc import Iterable

from ai_quantum_hvtc.simulation.domain import DistrictSpec, Flow


class SpecValidationError(ValueError):
    """Raised when a district spec is structurally invalid."""


def _require_unique(ids: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)
    if duplicates:
        formatted = ", ".join(sorted(duplicates))
        raise SpecValidationError(f"duplicate {label} id(s): {formatted}")


def _validate_flow_mix(flow: Flow) -> None:
    total_share = sum(flow.vehicle_mix.values())
    if abs(total_share - 1.0) > 0.001:
        raise SpecValidationError(
            f"{flow.flow_id}: vehicle_mix shares must sum to 1.0, got {total_share:.3f}"
        )
    if flow.departure_end <= flow.departure_start:
        raise SpecValidationError(f"{flow.flow_id}: departure_end must be after departure_start")
    if flow.base_volume < 0:
        raise SpecValidationError(f"{flow.flow_id}: base_volume must be non-negative")


def validate_spec(spec: DistrictSpec) -> None:
    _require_unique(spec.zones, "zone")
    _require_unique(spec.intersections, "intersection")
    _require_unique(spec.roads, "road")
    _require_unique(spec.vehicle_types, "vehicle_type")
    _require_unique(spec.flows, "flow")

    if spec.metadata.time_step_seconds <= 0:
        raise SpecValidationError("metadata.time_step_seconds must be positive")
    if spec.metadata.horizon_seconds <= spec.metadata.time_step_seconds:
        raise SpecValidationError("metadata.horizon_seconds must exceed time_step_seconds")

    for zone in spec.zones.values():
        if not zone.intersection_ids:
            raise SpecValidationError(f"{zone.zone_id}: zone must list at least one intersection")
        for intersection_id in zone.intersection_ids:
            if intersection_id not in spec.intersections:
                raise SpecValidationError(
                    f"{zone.zone_id}: unknown intersection_id {intersection_id}"
                )

    for road in spec.roads.values():
        if road.from_intersection not in spec.intersections:
            raise SpecValidationError(f"{road.road_id}: unknown from intersection")
        if road.to_intersection not in spec.intersections:
            raise SpecValidationError(f"{road.road_id}: unknown to intersection")
        if road.length_km <= 0 or road.speed_kph <= 0 or road.lanes <= 0 or road.capacity <= 0:
            raise SpecValidationError(f"{road.road_id}: road dimensions must be positive")

    for flow in spec.flows.values():
        _validate_flow_mix(flow)
        if flow.origin_zone not in spec.zones:
            raise SpecValidationError(f"{flow.flow_id}: unknown origin_zone")
        if flow.destination_zone not in spec.zones:
            raise SpecValidationError(f"{flow.flow_id}: unknown destination_zone")
        for vehicle_type_id in flow.vehicle_mix:
            if vehicle_type_id not in spec.vehicle_types:
                raise SpecValidationError(f"{flow.flow_id}: unknown vehicle_type {vehicle_type_id}")
        for road_id in flow.fixed_route:
            if road_id not in spec.roads:
                raise SpecValidationError(f"{flow.flow_id}: unknown fixed_route road {road_id}")
            road = spec.roads[road_id]
            if "HEAVY_TRUCK" in flow.vehicle_mix and (
                not road.truck_allowed or "TRUCK_RESTRICTED" in road.tags
            ):
                raise SpecValidationError(
                    f"{flow.flow_id}: HEAVY_TRUCK fixed route uses restricted road {road_id}"
                )

    for scenario in spec.scenarios.values():
        for flow_id in scenario.flow_multipliers:
            if flow_id not in spec.flows:
                raise SpecValidationError(f"{scenario.scenario_id}: unknown flow {flow_id}")
        for road_id in scenario.road_capacity_multipliers:
            if road_id not in spec.roads:
                raise SpecValidationError(f"{scenario.scenario_id}: unknown road {road_id}")
        for road_id in scenario.closed_roads:
            if road_id not in spec.roads:
                raise SpecValidationError(f"{scenario.scenario_id}: unknown closed road {road_id}")

    for candidate in spec.investment_candidates.values():
        if candidate.intersection_id not in spec.intersections:
            raise SpecValidationError(f"{candidate.candidate_id}: unknown intersection_id")
        for flow_id in candidate.affected_flow_ids:
            if flow_id not in spec.flows:
                raise SpecValidationError(f"{candidate.candidate_id}: unknown affected flow")
        if candidate.capex_vnd < 0 or candidate.annual_maintenance_vnd < 0:
            raise SpecValidationError(f"{candidate.candidate_id}: costs must be non-negative")
