from __future__ import annotations

from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.cli import main
from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


def test_simulate_reference_validation_backend_still_writes_aggregate_trace(
    tmp_path: Path,
) -> None:
    out = tmp_path / "result.json"
    trace = tmp_path / "trace.jsonl"

    exit_code = main(
        [
            "run",
            "--engine",
            "reference",
            "--spec",
            str(SPEC_PATH),
            "--scenario",
            "normal_weekday",
            "--controller",
            "fixed_time",
            "--out",
            str(out),
            "--trace-out",
            str(trace),
        ]
    )

    assert exit_code == 0
    assert out.is_file()
    assert trace.is_file()
    assert trace.read_text(encoding="utf-8").strip()


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO/netconvert runtime is not available")
def test_simulate_run_sumo_writes_real_vehicle_trace_and_keeps_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    trace = tmp_path / "trace.jsonl"
    work_dir = tmp_path / "sumo_artifacts"

    exit_code = main(
        [
            "run",
            "--spec",
            str(SPEC_PATH),
            "--scenario",
            "normal_weekday",
            "--controller",
            "fixed_time",
            "--out",
            str(out),
            "--trace-out",
            str(trace),
            "--sumo-work-dir",
            str(work_dir),
        ]
    )

    assert exit_code == 0
    assert out.is_file()
    assert trace.is_file()
    assert (work_dir / "normal_weekday" / "fixed_time" / "fcd.xml").is_file()
    assert '"engine_id": "sumo"' in trace.read_text(encoding="utf-8")
