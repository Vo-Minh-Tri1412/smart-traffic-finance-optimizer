"""Sensor and computer-vision input contracts."""

from __future__ import annotations

from .domain import DetectedVehicle, SensorObservation, TrafficCount, aggregate_vehicle_counts

__all__ = [
    "DetectedVehicle",
    "SensorObservation",
    "TrafficCount",
    "aggregate_vehicle_counts",
]
