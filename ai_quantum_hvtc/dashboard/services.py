from __future__ import annotations

import shutil
import threading
from dataclasses import asdict
from pathlib import Path

from ai_quantum_hvtc.policy import InvestmentOption, optimize_exact, optimize_greedy, qubo_matrix
from ai_quantum_hvtc.public_finance import CandidateScore, score_candidates
from ai_quantum_hvtc.reports import baseline_comparison_rows
from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.engines import ReferenceGraphEngine, SimulationEngine, SumoAdapter
from ai_quantum_hvtc.simulation.metrics import SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec

from .store import RunStore, RunStoreError, StoredRunMeta


class DashboardServiceError(Exception):
    pass


class SpecCache:
    """Loads and caches the district spec used by the dashboard."""

    def __init__(self, spec_path: Path) -> None:
        self._spec_path = spec_path
        self._lock = threading.Lock()
        self._spec: DistrictSpec | None = None

    @property
    def spec_path(self) -> Path:
        return self._spec_path

    def get(self) -> DistrictSpec:
        with self._lock:
            if self._spec is None:
                self._spec = load_district_spec(self._spec_path)
            return self._spec


def sumo_available() -> tuple[bool, str]:
    binary = shutil.which("sumo")
    if binary is None:
        return False, "sumo binary not found on PATH"
    return True, binary


def build_engine(engine_id: str, *, work_dir: Path | None = None) -> SimulationEngine:
    if engine_id == "reference":
        return ReferenceGraphEngine()
    if engine_id == "sumo":
        return SumoAdapter(work_dir=work_dir)
    raise DashboardServiceError(f"unknown engine: {engine_id}")


def run_simulation(
    *,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    engine_id: str,
    seed: int,
    sumo_work_dir: Path | None = None,
) -> SimulationResult:
    if scenario_id not in spec.scenarios:
        raise DashboardServiceError(f"unknown scenario: {scenario_id}")
    if controller_id not in spec.controllers:
        raise DashboardServiceError(f"unknown controller: {controller_id}")
    engine = build_engine(engine_id, work_dir=sumo_work_dir)
    return engine.run(
        spec=spec,
        scenario_id=scenario_id,
        controller_id=controller_id,
        seed=seed,
    )


def seed_demo_runs(
    *,
    store: RunStore,
    spec_cache: SpecCache,
    scenarios: tuple[str, ...],
    controllers: tuple[str, ...],
    seed: int = 42,
) -> list[StoredRunMeta]:
    """Populate an empty store with fast reference-engine demo runs."""

    if store.list_runs():
        return []
    spec = spec_cache.get()
    created: list[StoredRunMeta] = []
    for scenario_id in scenarios:
        if scenario_id not in spec.scenarios:
            continue
        for controller_id in controllers:
            if controller_id not in spec.controllers:
                continue
            try:
                result = run_simulation(
                    spec=spec,
                    scenario_id=scenario_id,
                    controller_id=controller_id,
                    engine_id="reference",
                    seed=seed,
                )
            except Exception:  # noqa: BLE001 - demo seeding must never kill startup
                continue
            created.append(
                store.save_run(
                    result=result,
                    spec=spec,
                    district_id=spec.metadata.district_id,
                    label="demo seed",
                )
            )
    return created


def compare_controllers(
    *,
    store: RunStore,
    scenario_id: str,
    engine_id: str,
) -> tuple[str, list[dict[str, object]]]:
    """Build baseline comparison rows from the latest stored run per controller."""

    latest = store.latest_by_controller(scenario_id=scenario_id, engine_id=engine_id)
    if not latest:
        raise RunStoreError(f"no runs stored for scenario {scenario_id} ({engine_id})")
    if "fixed_time" not in latest:
        raise RunStoreError(
            f"scenario {scenario_id} ({engine_id}) has no fixed_time baseline run yet"
        )
    ordered_controllers = ["fixed_time"] + sorted(
        controller_id for controller_id in latest if controller_id != "fixed_time"
    )
    results: list[SimulationResult] = [
        store.load_result(latest[controller_id].run_id) for controller_id in ordered_controllers
    ]
    rows = baseline_comparison_rows(results)
    return "fixed_time", [dict(row) for row in rows]


def score_investments(
    *,
    store: RunStore,
    spec: DistrictSpec,
    scenario_id: str,
    controller_id: str,
    engine_id: str,
) -> list[CandidateScore]:
    latest = store.latest_by_controller(scenario_id=scenario_id, engine_id=engine_id)
    baseline_meta = latest.get("fixed_time")
    alternative_meta = latest.get(controller_id)
    if baseline_meta is None:
        raise RunStoreError(
            f"scenario {scenario_id} ({engine_id}) has no fixed_time baseline run yet"
        )
    if alternative_meta is None:
        raise RunStoreError(f"scenario {scenario_id} ({engine_id}) has no {controller_id} run yet")
    baseline = store.load_result(baseline_meta.run_id)
    alternative = store.load_result(alternative_meta.run_id)
    return score_candidates(spec, baseline, alternative)


