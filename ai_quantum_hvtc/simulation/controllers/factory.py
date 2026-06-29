from __future__ import annotations

from ai_quantum_hvtc.simulation.controllers.base import ControllerProfile


def controller_profile(controller_id: str) -> ControllerProfile:
    if controller_id == "fixed_time":
        return ControllerProfile(
            controller_id=controller_id,
            general_delay_multiplier=1.0,
            emergency_delay_multiplier=1.0,
            bus_delay_multiplier=1.0,
            truck_delay_multiplier=1.0,
            queue_multiplier=1.0,
        )
    if controller_id == "rule_based":
        return ControllerProfile(
            controller_id=controller_id,
            general_delay_multiplier=0.92,
            emergency_delay_multiplier=0.55,
            bus_delay_multiplier=0.78,
            truck_delay_multiplier=0.88,
            queue_multiplier=0.85,
        )
    if controller_id == "rl_policy":
        return ControllerProfile(
            controller_id=controller_id,
            general_delay_multiplier=0.86,
            emergency_delay_multiplier=0.60,
            bus_delay_multiplier=0.75,
            truck_delay_multiplier=0.82,
            queue_multiplier=0.80,
        )
    raise ValueError(f"unknown controller_id: {controller_id}")
