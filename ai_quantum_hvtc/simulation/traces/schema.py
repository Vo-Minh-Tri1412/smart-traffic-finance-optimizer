from __future__ import annotations

from typing import Any

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.metrics import SimulationResult
from ai_quantum_hvtc.simulation.traces.versions import SIMULATION_TRACE_FRAME_SCHEMA_VERSION


def trace_frames_from_result(result: SimulationResult, spec: DistrictSpec) -> list[dict[str, Any]]:
    """Create a compact replay trace for the future React UI.

    SUMO results may carry real FCD vehicle frames. Lightweight validation backends return
    aggregate metrics, so they use an honest aggregate replay instead.
    """

    if result.vehicle_trace_frames:
        return [_with_trace_schema_version(frame) for frame in result.vehicle_trace_frames]

    step_seconds = spec.metadata.time_step_seconds
    frame_count = max(1, min(20, spec.metadata.horizon_seconds // step_seconds))
    sorted_intersections = sorted(
        result.intersections.values(), key=lambda item: item.intersection_id
    )
    frames: list[dict[str, Any]] = []
    for frame_index in range(frame_count):
        progress = (frame_index + 1) / frame_count
        frames.append(
            {
                "schema_version": SIMULATION_TRACE_FRAME_SCHEMA_VERSION,
                "timestep": frame_index,
                "time_seconds": frame_index * step_seconds,
                "district_id": spec.metadata.district_id,
                "scenario_id": result.scenario_id,
                "controller_id": result.controller_id,
                "engine_id": result.engine_id,
                "traffic_lights": {
                    intersection.intersection_id: _signal_state(
                        frame_index, intersection.intersection_id
                    )
                    for intersection in spec.intersections.values()
                    if intersection.signalized
                },
                "road_occupancy": [],
                "intersection_queues": [
                    {
                        "intersection_id": metric.intersection_id,
                        "queue_vehicles": round(metric.queue_vehicles * progress, 3),
                        "delay_seconds": round(metric.delay_seconds * progress, 3),
                    }
                    for metric in sorted_intersections
                ],
                "events": _events_for_frame(result, frame_index),
                "metrics": {
                    "average_waiting_time_seconds": round(
                        result.average_waiting_time_seconds * progress,
                        3,
                    ),
                    "throughput": int(round(result.throughput * progress)),
                    "emergency_delay_seconds": round(result.emergency_delay_seconds * progress, 3),
                    "truck_delay_seconds": round(result.truck_delay_seconds * progress, 3),
                },
            }
        )
    return frames


def _with_trace_schema_version(frame: dict[str, Any]) -> dict[str, Any]:
    if frame.get("schema_version") == SIMULATION_TRACE_FRAME_SCHEMA_VERSION:
        return frame
    return {"schema_version": SIMULATION_TRACE_FRAME_SCHEMA_VERSION, **frame}


def _signal_state(frame_index: int, intersection_id: str) -> str:
    phase = (frame_index + int(intersection_id.removeprefix("I") or "0")) % 3
    return "GREEN_NS" if phase == 0 else "GREEN_EW" if phase == 1 else "YELLOW"


def _events_for_frame(result: SimulationResult, frame_index: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if frame_index == 0:
        events.append(
            {
                "type": "scenario_start",
                "scenario_id": result.scenario_id,
                "controller_id": result.controller_id,
            }
        )
    if result.emergency_delay_seconds > 0 and frame_index == 2:
        events.append({"type": "emergency_delay_observed"})
    if result.failed_route_count is not None and result.failed_route_count > 0 and frame_index == 3:
        events.append({"type": "failed_routes_observed", "count": result.failed_route_count})
    return events
