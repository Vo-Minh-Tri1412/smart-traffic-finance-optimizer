from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render.godot_sumo_trace_replay_smoke import main
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable

TRACE_PATH = Path("frontend/mock-data/sample_vehicle_simulation_trace.jsonl")
SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


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
