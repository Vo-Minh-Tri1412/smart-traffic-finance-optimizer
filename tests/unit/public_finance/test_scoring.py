from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ai_quantum_hvtc.public_finance import score_candidates
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_public_finance_scores_candidates_from_simulation_results() -> None:
    spec = load_district_spec(SPEC_PATH)
    baseline_intersections = {
        intersection_id: IntersectionMetric(intersection_id=intersection_id)
        for intersection_id in spec.intersections
    }
    baseline_intersections["I06"] = IntersectionMetric(
        intersection_id="I06",
        delay_seconds=500.0,
        emergency_delay_seconds=300.0,
        bus_passenger_delay_seconds=120.0,
    )
    alternative_intersections = {
        intersection_id: IntersectionMetric(intersection_id=intersection_id)
        for intersection_id in spec.intersections
    }
    alternative_intersections["I06"] = IntersectionMetric(
        intersection_id="I06",
        delay_seconds=200.0,
        emergency_delay_seconds=80.0,
        bus_passenger_delay_seconds=40.0,
    )
    baseline = SimulationResult(
        scenario_id="hospital_emergency",
        controller_id="fixed_time",
        seed=42,
        engine_id="sumo_fixture",
        total_vehicles=100,
        throughput=95,
        total_waiting_time_seconds=1200.0,
        average_waiting_time_seconds=12.0,
        max_queue_vehicles=8.0,
        average_queue_vehicles=3.0,
        stopped_vehicles=30,
        emergency_delay_seconds=300.0,
        bus_passenger_delay_seconds=600.0,
        truck_delay_seconds=400.0,
        reroute_count=0,
        failed_route_count=0,
        intersections=baseline_intersections,
    )
    alternative = SimulationResult(
        scenario_id="hospital_emergency",
        controller_id="rule_based",
        seed=42,
        engine_id="sumo_fixture",
        total_vehicles=100,
        throughput=98,
        total_waiting_time_seconds=900.0,
        average_waiting_time_seconds=9.0,
        max_queue_vehicles=5.0,
        average_queue_vehicles=2.0,
        stopped_vehicles=18,
        emergency_delay_seconds=80.0,
        bus_passenger_delay_seconds=400.0,
        truck_delay_seconds=350.0,
        reroute_count=0,
        failed_route_count=0,
        intersections=alternative_intersections,
    )

    scores = score_candidates(spec, baseline, alternative)

    assert scores
    assert {score.candidate_id for score in scores} == set(spec.investment_candidates)
    assert any(score.emergency_delay_saved_seconds > 0 for score in scores)


def test_public_finance_rejects_unknown_metrics_and_missing_bus_intersections() -> None:
    spec = load_district_spec(SPEC_PATH)
    baseline = SimulationResult(
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        engine_id="sumo",
        total_vehicles=1,
        throughput=1,
        total_waiting_time_seconds=1.0,
        average_waiting_time_seconds=1.0,
        max_queue_vehicles=1.0,
        average_queue_vehicles=1.0,
        stopped_vehicles=1,
        emergency_delay_seconds=0.0,
        bus_passenger_delay_seconds=None,
        truck_delay_seconds=0.0,
        reroute_count=None,
        failed_route_count=None,
    )
    alternative = replace(baseline, controller_id="rule_based")

    with pytest.raises(ValueError, match="metrics are unavailable"):
        score_candidates(spec, baseline, alternative)

    baseline_with_known_counts = replace(
        baseline,
        bus_passenger_delay_seconds=0.0,
        reroute_count=0,
        failed_route_count=0,
    )
    alternative_with_known_counts = replace(baseline_with_known_counts, controller_id="rule_based")
    with pytest.raises(ValueError, match="both include intersection"):
        score_candidates(spec, baseline_with_known_counts, alternative_with_known_counts)

    missing_bus_rows = {
        intersection_id: IntersectionMetric(
            intersection_id=intersection_id,
            bus_passenger_delay_seconds=None,
        )
        for intersection_id in spec.intersections
    }
    baseline_missing_bus_rows = replace(
        baseline_with_known_counts,
        intersections=missing_bus_rows,
    )
    alternative_missing_bus_rows = replace(
        alternative_with_known_counts,
        intersections=missing_bus_rows,
    )
    with pytest.raises(ValueError, match="bus passenger delay is unavailable"):
        score_candidates(spec, baseline_missing_bus_rows, alternative_missing_bus_rows)
