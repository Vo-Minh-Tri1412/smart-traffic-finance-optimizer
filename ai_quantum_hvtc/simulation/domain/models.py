from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Metadata:
    district_id: str
    name: str
    version: str
    horizon_seconds: int
    time_step_seconds: int


@dataclass(frozen=True)
class Zone:
    zone_id: str
    name: str
    zone_type: str
    intersection_ids: tuple[str, ...]
    economic_role: str
    peak_windows: tuple[str, ...] = ()


@dataclass(frozen=True)
class Intersection:
    intersection_id: str
    name: str
    x: float
    y: float
    tags: tuple[str, ...] = ()
    signalized: bool = True


@dataclass(frozen=True)
class Road:
    road_id: str
    from_intersection: str
    to_intersection: str
    length_km: float
    speed_kph: float
    lanes: int
    capacity: float
    tags: tuple[str, ...] = ()
    truck_allowed: bool = True
    lane_width_m: float = 3.2
    sidewalk_width_m: float = 0.0
    median_width_m: float = 0.0
    visual_width_m: float = 0.0
    shape_points: tuple[tuple[float, float], ...] = ()

    @property
    def free_flow_seconds(self) -> float:
        return (self.length_km / self.speed_kph) * 3600.0


@dataclass(frozen=True)
class VehicleType:
    vehicle_type_id: str
    passenger_count: float
    pcu: float
    value_class: str
    priority_level: int = 0
    forbidden_road_tags: tuple[str, ...] = ()
    length_m: float = 4.5
    width_m: float = 1.8
    height_m: float = 1.5
    ground_clearance_m: float = 0.0
    v_class: str = "passenger"
    max_speed_kph: float = 50.0
    accel_mps2: float = 2.6
    decel_mps2: float = 4.5
    min_gap_m: float = 2.5
    tau_seconds: float = 1.2
    emergency_decel_mps2: float = 7.0
    apparent_decel_mps2: float = 4.5
    action_step_length_seconds: float = 1.0
    max_speed_lat_mps: float = 0.0
    min_gap_lat_m: float = 0.0
    lat_alignment: str = "center"
    lc_sublane: float = 0.0
    lc_pushy: float = 0.0


@dataclass(frozen=True)
class Flow:
    flow_id: str
    origin_zone: str
    destination_zone: str
    trip_purpose: str
    departure_start: int
    departure_end: int
    base_volume: int
    vehicle_mix: dict[str, float]
    route_policy: str
    fixed_route: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    description: str
    flow_multipliers: dict[str, float] = field(default_factory=dict)
    road_capacity_multipliers: dict[str, float] = field(default_factory=dict)
    closed_roads: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControllerConfig:
    controller_id: str
    name: str
    controller_type: str


@dataclass(frozen=True)
class InvestmentCandidate:
    candidate_id: str
    intersection_id: str
    upgrade_type: str
    capex_vnd: float
    annual_maintenance_vnd: float
    affected_flow_ids: tuple[str, ...] = ()
    caveat: str = "placeholder"


@dataclass(frozen=True)
class FinanceAssumptions:
    value_of_time_vnd_per_hour: float
    bus_passenger_value_multiplier: float
    emergency_delay_value_vnd_per_hour: float
    logistics_delay_value_vnd_per_truck_hour: float
    fuel_emission_saving_vnd_per_delay_hour: float
    deployment_risk_penalty_vnd: float
    assumption_status: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DistrictSpec:
    metadata: Metadata
    zones: dict[str, Zone]
    intersections: dict[str, Intersection]
    roads: dict[str, Road]
    vehicle_types: dict[str, VehicleType]
    flows: dict[str, Flow]
    scenarios: dict[str, Scenario]
    controllers: dict[str, ControllerConfig]
    investment_candidates: dict[str, InvestmentCandidate]
    finance_assumptions: FinanceAssumptions
    raw: dict[str, Any] = field(default_factory=dict)

    def zone_origin_intersection(self, zone_id: str) -> str:
        return self.zones[zone_id].intersection_ids[0]

    def zone_destination_intersection(self, zone_id: str) -> str:
        return self.zones[zone_id].intersection_ids[-1]
