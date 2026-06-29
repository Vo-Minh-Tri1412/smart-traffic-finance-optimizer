"""Sensor and computer-vision input contracts."""

from __future__ import annotations

from .domain import DetectedVehicle, SensorObservation, TrafficCount, aggregate_vehicle_counts
from .synthetic_cv import (
    DEFAULT_SYNTHETIC_YOLO_CLASSES,
    DatasetValidationResult,
    SyntheticDatasetPaths,
    expected_yolo_paths,
    init_synthetic_yolo_dataset,
    validate_synthetic_yolo_dataset,
)

__all__ = [
    "DEFAULT_SYNTHETIC_YOLO_CLASSES",
    "DatasetValidationResult",
    "DetectedVehicle",
    "SensorObservation",
    "SyntheticDatasetPaths",
    "TrafficCount",
    "aggregate_vehicle_counts",
    "expected_yolo_paths",
    "init_synthetic_yolo_dataset",
    "validate_synthetic_yolo_dataset",
]
