"""Sensor and computer-vision input contracts."""

from __future__ import annotations

from .domain import DetectedVehicle, SensorObservation, TrafficCount, aggregate_vehicle_counts
from .geometry_camera import (
    CAMERA_CALIBRATION_SCHEMA_VERSION,
    SENSOR_OBSERVATION_SCHEMA_VERSION,
    VISIBILITY_TRACE_SCHEMA_VERSION,
    CameraCalibration,
    GeometryContractError,
    GeometryObservationAdapter,
    GeometrySensorObservation,
    StaticOccluder,
    VehicleBox,
    VisibilityRecord,
    load_camera_calibrations,
    visibility_for_frame,
    visibility_from_trace_frames,
    write_camera_calibrations,
    write_visibility_trace,
)
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
    "CAMERA_CALIBRATION_SCHEMA_VERSION",
    "DetectedVehicle",
    "CameraCalibration",
    "GeometryContractError",
    "GeometryObservationAdapter",
    "GeometrySensorObservation",
    "SensorObservation",
    "SENSOR_OBSERVATION_SCHEMA_VERSION",
    "StaticOccluder",
    "SyntheticDatasetPaths",
    "TrafficCount",
    "VehicleBox",
    "VisibilityRecord",
    "VISIBILITY_TRACE_SCHEMA_VERSION",
    "aggregate_vehicle_counts",
    "expected_yolo_paths",
    "init_synthetic_yolo_dataset",
    "load_camera_calibrations",
    "validate_synthetic_yolo_dataset",
    "visibility_for_frame",
    "visibility_from_trace_frames",
    "write_camera_calibrations",
    "write_visibility_trace",
]