def optimize_budget(
    *,
    scores: list[CandidateScore],
    budget_vnd: float,
    algorithm: str,
    include_qubo: bool,
) -> tuple[list[InvestmentOption], dict[str, dict[str, float]] | None]:
    options = [
        InvestmentOption(
            candidate_id=score.candidate_id,
            cost_vnd=score.capex_vnd + score.annual_maintenance_vnd,
            value_vnd=score.net_public_value_vnd,
            source_row={key: str(value) for key, value in asdict(score).items()},
        )
        for score in scores
    ]
    if algorithm == "exact":
        selected = optimize_exact(options, budget_vnd)
    elif algorithm == "greedy":
        selected = optimize_greedy(options, budget_vnd)
    else:
        raise DashboardServiceError(f"unknown optimizer algorithm: {algorithm}")
    qubo = qubo_matrix(options, budget_vnd=budget_vnd) if include_qubo else None
    return selected, qubo


def district_payload(spec: DistrictSpec) -> dict[str, object]:
    """Serialize the district spec into the dashboard API shape."""

    return {
        "metadata": {
            "id": spec.metadata.district_id,
            "name": spec.metadata.name,
            "version": spec.metadata.version,
            "horizon_seconds": spec.metadata.horizon_seconds,
            "time_step_seconds": spec.metadata.time_step_seconds,
        },
        "zones": [
            {
                "id": zone.zone_id,
                "name": zone.name,
                "type": zone.zone_type,
                "intersection_ids": list(zone.intersection_ids),
                "economic_role": zone.economic_role,
                "peak_windows": list(zone.peak_windows),
            }
            for zone in spec.zones.values()
        ],
        "intersections": [
            {
                "id": item.intersection_id,
                "name": item.name,
                "x": item.x,
                "y": item.y,
                "tags": list(item.tags),
                "signalized": item.signalized,
            }
            for item in spec.intersections.values()
        ],
        "roads": [
            {
                "id": road.road_id,
                "from": road.from_intersection,
                "to": road.to_intersection,
                "length_km": road.length_km,
                "speed_kph": road.speed_kph,
                "lanes": road.lanes,
                "capacity": road.capacity,
                "tags": list(road.tags),
                "truck_allowed": road.truck_allowed,
            }
            for road in spec.roads.values()
        ],
        "vehicle_types": [
            {
                "id": vehicle.vehicle_type_id,
                "passenger_count": vehicle.passenger_count,
                "pcu": vehicle.pcu,
                "value_class": vehicle.value_class,
                "priority_level": vehicle.priority_level,
            }
            for vehicle in spec.vehicle_types.values()
        ],
        "flows": [
            {
                "id": flow.flow_id,
                "origin_zone": flow.origin_zone,
                "destination_zone": flow.destination_zone,
                "trip_purpose": flow.trip_purpose,
                "departure_start": flow.departure_start,
                "departure_end": flow.departure_end,
                "base_volume": flow.base_volume,
                "vehicle_mix": dict(flow.vehicle_mix),
                "route_policy": flow.route_policy,
            }
            for flow in spec.flows.values()
        ],
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "flow_multipliers": dict(scenario.flow_multipliers),
                "road_capacity_multipliers": dict(scenario.road_capacity_multipliers),
                "closed_roads": list(scenario.closed_roads),
            }
            for scenario in spec.scenarios.values()
        ],
        "controllers": [
            {
                "id": controller.controller_id,
                "name": controller.name,
                "type": controller.controller_type,
            }
            for controller in spec.controllers.values()
        ],
        "investment_candidates": [
            {
                "id": candidate.candidate_id,
                "intersection_id": candidate.intersection_id,
                "upgrade_type": candidate.upgrade_type,
                "capex_vnd": candidate.capex_vnd,
                "annual_maintenance_vnd": candidate.annual_maintenance_vnd,
                "affected_flow_ids": list(candidate.affected_flow_ids),
                "caveat": candidate.caveat,
            }
            for candidate in spec.investment_candidates.values()
        ],
        "finance_assumptions": {
            "value_of_time_vnd_per_hour": spec.finance_assumptions.value_of_time_vnd_per_hour,
            "bus_passenger_value_multiplier": (
                spec.finance_assumptions.bus_passenger_value_multiplier
            ),
            "emergency_delay_value_vnd_per_hour": (
                spec.finance_assumptions.emergency_delay_value_vnd_per_hour
            ),
            "logistics_delay_value_vnd_per_truck_hour": (
                spec.finance_assumptions.logistics_delay_value_vnd_per_truck_hour
            ),
            "fuel_emission_saving_vnd_per_delay_hour": (
                spec.finance_assumptions.fuel_emission_saving_vnd_per_delay_hour
            ),
            "deployment_risk_penalty_vnd": spec.finance_assumptions.deployment_risk_penalty_vnd,
            "status": dict(spec.finance_assumptions.assumption_status),
        },
    }
