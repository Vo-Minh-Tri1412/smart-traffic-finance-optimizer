from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime
from scripts.render.godot_authoring_roundtrip_smoke import main
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable


def test_godot_authoring_roundtrip_runs_when_godot_and_sumo_are_available(
    tmp_path: Path,
) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")
    if not has_sumo_runtime():
        pytest.skip("SUMO/netconvert runtime is not available")

    output_root = tmp_path / "roundtrip"
    code = main(
        [
            "--output-root",
            str(output_root),
            "--max-frames",
            "30",
            "--godot-exe",
            str(godot_exe),
        ]
    )

    summary_path = output_root / "roundtrip_summary.json"
    assert code == 0
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["lane_count"] > 0
    assert summary["spawned_vehicle_count"] > 0
    assert summary["off_lane_vehicle_count"] == 0
