from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.specs import load_district_spec
from scripts.render.godot_authoring_export import main
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable


def test_godot_authoring_export_writes_valid_district_spec_when_godot_is_available(
    tmp_path: Path,
) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")

    spec_path = tmp_path / "district_spec.generated.json"
    code = main(["--out", str(spec_path), "--godot-exe", str(godot_exe)])

    assert code == 0
    spec = load_district_spec(spec_path)
    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec.metadata.district_id == "godot_authoring_district_v1"
    assert len(spec.intersections) >= 10
    assert any(not intersection.signalized for intersection in spec.intersections.values())
    assert len(spec.roads) >= 20
    assert len(raw["investment_candidates"]) >= 3
