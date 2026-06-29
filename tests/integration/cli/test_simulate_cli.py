from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.simulation.cli import main

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


def test_simulate_run_writes_result_and_frontend_trace(tmp_path: Path) -> None:
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
