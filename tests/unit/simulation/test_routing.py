from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.simulation.routing import RoutePlanner
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_heavy_truck_route_avoids_restricted_roads() -> None:
    spec = load_district_spec(SPEC_PATH)
    planner = RoutePlanner(spec)
    flow = spec.flows["F_LOGISTICS_DELIVERY"]
    vehicle_type = spec.vehicle_types["HEAVY_TRUCK"]
    scenario = spec.scenarios["normal_weekday"]

    route = planner.find_route(flow=flow, vehicle_type=vehicle_type, scenario=scenario)

    assert route.road_ids
    assert all("TRUCK_RESTRICTED" not in spec.roads[road_id].tags for road_id in route.road_ids)
    assert all(spec.roads[road_id].truck_allowed for road_id in route.road_ids)


def test_ambulance_priority_route_reaches_hospital_access() -> None:
    spec = load_district_spec(SPEC_PATH)
    planner = RoutePlanner(spec)
    flow = spec.flows["F_MEDICAL_EMERGENCY"]
    vehicle_type = spec.vehicle_types["AMBULANCE"]
    scenario = spec.scenarios["hospital_emergency"]

    route = planner.find_route(flow=flow, vehicle_type=vehicle_type, scenario=scenario)

    assert route.road_ids
    assert any("HOSPITAL_ACCESS" in spec.roads[road_id].tags for road_id in route.road_ids)
