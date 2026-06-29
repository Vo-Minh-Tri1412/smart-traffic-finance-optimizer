from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.domain import (
    ControllerConfig,
    DistrictSpec,
    FinanceAssumptions,
    Flow,
    Intersection,
    InvestmentCandidate,
    Metadata,
    Road,
    Scenario,
    VehicleType,
    Zone,
)
from ai_quantum_hvtc.simulation.specs.validation import validate_spec


def _tuple_of_strings(data: Any) -> tuple[str, ...]:
    if data is None:
        return ()
    if not isinstance(data, list):
        raise TypeError("expected a list of strings")
    return tuple(str(item) for item in data)


def _string_float_dict(data: Any) -> dict[str, float]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError("expected an object with numeric values")
    return {str(key): float(value) for key, value in data.items()}


def _metadata(data: dict[str, Any]) -> Metadata:
    return Metadata(
        district_id=str(data["id"]),
        name=str(data["name"]),
        version=str(data["version"]),
        horizon_seconds=int(data["horizon_seconds"]),
        time_step_seconds=int(data["time_step_seconds"]),
    )


def _zones(items: list[dict[str, Any]]) -> dict[str, Zone]:
    zones: dict[str, Zone] = {}
    for item in items:
        zone = Zone(
            zone_id=str(item["id"]),
            name=str(item["name"]),
            zone_type=str(item["type"]),
            intersection_ids=_tuple_of_strings(item["intersection_ids"]),
            economic_role=str(item.get("economic_role", "")),
            peak_windows=_tuple_of_strings(item.get("peak_windows", [])),
        )
        zones[zone.zone_id] = zone
    return zones


def _intersections(items: list[dict[str, Any]]) -> dict[str, Intersection]:
    intersections: dict[str, Intersection] = {}
    for item in items:
        intersection = Intersection(
            intersection_id=str(item["id"]),
            name=str(item["name"]),
            x=float(item["x"]),
            y=float(item["y"]),
            tags=_tuple_of_strings(item.get("tags", [])),
            signalized=bool(item.get("signalized", True)),
        )
        intersections[intersection.intersection_id] = intersection
    return intersections


def _roads(items: list[dict[str, Any]]) -> dict[str, Road]:
    roads: dict[str, Road] = {}
    for item in items:
        road = Road(
            road_id=str(item["id"]),
            from_intersection=str(item["from"]),
            to_intersection=str(item["to"]),
            length_km=float(item["length_km"]),
            speed_kph=float(item["speed_kph"]),
            lanes=int(item["lanes"]),
            capacity=float(item["capacity"]),
            tags=_tuple_of_strings(item.get("tags", [])),
            truck_allowed=bool(item.get("truck_allowed", True)),
        )
        roads[road.road_id] = road
    return roads


def _vehicle_types(items: list[dict[str, Any]]) -> dict[str, VehicleType]:
    vehicle_types: dict[str, VehicleType] = {}
    for item in items:
        defaults = _vehicle_type_defaults(str(item["id"]))
        vehicle_type = VehicleType(
            vehicle_type_id=str(item["id"]),
            passenger_count=float(item["passenger_count"]),
            pcu=float(item["pcu"]),
            value_class=str(item["value_class"]),
            priority_level=int(item.get("priority_level", 0)),
            forbidden_road_tags=_tuple_of_strings(item.get("forbidden_road_tags", [])),
            length_m=float(item.get("length_m", defaults["length_m"])),
            width_m=float(item.get("width_m", defaults["width_m"])),
            max_speed_kph=float(item.get("max_speed_kph", defaults["max_speed_kph"])),
            accel_mps2=float(item.get("accel_mps2", defaults["accel_mps2"])),
            decel_mps2=float(item.get("decel_mps2", defaults["decel_mps2"])),
            min_gap_m=float(item.get("min_gap_m", defaults["min_gap_m"])),
        )
        vehicle_types[vehicle_type.vehicle_type_id] = vehicle_type
    return vehicle_types


def _vehicle_type_defaults(vehicle_type_id: str) -> dict[str, float]:
    defaults = {
        "length_m": 4.5,
        "width_m": 1.8,
        "max_speed_kph": 50.0,
        "accel_mps2": 2.6,
        "decel_mps2": 4.5,
        "min_gap_m": 2.5,
    }
    overrides: dict[str, dict[str, float]] = {
        "MOTORBIKE": {
            "length_m": 2.0,
            "width_m": 0.7,
            "max_speed_kph": 45.0,
            "accel_mps2": 3.0,
            "decel_mps2": 5.0,
            "min_gap_m": 1.0,
        },
        "DELIVERY_BIKE": {
            "length_m": 2.0,
            "width_m": 0.7,
            "max_speed_kph": 40.0,
            "accel_mps2": 2.8,
            "decel_mps2": 5.0,
            "min_gap_m": 1.0,
        },
        "BUS": {"length_m": 12.0, "width_m": 2.5, "max_speed_kph": 45.0, "min_gap_m": 3.0},
        "SCHOOL_BUS": {
            "length_m": 10.0,
            "width_m": 2.4,
            "max_speed_kph": 40.0,
            "min_gap_m": 3.0,
        },
        "WORKER_SHUTTLE": {
            "length_m": 9.0,
            "width_m": 2.3,
            "max_speed_kph": 45.0,
            "min_gap_m": 3.0,
        },
        "AMBULANCE": {
            "length_m": 5.5,
            "width_m": 2.0,
            "max_speed_kph": 70.0,
            "accel_mps2": 3.5,
            "decel_mps2": 5.5,
            "min_gap_m": 2.0,
        },
        "LIGHT_TRUCK": {"length_m": 6.5, "width_m": 2.2, "max_speed_kph": 50.0},
        "HEAVY_TRUCK": {
            "length_m": 12.0,
            "width_m": 2.5,
            "max_speed_kph": 40.0,
            "accel_mps2": 1.2,
            "decel_mps2": 3.5,
            "min_gap_m": 3.5,
        },
    }
    return {**defaults, **overrides.get(vehicle_type_id, {})}


