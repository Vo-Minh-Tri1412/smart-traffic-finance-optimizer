"""The uncalibrated baseline must not hide a policy premium in RL alone."""

import json
from pathlib import Path


def test_retained_roi_baseline_uses_neutral_unsourced_multipliers() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "configs/economics/district7_map_economic_assumptions.v1.example.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["metadata"]["map_scope_status"] == "reviewed_roi"
    assert payload["metadata"]["status"] == "draft"
    for valuation in payload["valuations"]:
        for key in ("essential_service_multiplier", "economic_flow_multiplier"):
            record = valuation[key]
            assert record["estimate"] == record["lower"] == record["upper"] == 1.0
            assert record["is_assumption"] is True
            assert record["evidence_grade"] == "D"
