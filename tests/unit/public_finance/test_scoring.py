from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.public_finance import score_candidates
from ai_quantum_hvtc.simulation.engines import ReferenceGraphEngine
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


def test_public_finance_scores_candidates_from_simulation_results() -> None:
    spec = load_district_spec(SPEC_PATH)
    engine = ReferenceGraphEngine()
    baseline = engine.run(
        spec=spec,
        scenario_id="hospital_emergency",
        controller_id="fixed_time",
        seed=42,
    )
    alternative = engine.run(
        spec=spec,
        scenario_id="hospital_emergency",
        controller_id="rule_based",
        seed=42,
    )

    scores = score_candidates(spec, baseline, alternative)

    assert scores
    assert {score.candidate_id for score in scores} == set(spec.investment_candidates)
    assert any(score.emergency_delay_saved_seconds > 0 for score in scores)
