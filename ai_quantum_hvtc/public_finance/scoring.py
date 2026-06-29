from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ai_quantum_hvtc.simulation.domain import DistrictSpec, InvestmentCandidate
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult


@dataclass(frozen=True)
class CandidateScore:
    scenario_id: str
    controller_id: str
    candidate_id: str
    intersection_id: str
    upgrade_type: str
    delay_saved_seconds: float
    emergency_delay_saved_seconds: float
    bus_passenger_delay_saved_seconds: float
    truck_delay_saved_seconds: float
    public_value_vnd: float
    capex_vnd: float
    annual_maintenance_vnd: float
    net_public_value_vnd: float
    benefit_cost_ratio: float
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _metric_for(result: SimulationResult, intersection_id: str) -> IntersectionMetric:
    return result.intersections.get(intersection_id, IntersectionMetric(intersection_id))


def _score_candidate(
    spec: DistrictSpec,
    baseline: SimulationResult,
    alternative: SimulationResult,
    candidate: InvestmentCandidate,
) -> CandidateScore:
    finance = spec.finance_assumptions
    base = _metric_for(baseline, candidate.intersection_id)
    alt = _metric_for(alternative, candidate.intersection_id)

    delay_saved_seconds = max(0.0, base.delay_seconds - alt.delay_seconds)
    emergency_saved_seconds = max(0.0, base.emergency_delay_seconds - alt.emergency_delay_seconds)
    bus_saved_seconds = max(
        0.0,
        base.bus_passenger_delay_seconds - alt.bus_passenger_delay_seconds,
    )
    truck_saved_seconds = max(0.0, base.truck_delay_seconds - alt.truck_delay_seconds)

    delay_saved_hours = delay_saved_seconds / 3600.0
    emergency_saved_hours = emergency_saved_seconds / 3600.0
    bus_saved_hours = bus_saved_seconds / 3600.0
    truck_saved_hours = truck_saved_seconds / 3600.0

    public_value = (
        delay_saved_hours * finance.value_of_time_vnd_per_hour
        + bus_saved_hours
        * finance.value_of_time_vnd_per_hour
        * finance.bus_passenger_value_multiplier
        + emergency_saved_hours * finance.emergency_delay_value_vnd_per_hour
        + truck_saved_hours * finance.logistics_delay_value_vnd_per_truck_hour
        + delay_saved_hours * finance.fuel_emission_saving_vnd_per_delay_hour
    )
    total_cost = (
        candidate.capex_vnd + candidate.annual_maintenance_vnd + finance.deployment_risk_penalty_vnd
    )
    net_value = public_value - total_cost
    benefit_cost_ratio = public_value / total_cost if total_cost > 0 else 0.0

    return CandidateScore(
        scenario_id=alternative.scenario_id,
        controller_id=alternative.controller_id,
        candidate_id=candidate.candidate_id,
        intersection_id=candidate.intersection_id,
        upgrade_type=candidate.upgrade_type,
        delay_saved_seconds=round(delay_saved_seconds, 3),
        emergency_delay_saved_seconds=round(emergency_saved_seconds, 3),
        bus_passenger_delay_saved_seconds=round(bus_saved_seconds, 3),
        truck_delay_saved_seconds=round(truck_saved_seconds, 3),
        public_value_vnd=round(public_value, 3),
        capex_vnd=round(candidate.capex_vnd, 3),
        annual_maintenance_vnd=round(candidate.annual_maintenance_vnd, 3),
        net_public_value_vnd=round(net_value, 3),
        benefit_cost_ratio=round(benefit_cost_ratio, 6),
        caveat=candidate.caveat,
    )


def score_candidates(
    spec: DistrictSpec,
    baseline: SimulationResult,
    alternative: SimulationResult,
) -> list[CandidateScore]:
    return [
        _score_candidate(spec, baseline, alternative, candidate)
        for candidate in spec.investment_candidates.values()
    ]
