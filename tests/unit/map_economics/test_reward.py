from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.map_economics import (
    TripEconomicContext,
    build_map_economic_reward,
    load_map_economic_profile,
    map_economic_profile_from_mapping,
)

TEMPLATE = Path("data/catalog/map_economic_profile.v1.template.json")


def test_reward_keeps_raw_vnd_ledger_separate_from_scaled_reward() -> None:
    reward = build_map_economic_reward(load_map_economic_profile(TEMPLATE))

    result = reward.evaluate_trip_delay_delta(
        delay_delta_seconds=3600,
        context=TripEconomicContext(od_pair_id="OD_A_B", trip_id="trip-1"),
    )

    assert result.raw_public_cost.estimate == pytest.approx(1.0)
    assert result.raw_public_cost.unit == "VND"
    assert result.normalized_unclipped == pytest.approx(-1.0)
    assert result.reward == pytest.approx(-1.0)
    assert result.resolution_level == "od_pair"
    assert result.matched_id == "OD_A_B"
    assert result.contains_assumptions
    assert result.evidence_grades == ("D",)


def test_negative_increment_is_saved_delay_and_reward_is_clipped() -> None:
    reward = build_map_economic_reward(load_map_economic_profile(TEMPLATE))

    saving = reward.evaluate_trip_delay_delta(
        delay_delta_seconds=-3600,
        context=TripEconomicContext(od_pair_id="OD_A_B"),
    )
    large_cost = reward.evaluate_trip_delay_delta(
        delay_delta_seconds=3600 * 100,
        context=TripEconomicContext(od_pair_id="OD_A_B"),
    )

    assert saving.raw_public_cost.estimate == pytest.approx(-1.0)
    assert saving.reward == pytest.approx(1.0)
    assert large_cost.normalized_unclipped == pytest.approx(-100.0)
    assert large_cost.reward == -10.0


def test_reliability_value_requires_a_separate_measured_delta() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    od_valuation = next(item for item in data["valuations"] if item["valuation_id"] == "VAL_OD_A_B")
    od_valuation["reliability_value"].update(estimate=1, lower=1, upper=1)
    reward = build_map_economic_reward(map_economic_profile_from_mapping(data))

    delay_only = reward.evaluate_trip_delay_delta(
        delay_delta_seconds=3600,
        context=TripEconomicContext(od_pair_id="OD_A_B"),
    )
    with_reliability = reward.evaluate_trip_delay_delta(
        delay_delta_seconds=3600,
        reliability_delta_seconds=3600,
        context=TripEconomicContext(od_pair_id="OD_A_B"),
    )

    assert delay_only.raw_public_cost.estimate == pytest.approx(1.0)
    assert with_reliability.raw_public_cost.estimate == pytest.approx(2.0)


def test_reward_rejects_cumulative_or_invalid_values_only_by_explicit_delta_contract() -> None:
    reward = build_map_economic_reward(load_map_economic_profile(TEMPLATE))

    with pytest.raises(ValueError, match="finite"):
        reward.evaluate_trip_delay_delta(
            delay_delta_seconds=float("nan"), context=TripEconomicContext()
        )
    with pytest.raises(ValueError, match="> 0"):
        reward.evaluate_trip_delay_delta(
            delay_delta_seconds=1.0,
            context=TripEconomicContext(),
            persons_per_trip=0,
        )
