from __future__ import annotations

from ai_quantum_hvtc.sensors import DetectedVehicle, SensorObservation, aggregate_vehicle_counts


def test_sensor_observation_aggregates_vehicle_counts() -> None:
    observation = SensorObservation(
        sensor_id="CAM_I06_N",
        timestamp_seconds=120,
        source_type="camera_cv",
        detections=(
            DetectedVehicle("v1", "MOTORBIKE", 0.91, intersection_id="I06"),
            DetectedVehicle("v2", "MOTORBIKE", 0.88, intersection_id="I06"),
            DetectedVehicle("v3", "AMBULANCE", 0.97, intersection_id="I06"),
        ),
    )

    count = aggregate_vehicle_counts(observation)

    assert count.total_count == 3
    assert count.counts_by_vehicle_type == {"MOTORBIKE": 2, "AMBULANCE": 1}
