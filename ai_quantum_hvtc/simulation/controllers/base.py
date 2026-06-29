from __future__ import annotations

from dataclasses import dataclass

from ai_quantum_hvtc.simulation.domain import Road, VehicleType


@dataclass(frozen=True)
class ControllerProfile:
    controller_id: str
    general_delay_multiplier: float
    emergency_delay_multiplier: float
    bus_delay_multiplier: float
    truck_delay_multiplier: float
    queue_multiplier: float

    def delay_multiplier(self, *, vehicle_type: VehicleType, road: Road) -> float:
        multiplier = self.general_delay_multiplier
        if vehicle_type.vehicle_type_id == "AMBULANCE" or vehicle_type.priority_level >= 10:
            multiplier *= self.emergency_delay_multiplier
        if vehicle_type.vehicle_type_id in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
            multiplier *= self.bus_delay_multiplier
        if vehicle_type.vehicle_type_id in {"HEAVY_TRUCK", "LIGHT_TRUCK"}:
            multiplier *= self.truck_delay_multiplier
        if "HOSPITAL_ACCESS" in road.tags and vehicle_type.vehicle_type_id == "AMBULANCE":
            multiplier *= 0.85
        return multiplier
