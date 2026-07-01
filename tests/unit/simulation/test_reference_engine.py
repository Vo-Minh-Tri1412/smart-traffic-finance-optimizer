from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.simulation.engines import ReferenceGraphEngine
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_reference_engine_is_deterministic_for_seed() -> None:
    spec = load_district_spec(SPEC_PATH)
    engine = ReferenceGraphEngine()

    first = engine.run(
        spec=spec,
        scenario_id="industrial_shift_in",
        controller_id="rule_based",
        seed=7,
    )
    second = engine.run(
        spec=spec,
        scenario_id="industrial_shift_in",
        controller_id="rule_based",
        seed=7,
    )

    assert first.to_dict() == second.to_dict()
    assert first.total_vehicles > 0
    assert first.max_queue_vehicles > 0


def test_rule_based_reduces_emergency_delay_against_fixed_time() -> None:
    spec = load_district_spec(SPEC_PATH)
    engine = ReferenceGraphEngine()

    fixed = engine.run(
        spec=spec,
        scenario_id="hospital_emergency",
        controller_id="fixed_time",
        seed=42,
    )
    rule_based = engine.run(
        spec=spec,
        scenario_id="hospital_emergency",
        controller_id="rule_based",
        seed=42,
    )

    assert fixed.emergency_delay_seconds > 0
    assert rule_based.emergency_delay_seconds < fixed.emergency_delay_seconds
