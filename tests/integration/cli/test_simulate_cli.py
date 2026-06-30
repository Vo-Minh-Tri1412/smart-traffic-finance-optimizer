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


def test_simulate_compare_baselines_writes_csv_and_markdown(tmp_path: Path) -> None:
    out = tmp_path / "baseline.csv"
    report = tmp_path / "baseline.md"

    exit_code = main(
        [
            "compare-baselines",
            "--engine",
            "reference",
            "--spec",
            str(SPEC_PATH),
            "--scenario",
            "normal_weekday",
            "--controllers",
            "fixed_time,rule_based",
            "--out",
            str(out),
            "--report",
            str(report),
        ]
    )

    assert exit_code == 0
    assert out.is_file()
    assert report.is_file()
    assert "waiting_time_saved_vs_fixed_seconds" in out.read_text(encoding="utf-8")
    assert "Báo cáo baseline: normal_weekday" in report.read_text(encoding="utf-8")


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
    assert '"schema_version": "simulation_trace_frame.v1"' in trace.read_text(encoding="utf-8")
