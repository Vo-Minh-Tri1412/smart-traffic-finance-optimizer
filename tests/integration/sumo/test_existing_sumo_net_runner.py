from __future__ import annotations

from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo import (
    SumoRuntimeConfig,
    prepare_existing_sumo_net_run,
    run_existing_sumo_net,
)
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.parser import parse_existing_sumo_net_result
from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime, run_sumo_pipeline
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO runtime is not available")
def test_existing_sumo_net_runner_reuses_net_and_routes(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    seed_paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        work_dir=tmp_path / "seed",
    )
    run_sumo_pipeline(seed_paths, SumoRuntimeConfig(), controller_id="fixed_time")

    run_paths = prepare_existing_sumo_net_run(
        net=seed_paths.net,
        routes=seed_paths.routes,
        work_dir=tmp_path / "existing",
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        horizon_seconds=600,
    )
    run_existing_sumo_net(run_paths, SumoRuntimeConfig())
    result = parse_existing_sumo_net_result(
        paths=run_paths,
        district_id="toy_public_district_v1",
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )

    assert result.engine_id == "sumo_net"
    assert result.total_vehicles > 0
    assert result.vehicle_trace_frames
    assert result.vehicle_trace_frames[0]["engine_id"] == "sumo_net"
