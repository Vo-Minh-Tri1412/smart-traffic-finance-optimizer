from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_quantum_hvtc.sensors import (
    CameraCalibration,
    GeometryContractError,
    GeometryObservationAdapter,
    VehicleBox,
    load_camera_calibrations,
    visibility_for_frame,
    visibility_from_trace_frames,
    write_camera_calibrations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _camera() -> CameraCalibration:
    return CameraCalibration.from_fov(
        camera_id="CAM_GOLDEN",
        position_m=(0.0, -20.0, 5.0),
        yaw_degrees=0.0,
        pitch_degrees=-8.0,
        image_width=240,
        image_height=160,
        vertical_fov_degrees=42.0,
    )


def _vehicle(
    vehicle_id: str,
    *,
    front_y: float,
    width_m: float = 1.8,
    height_m: float = 1.5,
    length_m: float = 4.5,
    x: float = 0.0,
    lane_id: str = "inbound_0",
) -> VehicleBox:
    return VehicleBox(
        vehicle_id=vehicle_id,
        vehicle_type="BUS" if length_m > 8 else "PRIVATE_CAR",
        front_bumper_m=(x, front_y, 0.0),
        angle_degrees=0.0,
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
        ground_clearance_m=0.0,
        lane_id=lane_id,
        road_id="edge_inbound",
    )


def test_vehicle_box_converts_sumo_front_bumper_to_center() -> None:
    vehicle = _vehicle("car", front_y=10.0, length_m=4.0)

    assert vehicle.center_m == (0.0, 8.0, 0.75)


def test_geometry_camera_marks_single_vehicle_visible() -> None:
    records = visibility_for_frame(
        camera=_camera(),
        vehicles=(_vehicle("car", front_y=28.0),),
        time_seconds=1.0,
    )

    record = records[0]
    assert record.in_fov
    assert record.visibility_state == "visible"
    assert record.visible_fraction == 1.0
    assert record.depth_m is not None and record.depth_m > 0


def test_nearer_bus_occludes_car_behind_it_deterministically() -> None:
    records = visibility_for_frame(
        camera=_camera(),
        vehicles=(
            _vehicle("bus", front_y=16.0, width_m=3.0, height_m=4.0, length_m=12.0),
            _vehicle("car", front_y=31.0),
        ),
        time_seconds=1.0,
    )
    by_id = {record.vehicle_id: record for record in records}

    assert by_id["bus"].visibility_state == "visible"
    assert by_id["car"].visibility_state in {"partially_occluded", "fully_occluded"}
    assert by_id["car"].visible_fraction < 1.0
    assert by_id["bus"].depth_m is not None
    assert by_id["car"].depth_m is not None
    assert by_id["bus"].depth_m < by_id["car"].depth_m


def test_nearer_truck_occludes_motorbike_and_elevation_is_preserved() -> None:
    truck = VehicleBox(
        vehicle_id="truck",
        vehicle_type="HEAVY_TRUCK",
        front_bumper_m=(0.0, 16.0, 0.0),
        angle_degrees=0.0,
        length_m=12.0,
        width_m=2.5,
        height_m=3.8,
        ground_clearance_m=0.0,
        lane_id="inbound_0",
    )
    motorbike = VehicleBox(
        vehicle_id="motorbike",
        vehicle_type="MOTORBIKE",
        front_bumper_m=(0.0, 31.0, 1.5),
        angle_degrees=0.0,
        length_m=2.0,
        width_m=0.7,
        height_m=1.2,
        ground_clearance_m=0.12,
        lane_id="inbound_0",
    )
    records = visibility_for_frame(
        camera=_camera(),
        vehicles=(truck, motorbike),
        time_seconds=1.0,
    )
    by_id = {record.vehicle_id: record for record in records}

    assert motorbike.center_m[2] == pytest.approx(2.22)
    assert by_id["motorbike"].visible_fraction < 1.0
    assert by_id["motorbike"].visibility_state in {"partially_occluded", "fully_occluded"}


def test_geometry_camera_handles_out_of_fov_and_deterministic_ties() -> None:
    records = visibility_for_frame(
        camera=_camera(),
        vehicles=(
            _vehicle("z_car", front_y=28.0),
            _vehicle("a_car", front_y=28.0),
            _vehicle("far", front_y=28.0, x=200.0),
        ),
        time_seconds=1.0,
    )
    by_id = {record.vehicle_id: record for record in records}

    assert by_id["a_car"].visible_fraction > 0.99
    assert by_id["z_car"].visibility_state == "fully_occluded"
    assert by_id["far"].visibility_state == "out_of_fov"


def test_camera_calibration_round_trip_and_trace_contract(tmp_path) -> None:
    camera = _camera()
    path = tmp_path / "camera_calibration.v1.json"
    write_camera_calibrations((camera,), path)

    loaded = load_camera_calibrations(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "camera_calibration.v1"
    assert loaded == (camera,)

    trace_frame = {
        "schema_version": "vehicle_trace.v2",
        "time_seconds": 1.0,
        "vehicles": [
            {
                "vehicle_id": "car",
                "vehicle_type": "PRIVATE_CAR",
                "x": 0.0,
                "y": 28.0,
                "angle": 0.0,
                "lane_id": "inbound_0",
                "road_id": "edge_inbound",
                "length_m": 4.5,
                "width_m": 1.8,
                "height_m": 1.5,
                "ground_clearance_m": 0.0,
                "elevation_m": 0.0,
                "reference_point": "front_bumper_center",
            }
        ],
    }
    records = visibility_from_trace_frames(frames=(trace_frame,), cameras=loaded)
    assert records[0].visibility_state == "visible"

    trace_frame["schema_version"] = "simulation_trace_frame.v1"
    with pytest.raises(GeometryContractError, match="vehicle_trace.v2"):
        visibility_from_trace_frames(frames=(trace_frame,), cameras=loaded)


def test_observation_adapter_never_counts_a_fully_hidden_vehicle() -> None:
    records = visibility_for_frame(
        camera=_camera(),
        vehicles=(
            _vehicle("bus", front_y=16.0, width_m=3.0, height_m=4.0, length_m=12.0),
            _vehicle("car", front_y=31.0),
        ),
        time_seconds=1.0,
    )
    adapter = GeometryObservationAdapter(
        sensor_id="CAM_GOLDEN",
        lane_to_approach={"inbound_0": "north"},
    )

    observation = adapter.observe(timestamp_seconds=1.0, records=records)

    assert observation.sensor_mode == "geometry_visibility"
    assert observation.estimated_count_by_approach["north"] == 1
    assert observation.class_mix_by_approach["north"] == {"BUS": 1}
    assert observation.detector_unknown_count_by_approach["north"] == 0


def test_geometry_camera_cli_writes_visibility_and_summary_artifacts(tmp_path: Path) -> None:
    calibration_path = tmp_path / "camera_calibration.v1.json"
    trace_path = tmp_path / "trace.jsonl"
    visibility_path = tmp_path / "visibility_trace.v1.jsonl"
    observation_path = tmp_path / "sensor_observation.v1.jsonl"
    summary_path = tmp_path / "summary.json"
    lane_map_path = tmp_path / "lanes.json"
    write_camera_calibrations((_camera(),), calibration_path)
    trace_path.write_text(
        json.dumps(
            {
                "schema_version": "vehicle_trace.v2",
                "time_seconds": 1.0,
                "vehicles": [
                    {
                        "vehicle_id": "car",
                        "vehicle_type": "PRIVATE_CAR",
                        "x": 0.0,
                        "y": 28.0,
                        "angle": 0.0,
                        "lane_id": "inbound_0",
                        "road_id": "edge_inbound",
                        "length_m": 4.5,
                        "width_m": 1.8,
                        "height_m": 1.5,
                        "ground_clearance_m": 0.0,
                        "elevation_m": 0.0,
                        "reference_point": "front_bumper_center",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lane_map_path.write_text(json.dumps({"inbound_0": "north"}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "sensors" / "run_geometry_camera.py"),
            "--trace",
            str(trace_path),
            "--camera-calibration",
            str(calibration_path),
            "--output",
            str(visibility_path),
            "--lane-to-approach",
            str(lane_map_path),
            "--observation-output",
            str(observation_path),
            "--summary-out",
            str(summary_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(summary_path.read_text(encoding="utf-8"))["visibility_record_count"] == 1
    assert json.loads(visibility_path.read_text(encoding="utf-8"))["visibility_state"] == "visible"
    assert (
        json.loads(observation_path.read_text(encoding="utf-8"))["sensor_mode"]
        == "geometry_visibility"
    )
