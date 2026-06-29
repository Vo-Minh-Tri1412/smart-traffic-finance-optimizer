from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.public_finance import score_candidates
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")


def test_public_finance_scores_candidates_from_simulation_results() -> None:
    spec = load_district_spec(SPEC_PATH)
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
        intersections={
            "I06": IntersectionMetric(
                intersection_id="I06",
                delay_seconds=500.0,
                emergency_delay_seconds=300.0,
                bus_passenger_delay_seconds=120.0,
            )
        },
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
        intersections={
            "I06": IntersectionMetric(
                intersection_id="I06",
                delay_seconds=200.0,
                emergency_delay_seconds=80.0,
                bus_passenger_delay_seconds=40.0,
            )
        },
    )

    scores = score_candidates(spec, baseline, alternative)

    assert scores
    assert {score.candidate_id for score in scores} == set(spec.investment_candidates)
    assert any(score.emergency_delay_saved_seconds > 0 for score in scores)
