from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IntersectionMetric:
    intersection_id: str
    delay_seconds: float = 0.0
    queue_vehicles: float = 0.0
    vehicles: int = 0
    emergency_delay_seconds: float = 0.0
    bus_passenger_delay_seconds: float = 0.0
    truck_delay_seconds: float = 0.0


@dataclass
class SimulationResult:
    scenario_id: str
    controller_id: str
    engine_id: str
    seed: int
    total_vehicles: int
    throughput: int
    total_waiting_time_seconds: float
    average_waiting_time_seconds: float
    max_queue_vehicles: float
    average_queue_vehicles: float
    stopped_vehicles: int
    emergency_delay_seconds: float
    bus_passenger_delay_seconds: float
    truck_delay_seconds: float
    reroute_count: int
    failed_route_count: int
    intersections: dict[str, IntersectionMetric] = field(default_factory=dict)
    vehicle_trace_frames: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("vehicle_trace_frames", None)
        data["intersections"] = {key: asdict(value) for key, value in self.intersections.items()}
        return data
