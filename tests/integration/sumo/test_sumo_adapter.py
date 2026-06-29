from __future__ import annotations

from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo import SumoAdapter
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


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
    assert paths.routes.is_file()
    assert paths.config.is_file()


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