def _flows(items: list[dict[str, Any]]) -> dict[str, Flow]:
    flows: dict[str, Flow] = {}
    for item in items:
        flow = Flow(
            flow_id=str(item["id"]),
            origin_zone=str(item["origin_zone"]),
            destination_zone=str(item["destination_zone"]),
            trip_purpose=str(item["trip_purpose"]),
            departure_start=int(item["departure_start"]),
            departure_end=int(item["departure_end"]),
            base_volume=int(item["base_volume"]),
            vehicle_mix=_string_float_dict(item["vehicle_mix"]),
            route_policy=str(item["route_policy"]),
            fixed_route=_tuple_of_strings(item.get("fixed_route", [])),
        )
        flows[flow.flow_id] = flow
    return flows


def _scenarios(items: list[dict[str, Any]]) -> dict[str, Scenario]:
    scenarios: dict[str, Scenario] = {}
    for item in items:
        scenario = Scenario(
            scenario_id=str(item["id"]),
            name=str(item["name"]),
            description=str(item.get("description", "")),
            flow_multipliers=_string_float_dict(item.get("flow_multipliers", {})),
            road_capacity_multipliers=_string_float_dict(item.get("road_capacity_multipliers", {})),
            closed_roads=_tuple_of_strings(item.get("closed_roads", [])),
        )
        scenarios[scenario.scenario_id] = scenario
    return scenarios


def _controllers(items: list[dict[str, Any]]) -> dict[str, ControllerConfig]:
    controllers: dict[str, ControllerConfig] = {}
    for item in items:
        controller = ControllerConfig(
            controller_id=str(item["id"]),
            name=str(item["name"]),
            controller_type=str(item["type"]),
        )
        controllers[controller.controller_id] = controller
    return controllers


def _investment_candidates(items: list[dict[str, Any]]) -> dict[str, InvestmentCandidate]:
    candidates: dict[str, InvestmentCandidate] = {}
    for item in items:
        candidate = InvestmentCandidate(
            candidate_id=str(item["id"]),
            intersection_id=str(item["intersection_id"]),
            upgrade_type=str(item["upgrade_type"]),
            capex_vnd=float(item["capex_vnd"]),
            annual_maintenance_vnd=float(item["annual_maintenance_vnd"]),
            affected_flow_ids=_tuple_of_strings(item.get("affected_flow_ids", [])),
            caveat=str(item.get("caveat", "placeholder")),
        )
        candidates[candidate.candidate_id] = candidate
    return candidates


def _finance_assumptions(data: dict[str, Any]) -> FinanceAssumptions:
    return FinanceAssumptions(
        value_of_time_vnd_per_hour=float(data["value_of_time_vnd_per_hour"]),
        bus_passenger_value_multiplier=float(data["bus_passenger_value_multiplier"]),
        emergency_delay_value_vnd_per_hour=float(data["emergency_delay_value_vnd_per_hour"]),
        logistics_delay_value_vnd_per_truck_hour=float(
            data["logistics_delay_value_vnd_per_truck_hour"]
        ),
        fuel_emission_saving_vnd_per_delay_hour=float(
            data["fuel_emission_saving_vnd_per_delay_hour"]
        ),
        deployment_risk_penalty_vnd=float(data["deployment_risk_penalty_vnd"]),
        assumption_status={str(key): str(value) for key, value in data.get("status", {}).items()},
    )


def district_spec_from_dict(data: dict[str, Any]) -> DistrictSpec:
    spec = DistrictSpec(
        metadata=_metadata(data["metadata"]),
        zones=_zones(data["zones"]),
        intersections=_intersections(data["intersections"]),
        roads=_roads(data["roads"]),
        vehicle_types=_vehicle_types(data["vehicle_types"]),
        flows=_flows(data["flows"]),
        scenarios=_scenarios(data["scenarios"]),
        controllers=_controllers(data["controllers"]),
        investment_candidates=_investment_candidates(data["investment_candidates"]),
        finance_assumptions=_finance_assumptions(data["finance_assumptions"]),
        raw=data,
    )
    validate_spec(spec)
    return spec


def load_district_spec(path: Path | str) -> DistrictSpec:
    spec_path = Path(path)
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{spec_path}: root JSON value must be an object")
    return district_spec_from_dict(data)
