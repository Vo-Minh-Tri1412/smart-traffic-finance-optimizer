from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime
from scripts.render.godot_sumo_trace_replay_smoke import main
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable

TRACE_PATH = Path("frontend/mock-data/sample_vehicle_simulation_trace.jsonl")
SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_godot_sumo_trace_replay_smoke_runs_when_godot_is_available(tmp_path: Path) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")

    output_root = tmp_path / "godot_replay"
    code = main(
        [
            "--trace",
            str(TRACE_PATH),
            "--spec",
            str(SPEC_PATH),
            "--output-root",
            str(output_root),
            "--max-frames",
            "2",
            "--godot-exe",
            str(godot_exe),
        ]
    )

    summary_path = output_root / "replay_summary.json"
    assert code == 0
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["loaded_frames"] == 2
    assert summary["spawned_vehicle_count"] >= 2
    assert summary["parse_error_count"] == 0
    assert summary["vehicle_asset_registry_loaded"] is True
    assert summary["vehicle_scene_count"] >= 5
    assert summary["trace_data_model"] == "TraceFrameData/TraceVehicleState"
    assert summary["trace_schema_version"] == "simulation_trace_frame.v1"
    assert summary["playback_data_model"] == "TracePlaybackClock/TraceInterpolator"
    assert summary["interpolated_frame_count"] >= 1
    assert summary["vehicle_pool_model"] == "VehiclePool"
    assert summary["vehicle_pool_created_count"] >= 1


def test_godot_sumo_trace_replay_generates_sumo_net_geometry_when_trace_is_omitted(
    tmp_path: Path,
) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")
    if not has_sumo_runtime():
        pytest.skip("SUMO/netconvert runtime is not available")

    output_root = tmp_path / "godot_replay"
    code = main(
        [
            "--spec",
            str(SPEC_PATH),
            "--output-root",
            str(output_root),
            "--max-frames",
            "10",
            "--godot-exe",
            str(godot_exe),
        ]
    )

    summary = json.loads((output_root / "replay_summary.json").read_text(encoding="utf-8"))
    assert code == 0
    assert summary["lane_count"] > 0
    assert summary["off_lane_vehicle_count"] == 0
    assert summary["vehicle_asset_registry_loaded"] is True
    assert summary["vehicle_fallback_spawn_count"] == 0
    assert summary["sumo_geometry_data_model"] == "SumoNetGeometryData"
    assert summary["playback_data_model"] == "TracePlaybackClock/TraceInterpolator"
    assert summary["vehicle_pool_model"] == "VehiclePool"


def test_godot_replay_vehicle_pool_reuses_released_vehicle_nodes(tmp_path: Path) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")

    trace = tmp_path / "pool_trace.jsonl"
    rows = [
        {
            "schema_version": "simulation_trace_frame.v1",
            "timestep": 0,
            "time_seconds": 0.0,
            "district_id": "pool_test",
            "scenario_id": "pool_reuse",
            "controller_id": "fixed_time",
            "engine_id": "sumo",
            "vehicles": [
                {
                    "vehicle_id": "car.0",
                    "vehicle_type": "PRIVATE_CAR",
                    "x": 0.0,
                    "y": 0.0,
                    "speed": 1.0,
                    "angle": 90.0,
                    "lane_id": "R01_0",
                    "road_id": "R01",
                }
            ],
        },
        {
            "schema_version": "simulation_trace_frame.v1",
            "timestep": 1,
            "time_seconds": 1.0,
            "district_id": "pool_test",
            "scenario_id": "pool_reuse",
            "controller_id": "fixed_time",
            "engine_id": "sumo",
            "vehicles": [],
        },
        {
            "schema_version": "simulation_trace_frame.v1",
            "timestep": 2,
            "time_seconds": 2.0,
            "district_id": "pool_test",
            "scenario_id": "pool_reuse",
            "controller_id": "fixed_time",
            "engine_id": "sumo",
            "vehicles": [],
        },
        {
            "schema_version": "simulation_trace_frame.v1",
            "timestep": 3,
            "time_seconds": 3.0,
            "district_id": "pool_test",
            "scenario_id": "pool_reuse",
            "controller_id": "fixed_time",
            "engine_id": "sumo",
            "vehicles": [
                {
                    "vehicle_id": "car.1",
                    "vehicle_type": "PRIVATE_CAR",
                    "x": 15.0,
                    "y": 0.0,
                    "speed": 1.0,
                    "angle": 90.0,
                    "lane_id": "R01_0",
                    "road_id": "R01",
                }
            ],
        },
    ]
    trace.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    output_root = tmp_path / "godot_replay"
    code = main(
        [
            "--trace",
            str(trace),
            "--spec",
            str(SPEC_PATH),
            "--output-root",
            str(output_root),
            "--max-frames",
            "4",
            "--godot-exe",
            str(godot_exe),
        ]
    )

    summary = json.loads((output_root / "replay_summary.json").read_text(encoding="utf-8"))
    assert code == 0
    assert summary["vehicle_pool_model"] == "VehiclePool"
    assert summary["vehicle_pool_released_count"] >= 1
    assert summary["vehicle_pool_reused_count"] >= 1
    assert summary["vehicle_pool_created_count"] == 1
