from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DetectedVehicle:
    vehicle_id: str
    vehicle_type_id: str
    confidence: float
    road_id: str | None = None
    intersection_id: str | None = None


@dataclass(frozen=True)
class SensorObservation:
    sensor_id: str
    timestamp_seconds: int
    source_type: str
    detections: tuple[DetectedVehicle, ...] = ()
    caveats: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrafficCount:
    sensor_id: str
    timestamp_seconds: int
    counts_by_vehicle_type: dict[str, int] = field(default_factory=dict)
    total_count: int = 0


def aggregate_vehicle_counts(observation: SensorObservation) -> TrafficCount:
    counts: dict[str, int] = {}
    for detection in observation.detections:
        counts[detection.vehicle_type_id] = counts.get(detection.vehicle_type_id, 0) + 1
    return TrafficCount(
        sensor_id=observation.sensor_id,
        timestamp_seconds=observation.timestamp_seconds,
        counts_by_vehicle_type=counts,
        total_count=sum(counts.values()),
    )
