from __future__ import annotations

from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo import SumoAdapter
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.profiles import GEOMETRY_SENSOR_SUMO_PROFILE
from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_sumo_exporter_writes_xml_artifacts(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)

    paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        work_dir=tmp_path,
    )

    assert paths.nodes.is_file()
    assert paths.edges.is_file()
    assert paths.additional.is_file()
    assert paths.routes.is_file()
    assert paths.config.is_file()
    assert paths.edge_data.name == "edge_data.xml"
    assert paths.fcd.name == "fcd.xml"
    assert paths.controller_log.name == "controller_interventions.jsonl"


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO/netconvert runtime is not available")
def test_sumo_adapter_runs_when_runtime_is_available(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)

    result = SumoAdapter(work_dir=tmp_path).run(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )

    assert result.engine_id == "sumo"
    assert result.total_vehicles >= 0
    assert result.max_queue_vehicles > 0
    assert any(metric.delay_seconds > 0 for metric in result.intersections.values())
    assert result.vehicle_trace_frames
    assert result.vehicle_trace_frames[0]["schema_version"] == "vehicle_trace.v2"
    assert "vehicles" in result.vehicle_trace_frames[0]


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO/netconvert runtime is not available")
def test_sumo_rule_based_controller_runs_and_writes_controller_log(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)

    result = SumoAdapter(work_dir=tmp_path).run(
        spec=spec,
        scenario_id="hospital_emergency",
        controller_id="rule_based",
        seed=42,
    )

    assert result.engine_id == "sumo"
    assert result.controller_id == "rule_based"
    assert result.total_vehicles > 0
    assert result.controller_interventions >= 0
    assert (tmp_path / "controller_interventions.jsonl").is_file()


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO/netconvert runtime is not available")
def test_sumo_geometry_sensor_profile_emits_geometry_ready_trace(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)

    result = SumoAdapter(
        work_dir=tmp_path,
        simulation_profile=GEOMETRY_SENSOR_SUMO_PROFILE,
    ).run(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )

    vehicle = next(
        vehicle
        for frame in result.vehicle_trace_frames
        for vehicle in frame["vehicles"]
        if vehicle.get("vehicle_type")
    )
    assert result.vehicle_trace_frames[0]["schema_version"] == "vehicle_trace.v2"
    assert vehicle["reference_point"] == "front_bumper_center"
    assert vehicle["height_m"] > 0
    assert "pos_lat_m" in vehicle


def test_sumo_rl_policy_placeholder_fails_clearly(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)

    with pytest.raises(SumoRuntimeError, match="RL training/evaluation is not implemented yet"):
        SumoAdapter(work_dir=tmp_path).run(
            spec=spec,
            scenario_id="normal_weekday",
            controller_id="rl_policy",
            seed=42,
        )
