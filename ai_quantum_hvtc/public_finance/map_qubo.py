"""Map-aware public-investment QUBO construction and small exact verification.

This module consumes the evidence-bearing ``map_economic_profile.v1`` contract.  It
does not estimate economic values from building labels, vehicle classes, or gross
trip value.  Every benefit entering the objective must be a marginal, OD-specific
impact supplied by the profile.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any, Literal, cast

MAP_ECONOMIC_PROFILE_VERSION = "map_economic_profile.v1"
MAP_AWARE_QUBO_MODEL_VERSION = "map_aware_qubo.v1"
MAP_AWARE_QUBO_RUN_VERSION = "map_aware_qubo_run.v1"

RiskMode = Literal["estimate", "conservative", "optimistic"]
ValueRole = Literal["benefit", "cost"]


class MapQuboValidationError(ValueError):
    """Raised when economic evidence cannot safely define a QUBO."""


@dataclass(frozen=True)
class EvidenceValue:
    """An estimate range with the evidence needed to interpret it."""

    estimate: float
    lower: float
    upper: float
    unit: str
    evidence_grade: str
    source_ids: tuple[str, ...]
    is_assumption: bool
    price_year: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("lower", self.lower),
            ("estimate", self.estimate),
            ("upper", self.upper),
        ):
            if not math.isfinite(value):
                raise MapQuboValidationError(f"evidence value {label} must be finite")
        if self.lower > self.estimate or self.estimate > self.upper:
            raise MapQuboValidationError("evidence range must satisfy lower <= estimate <= upper")
        if not self.unit:
            raise MapQuboValidationError("evidence value unit must not be empty")
        if not self.is_assumption and not self.source_ids:
            raise MapQuboValidationError(
                "a non-assumption evidence value must cite at least one source_id"
            )

    def select(self, risk_mode: RiskMode, role: ValueRole) -> float:
        if risk_mode == "estimate":
            return self.estimate
        if risk_mode == "conservative":
            return self.lower if role == "benefit" else self.upper
        return self.upper if role == "benefit" else self.lower

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OdEconomicRecord:
    od_pair_id: str
    origin_id: str
    destination_id: str
    route_edge_ids: tuple[str, ...]
    corridor_ids: tuple[str, ...]
    annual_trips: EvidenceValue | None
    persons_per_trip: EvidenceValue | None
    value_of_time: EvidenceValue | None
    reliability_value: EvidenceValue | None


@dataclass(frozen=True)
class CandidateOdImpact:
    od_pair_id: str
    route_exposure: EvidenceValue | None
    annual_economic_benefit: EvidenceValue | None
    annual_person_delay_saved_hours: EvidenceValue | None
    annual_person_reliability_saved_hours: EvidenceValue | None
    delay_reduction_seconds_per_trip: EvidenceValue | None
    reliability_reduction_seconds_per_trip: EvidenceValue | None
    annual_trips: EvidenceValue | None
    persons_per_trip: EvidenceValue | None
    source_ids: tuple[str, ...]
    evidence_grade: str
    is_assumption: bool


@dataclass(frozen=True)
class InvestmentCandidateRecord:
    candidate_id: str
    junction_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    corridor_ids: tuple[str, ...]
    capital_cost: EvidenceValue
    annual_operating_cost: EvidenceValue | None
    od_impacts: tuple[CandidateOdImpact, ...]


@dataclass(frozen=True)
class CandidateInteractionRecord:
    left_candidate_id: str
    right_candidate_id: str
    kind: str
    annual_economic_benefit: EvidenceValue
    source_ids: tuple[str, ...]
    evidence_grade: str
    is_assumption: bool


@dataclass(frozen=True)
class MapEconomicQuboInput:
    profile_id: str
    schema_version: str
    currency: str
    price_year: int
    candidates: tuple[InvestmentCandidateRecord, ...]
    od_pairs: tuple[OdEconomicRecord, ...]
    interactions: tuple[CandidateInteractionRecord, ...]
    coverage: dict[str, Any]
    profile_sha256: str


@dataclass(frozen=True)
class MapQuboConfig:
    """Explicit profile-to-objective conversion and budget encoding.

    ``benefit_present_value_factor`` converts one year of marginal benefit into
    the analysis-period value. ``operating_cost_present_value_factor`` does the
    same for annual operating cost. They are deliberately required: the QUBO
    does not hide a discount rate or analysis horizon.
    """

    budget_vnd: float
    benefit_present_value_factor: float
    operating_cost_present_value_factor: float
    capital_cost_weight: float = 1.0
    risk_mode: RiskMode = "conservative"
    budget_unit_vnd: float = 1_000_000.0
    objective_scale_vnd: float = 1_000_000.0
    budget_penalty: float | None = None
    penalty_margin: float = 1.05
    max_exact_candidates: int = 22

    def __post_init__(self) -> None:
        if self.risk_mode not in ("estimate", "conservative", "optimistic"):
            raise MapQuboValidationError("unsupported risk_mode")
        if self.budget_vnd < 0 or not math.isfinite(self.budget_vnd):
            raise MapQuboValidationError("budget_vnd must be finite and non-negative")
        for label, value in (
            ("benefit_present_value_factor", self.benefit_present_value_factor),
            ("operating_cost_present_value_factor", self.operating_cost_present_value_factor),
            ("capital_cost_weight", self.capital_cost_weight),
        ):
            if value < 0 or not math.isfinite(value):
                raise MapQuboValidationError(f"{label} must be finite and non-negative")
        for label, value in (
            ("budget_unit_vnd", self.budget_unit_vnd),
            ("objective_scale_vnd", self.objective_scale_vnd),
            ("penalty_margin", self.penalty_margin),
        ):
            if value <= 0 or not math.isfinite(value):
                raise MapQuboValidationError(f"{label} must be finite and positive")
        if self.penalty_margin <= 1.0:
            raise MapQuboValidationError("penalty_margin must be greater than 1")
        if self.budget_penalty is not None and (
            self.budget_penalty <= 0 or not math.isfinite(self.budget_penalty)
        ):
            raise MapQuboValidationError("budget_penalty must be finite and positive")
        if self.max_exact_candidates < 0:
            raise MapQuboValidationError("max_exact_candidates must be non-negative")


@dataclass(frozen=True)
class BenefitContribution:
    candidate_id: str
    od_pair_id: str
    origin_id: str
    destination_id: str
    calculation: str
    exposure_basis: str
    route_exposure_fraction: float
    annual_benefit_vnd: float
    source_ids: tuple[str, ...]
    evidence_grade: str
    is_assumption: bool
    input_values: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateCoefficient:
    candidate_id: str
    capital_cost_vnd: float
    annual_operating_cost_vnd: float
    annual_marginal_benefit_vnd: float
    analysis_period_benefit_vnd: float
    analysis_period_cost_vnd: float
    linear_objective_scaled: float
    budget_cost_units: int
    contributions: tuple[BenefitContribution, ...]
    capital_cost_evidence: dict[str, Any]
    operating_cost_evidence: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InteractionCoefficient:
    left_candidate_id: str
    right_candidate_id: str
    kind: str
    annual_marginal_benefit_vnd: float
    analysis_period_benefit_vnd: float
    quadratic_objective_scaled: float
    evidence: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_grade: str
    is_assumption: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuadraticBias:
    left: str
    right: str
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuboModel:
    schema_version: str
    variables: tuple[str, ...]
    candidate_variables: tuple[str, ...]
    slack_variables: tuple[str, ...]
    slack_weights: tuple[int, ...]
    linear_bias: dict[str, float]
    quadratic_bias: tuple[QuadraticBias, ...]
    constant: float
    budget_units: int
    budget_unit_vnd: float
    budget_penalty: float
    minimum_safe_budget_penalty: float
    objective_scale_vnd: float

    def energy(self, assignment: Mapping[str, int | bool]) -> float:
        unknown = set(assignment) - set(self.variables)
        if unknown:
            raise MapQuboValidationError(
                f"assignment contains unknown variables: {sorted(unknown)}"
            )
        bits: dict[str, int] = {}
        for variable in self.variables:
            raw_value = assignment.get(variable, 0)
            if not isinstance(raw_value, (int, bool)) or raw_value not in (0, 1):
                raise MapQuboValidationError(f"{variable}: assignment value must be binary")
            value = int(raw_value)
            bits[variable] = value
        energy = self.constant
        energy += sum(self.linear_bias[name] * bits[name] for name in self.variables)
        energy += sum(
            term.value * bits[term.left] * bits[term.right] for term in self.quadratic_bias
        )
        return energy

    def matrix(self) -> dict[str, dict[str, float]]:
        rows = {name: {name: self.linear_bias[name]} for name in self.variables}
        for term in self.quadratic_bias:
            rows[term.left][term.right] = term.value
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "variables": list(self.variables),
            "candidate_variables": list(self.candidate_variables),
            "slack_variables": list(self.slack_variables),
            "slack_weights": list(self.slack_weights),
            "linear_bias": dict(self.linear_bias),
            "quadratic_bias": [term.to_dict() for term in self.quadratic_bias],
            "matrix_upper_triangular": self.matrix(),
            "constant": self.constant,
            "budget_units": self.budget_units,
            "budget_unit_vnd": self.budget_unit_vnd,
            "budget_penalty": self.budget_penalty,
            "minimum_safe_budget_penalty": self.minimum_safe_budget_penalty,
            "objective_scale_vnd": self.objective_scale_vnd,
        }


@dataclass(frozen=True)
class MapQuboBuild:
    profile: MapEconomicQuboInput
    config: MapQuboConfig
    candidate_coefficients: tuple[CandidateCoefficient, ...]
    interaction_coefficients: tuple[InteractionCoefficient, ...]
    model: QuboModel
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortfolioEvaluation:
    selected_candidate_ids: tuple[str, ...]
    capital_cost_vnd: float
    annual_marginal_benefit_vnd: float
    analysis_period_benefit_vnd: float
    analysis_period_cost_vnd: float
    interaction_benefit_vnd: float
    net_public_value_vnd: float
    budget_feasible: bool
    budget_slack_vnd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExactQuboSolution:
    selected_candidate_ids: tuple[str, ...]
    assignment: dict[str, int]
    energy: float
    evaluated_candidate_subsets: int
    portfolio: PortfolioEvaluation

    def to_dict(self) -> dict[str, Any]:
        return {
            "solver": "deterministic_candidate_subset_bruteforce",
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "assignment": dict(self.assignment),
            "energy": self.energy,
            "evaluated_candidate_subsets": self.evaluated_candidate_subsets,
            "portfolio": self.portfolio.to_dict(),
        }


def load_map_economic_profile(
    source: Mapping[str, Any] | Path | str | object,
) -> MapEconomicQuboInput:
    """Load and validate the QUBO view of ``map_economic_profile.v1``.

    Objects with a ``to_dict()`` method are accepted so this adapter can consume
    the typed data-management model without importing that package.
    """

    raw = _load_profile_mapping(source)
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    profile_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    schema_version = _required_string(raw, ("schema_version",), "profile")
    if schema_version != MAP_ECONOMIC_PROFILE_VERSION:
        raise MapQuboValidationError(
            f"unsupported profile schema_version {schema_version!r}; "
            f"expected {MAP_ECONOMIC_PROFILE_VERSION!r}"
        )
    metadata = _optional_mapping(raw.get("metadata"), "metadata")
    profile_id = _first_string(raw, metadata, ("profile_id", "id"))
    if not profile_id:
        raise MapQuboValidationError("profile_id is required")
    currency = _first_string(raw, metadata, ("currency", "price_currency"))
    if not currency:
        raise MapQuboValidationError("currency is required")
    if currency != "VND":
        raise MapQuboValidationError("this VND objective requires currency VND")
    price_year = _optional_int(_first_value(raw, metadata, ("price_year",)), "price_year")
    if price_year is None:
        raise MapQuboValidationError("price_year is required")

    valuation_items = _required_object_list(raw.get("valuations", []), "valuations")
    valuations: dict[str, Mapping[str, Any]] = {}
    for item in valuation_items:
        valuation_id = _required_string(item, ("valuation_id", "id"), "valuation")
        if valuation_id in valuations:
            raise MapQuboValidationError(f"duplicate valuation_id: {valuation_id!r}")
        valuations[valuation_id] = item

    od_items = _required_object_list(raw.get("od_pairs", []), "od_pairs")
    od_pairs = tuple(
        sorted(
            (_parse_od_pair(item, valuations, currency) for item in od_items),
            key=lambda x: x.od_pair_id,
        )
    )
    _require_unique([item.od_pair_id for item in od_pairs], "od_pair_id")
    od_ids = {item.od_pair_id for item in od_pairs}

    candidate_items = _required_object_list(
        raw.get("investment_candidates", raw.get("candidates", [])),
        "investment_candidates",
    )
    candidates = tuple(
        sorted(
            (_parse_candidate(item, currency) for item in candidate_items),
            key=lambda x: x.candidate_id,
        )
    )
    if not candidates:
        raise MapQuboValidationError("profile must contain at least one investment candidate")
    _require_unique([item.candidate_id for item in candidates], "candidate_id")
    for candidate in candidates:
        for impact in candidate.od_impacts:
            if impact.od_pair_id not in od_ids:
                raise MapQuboValidationError(
                    f"{candidate.candidate_id}: unknown od_pair_id {impact.od_pair_id!r}"
                )

    candidate_ids = {item.candidate_id for item in candidates}
    interaction_items = _required_object_list(
        raw.get("candidate_interactions", raw.get("interactions", [])),
        "candidate_interactions",
    )
    interactions = tuple(
        sorted(
            (_parse_interaction(item, currency) for item in interaction_items),
            key=lambda x: (x.left_candidate_id, x.right_candidate_id),
        )
    )
    seen_pairs: set[tuple[str, str]] = set()
    for interaction in interactions:
        pair = (interaction.left_candidate_id, interaction.right_candidate_id)
        if (
            interaction.left_candidate_id not in candidate_ids
            or interaction.right_candidate_id not in candidate_ids
        ):
            raise MapQuboValidationError(f"interaction references unknown candidates: {pair}")
        if pair in seen_pairs:
            raise MapQuboValidationError(f"duplicate candidate interaction: {pair}")
        seen_pairs.add(pair)

    for value in _all_profile_evidence_values(candidates, od_pairs, interactions):
        if value.unit.startswith("VND"):
            if value.price_year != price_year:
                raise MapQuboValidationError(
                    f"monetary value price_year {value.price_year!r} must match profile "
                    f"price_year {price_year}"
                )
        elif value.price_year is not None:
            raise MapQuboValidationError(
                f"non-monetary unit {value.unit!r} must not define price_year"
            )

    coverage = dict(_optional_mapping(raw.get("coverage"), "coverage"))
    return MapEconomicQuboInput(
        profile_id=profile_id,
        schema_version=schema_version,
        currency=currency,
        price_year=price_year,
        candidates=candidates,
        od_pairs=od_pairs,
        interactions=interactions,
        coverage=coverage,
        profile_sha256=profile_hash,
    )


def build_map_aware_qubo(profile: MapEconomicQuboInput, config: MapQuboConfig) -> MapQuboBuild:
    od_by_id = {item.od_pair_id: item for item in profile.od_pairs}
    warnings: list[str] = []
    candidate_coefficients: list[CandidateCoefficient] = []

    for candidate in profile.candidates:
        contributions = tuple(
            _benefit_contribution(
                candidate.candidate_id,
                impact,
                od_by_id[impact.od_pair_id],
                config,
                profile.currency,
            )
            for impact in sorted(candidate.od_impacts, key=lambda value: value.od_pair_id)
        )
        annual_benefit = sum(item.annual_benefit_vnd for item in contributions)
        capital_cost = candidate.capital_cost.select(config.risk_mode, "cost")
        operating_cost = (
            candidate.annual_operating_cost.select(config.risk_mode, "cost")
            if candidate.annual_operating_cost is not None
            else 0.0
        )
        analysis_benefit = annual_benefit * config.benefit_present_value_factor
        analysis_cost = (
            config.capital_cost_weight * capital_cost
            + operating_cost * config.operating_cost_present_value_factor
        )
        cost_units = _cost_to_budget_units(capital_cost, config.budget_unit_vnd)
        if not contributions:
            warnings.append(f"{candidate.candidate_id}: no OD-specific marginal benefit supplied")
        if candidate.capital_cost.is_assumption:
            warnings.append(f"{candidate.candidate_id}: capital cost is an assumption")
        candidate_coefficients.append(
            CandidateCoefficient(
                candidate_id=candidate.candidate_id,
                capital_cost_vnd=capital_cost,
                annual_operating_cost_vnd=operating_cost,
                annual_marginal_benefit_vnd=annual_benefit,
                analysis_period_benefit_vnd=analysis_benefit,
                analysis_period_cost_vnd=analysis_cost,
                linear_objective_scaled=(analysis_cost - analysis_benefit)
                / config.objective_scale_vnd,
                budget_cost_units=cost_units,
                contributions=contributions,
                capital_cost_evidence=candidate.capital_cost.to_dict(),
                operating_cost_evidence=(
                    candidate.annual_operating_cost.to_dict()
                    if candidate.annual_operating_cost is not None
                    else None
                ),
            )
        )

    interaction_coefficients = tuple(
        _interaction_coefficient(item, config) for item in profile.interactions
    )
    base_reduction_bound = sum(
        max(-coefficient.linear_objective_scaled, 0.0) for coefficient in candidate_coefficients
    ) + sum(
        max(-coefficient.quadratic_objective_scaled, 0.0)
        for coefficient in interaction_coefficients
    )
    minimum_safe_penalty = base_reduction_bound + max(1e-9, abs(base_reduction_bound) * 1e-9)
    automatic_penalty = max(1.0, base_reduction_bound * config.penalty_margin + 1e-9)
    if config.budget_penalty is not None and config.budget_penalty <= minimum_safe_penalty:
        raise MapQuboValidationError(
            "budget_penalty does not dominate the maximum attainable objective reduction: "
            f"got {config.budget_penalty:.12g}, require > {minimum_safe_penalty:.12g}"
        )
    budget_penalty = config.budget_penalty or automatic_penalty
    model = _assemble_qubo_model(
        tuple(candidate_coefficients),
        interaction_coefficients,
        config,
        budget_penalty,
        minimum_safe_penalty,
    )
    return MapQuboBuild(
        profile=profile,
        config=config,
        candidate_coefficients=tuple(candidate_coefficients),
        interaction_coefficients=interaction_coefficients,
        model=model,
        warnings=tuple(sorted(set(warnings))),
    )


def evaluate_portfolio(
    build: MapQuboBuild, selected_candidate_ids: Sequence[str]
) -> PortfolioEvaluation:
    selected = tuple(sorted(set(selected_candidate_ids)))
    available = {item.candidate_id: item for item in build.candidate_coefficients}
    unknown = set(selected) - set(available)
    if unknown:
        raise MapQuboValidationError(f"unknown selected candidates: {sorted(unknown)}")
    coefficients = [available[candidate_id] for candidate_id in selected]
    selected_set = set(selected)
    interactions = [
        item
        for item in build.interaction_coefficients
        if item.left_candidate_id in selected_set and item.right_candidate_id in selected_set
    ]
    capital_cost = sum(item.capital_cost_vnd for item in coefficients)
    annual_candidate_benefit = sum(item.annual_marginal_benefit_vnd for item in coefficients)
    annual_interaction_benefit = sum(item.annual_marginal_benefit_vnd for item in interactions)
    analysis_candidate_benefit = sum(item.analysis_period_benefit_vnd for item in coefficients)
    analysis_interaction_benefit = sum(item.analysis_period_benefit_vnd for item in interactions)
    analysis_cost = sum(item.analysis_period_cost_vnd for item in coefficients)
    total_analysis_benefit = analysis_candidate_benefit + analysis_interaction_benefit
    return PortfolioEvaluation(
        selected_candidate_ids=selected,
        capital_cost_vnd=capital_cost,
        annual_marginal_benefit_vnd=annual_candidate_benefit + annual_interaction_benefit,
        analysis_period_benefit_vnd=total_analysis_benefit,
        analysis_period_cost_vnd=analysis_cost,
        interaction_benefit_vnd=analysis_interaction_benefit,
        net_public_value_vnd=total_analysis_benefit - analysis_cost,
        budget_feasible=capital_cost <= build.config.budget_vnd + 1e-6,
        budget_slack_vnd=build.config.budget_vnd - capital_cost,
    )


def solve_map_qubo_exact(build: MapQuboBuild) -> ExactQuboSolution:
    """Solve small candidate sets exactly while analytically filling budget slack bits."""

    candidate_ids = build.model.candidate_variables
    if len(candidate_ids) > build.config.max_exact_candidates:
        raise MapQuboValidationError(
            f"exact solver supports at most {build.config.max_exact_candidates} candidates; "
            f"got {len(candidate_ids)}"
        )
    costs = {item.candidate_id: item.budget_cost_units for item in build.candidate_coefficients}
    best_assignment: dict[str, int] | None = None
    best_energy = math.inf
    best_ids: tuple[str, ...] = ()
    best_cost = math.inf
    subset_count = 1 << len(candidate_ids)
    for mask in range(subset_count):
        assignment = {
            name: int(bool(mask & (1 << index))) for index, name in enumerate(candidate_ids)
        }
        spent_units = sum(costs[name] * assignment[name] for name in candidate_ids)
        remaining = max(build.model.budget_units - spent_units, 0)
        assignment.update(
            _slack_assignment(
                build.model.slack_variables,
                build.model.slack_weights,
                remaining,
            )
        )
        energy = build.model.energy(assignment)
        ids = tuple(name for name in candidate_ids if assignment[name])
        capital_cost = sum(
            item.capital_cost_vnd
            for item in build.candidate_coefficients
            if item.candidate_id in ids
        )
        if _is_better_solution(energy, capital_cost, ids, best_energy, best_cost, best_ids):
            best_assignment = assignment
            best_energy = energy
            best_ids = ids
            best_cost = capital_cost
    if best_assignment is None:
        raise RuntimeError("exact solver failed to evaluate the empty subset")
    portfolio = evaluate_portfolio(build, best_ids)
    return ExactQuboSolution(
        selected_candidate_ids=best_ids,
        assignment=best_assignment,
        energy=best_energy,
        evaluated_candidate_subsets=subset_count,
        portfolio=portfolio,
    )


def build_qubo_run_manifest(
    build: MapQuboBuild,
    solution: ExactQuboSolution,
    *,
    run_id: str,
) -> dict[str, Any]:
    if not run_id.strip():
        raise MapQuboValidationError("run_id must not be empty")
    return {
        "schema_version": MAP_AWARE_QUBO_RUN_VERSION,
        "run_id": run_id,
        "input_profile": {
            "profile_id": build.profile.profile_id,
            "schema_version": build.profile.schema_version,
            "sha256": build.profile.profile_sha256,
            "currency": build.profile.currency,
            "price_year": build.profile.price_year,
            "economic_calibration_coverage": build.profile.coverage,
        },
        "objective_contract": {
            "sense": "minimize",
            "benefit_basis": "OD-specific marginal impact only",
            "gross_trip_value_used": False,
            "risk_mode": build.config.risk_mode,
            "benefit_present_value_factor": build.config.benefit_present_value_factor,
            "operating_cost_present_value_factor": (
                build.config.operating_cost_present_value_factor
            ),
            "capital_cost_weight": build.config.capital_cost_weight,
            "objective_scale_vnd": build.config.objective_scale_vnd,
            "budget_vnd": build.config.budget_vnd,
        },
        "candidate_coefficients": [item.to_dict() for item in build.candidate_coefficients],
        "interaction_coefficients": [item.to_dict() for item in build.interaction_coefficients],
        "qubo": build.model.to_dict(),
        "solution": solution.to_dict(),
        "warnings": list(build.warnings),
        "claim_status": "decision_support_only_requires_economic_review",
    }


def _benefit_contribution(
    candidate_id: str,
    impact: CandidateOdImpact,
    od_pair: OdEconomicRecord,
    config: MapQuboConfig,
    currency: str,
) -> BenefitContribution:
    exposure, exposure_basis, exposure_input = _resolve_exposure(impact, od_pair, config)
    inputs: dict[str, dict[str, Any]] = {}
    if exposure_input is not None:
        inputs["route_exposure_fraction"] = exposure_input.to_dict()

    if impact.annual_economic_benefit is not None:
        value = impact.annual_economic_benefit
        _require_unit(
            value,
            {currency, f"{currency}/year", "VND", "VND/year"},
            "annual_economic_benefit_vnd",
        )
        annual_benefit = _selected_product((value, exposure_input), config.risk_mode)
        inputs["annual_economic_benefit_vnd"] = value.to_dict()
        calculation = "explicit_annual_marginal_economic_benefit"
    else:
        annual_benefit = 0.0
        calculation_parts: list[str] = []
        if impact.annual_person_delay_saved_hours is not None:
            saved = impact.annual_person_delay_saved_hours
            _require_unit(
                saved,
                {"person_hours/year", "person_hour/year"},
                "annual_person_delay_saved_hours",
            )
            vot = _required_od_value(od_pair.value_of_time, od_pair.od_pair_id, "value_of_time")
            _require_rate_unit(vot, "value_of_time", currency)
            annual_benefit += _selected_product((saved, vot, exposure_input), config.risk_mode)
            inputs["annual_person_delay_saved_hours"] = saved.to_dict()
            inputs["value_of_time"] = vot.to_dict()
            calculation_parts.append("saved_person_hours_x_value_of_time")
        if impact.annual_person_reliability_saved_hours is not None:
            saved_reliability = impact.annual_person_reliability_saved_hours
            _require_unit(
                saved_reliability,
                {"person_hours/year", "person_hour/year"},
                "annual_person_reliability_saved_hours",
            )
            reliability_value = _required_od_value(
                od_pair.reliability_value,
                od_pair.od_pair_id,
                "reliability_value",
            )
            _require_rate_unit(reliability_value, "reliability_value", currency)
            annual_benefit += _selected_product(
                (saved_reliability, reliability_value, exposure_input), config.risk_mode
            )
            inputs["annual_person_reliability_saved_hours"] = saved_reliability.to_dict()
            inputs["reliability_value"] = reliability_value.to_dict()
            calculation_parts.append("saved_reliability_hours_x_reliability_value")
        if impact.delay_reduction_seconds_per_trip is not None:
            annual_benefit += _per_trip_time_benefit(
                impact.delay_reduction_seconds_per_trip,
                impact.annual_trips or od_pair.annual_trips,
                impact.persons_per_trip or od_pair.persons_per_trip,
                od_pair.value_of_time,
                od_pair.od_pair_id,
                config,
                inputs,
                prefix="delay",
                currency=currency,
                exposure=exposure_input,
            )
            calculation_parts.append("marginal_delay_x_annual_trips_x_persons_x_value_of_time")
        if impact.reliability_reduction_seconds_per_trip is not None:
            annual_benefit += _per_trip_time_benefit(
                impact.reliability_reduction_seconds_per_trip,
                impact.annual_trips or od_pair.annual_trips,
                impact.persons_per_trip or od_pair.persons_per_trip,
                od_pair.reliability_value,
                od_pair.od_pair_id,
                config,
                inputs,
                prefix="reliability",
                currency=currency,
                exposure=exposure_input,
            )
            calculation_parts.append(
                "marginal_reliability_x_annual_trips_x_persons_x_reliability_value"
            )
        if not calculation_parts:
            raise MapQuboValidationError(
                f"{candidate_id}/{impact.od_pair_id}: impact has no monetizable marginal benefit"
            )
        calculation = "+".join(calculation_parts)

    source_ids = tuple(
        sorted(
            set(impact.source_ids).union(
                source_id
                for record in inputs.values()
                for source_id in cast(list[str], record.get("source_ids", []))
            )
        )
    )
    is_assumption = impact.is_assumption or any(
        bool(record.get("is_assumption", False)) for record in inputs.values()
    )
    grades = [str(record.get("evidence_grade", "unrated")) for record in inputs.values()]
    evidence_grade = impact.evidence_grade or _least_evidence_grade(grades)
    return BenefitContribution(
        candidate_id=candidate_id,
        od_pair_id=impact.od_pair_id,
        origin_id=od_pair.origin_id,
        destination_id=od_pair.destination_id,
        calculation=calculation,
        exposure_basis=exposure_basis,
        route_exposure_fraction=exposure,
        annual_benefit_vnd=annual_benefit,
        source_ids=source_ids,
        evidence_grade=evidence_grade,
        is_assumption=is_assumption,
        input_values=inputs,
    )


def _per_trip_time_benefit(
    seconds_per_trip: EvidenceValue,
    annual_trips: EvidenceValue | None,
    persons_per_trip: EvidenceValue | None,
    rate: EvidenceValue | None,
    od_pair_id: str,
    config: MapQuboConfig,
    inputs: dict[str, dict[str, Any]],
    *,
    prefix: str,
    currency: str,
    exposure: EvidenceValue | None,
) -> float:
    _require_unit(seconds_per_trip, {"seconds/trip", "second/trip"}, f"{prefix}_seconds")
    trips = _required_od_value(annual_trips, od_pair_id, "annual_trips")
    persons = _required_od_value(persons_per_trip, od_pair_id, "persons_per_trip")
    economic_rate = _required_od_value(rate, od_pair_id, f"{prefix}_economic_rate")
    _require_unit(trips, {"trips/year", "trip/year"}, "annual_trips")
    _require_unit(persons, {"persons/trip", "person/trip"}, "persons_per_trip")
    _require_rate_unit(economic_rate, f"{prefix}_economic_rate", currency)
    for value, label in (
        (trips, "annual_trips"),
        (persons, "persons_per_trip"),
        (economic_rate, f"{prefix}_economic_rate"),
    ):
        _require_non_negative(value, label)
    inputs[f"{prefix}_reduction_seconds_per_trip"] = seconds_per_trip.to_dict()
    inputs["annual_trips"] = trips.to_dict()
    inputs["persons_per_trip"] = persons.to_dict()
    inputs[f"{prefix}_economic_rate"] = economic_rate.to_dict()
    return (
        _selected_product(
            (seconds_per_trip, trips, persons, economic_rate, exposure), config.risk_mode
        )
        / 3600.0
    )


def _selected_product(values: Sequence[EvidenceValue | None], mode: RiskMode) -> float:
    """Bound signed products; a negative effect worsens as positive exposure grows."""
    lower = upper = estimate = 1.0
    for value in values:
        if value is None:
            continue
        endpoints = (
            lower * value.lower,
            lower * value.upper,
            upper * value.lower,
            upper * value.upper,
        )
        lower, upper = min(endpoints), max(endpoints)
        estimate *= value.estimate
    result = estimate if mode == "estimate" else lower if mode == "conservative" else upper
    if not math.isfinite(result):
        raise MapQuboValidationError("economic product overflows finite objective range")
    return result


def _resolve_exposure(
    impact: CandidateOdImpact,
    od_pair: OdEconomicRecord,
    config: MapQuboConfig,
) -> tuple[float, str, EvidenceValue | None]:
    if impact.route_exposure is not None:
        _require_unit(
            impact.route_exposure,
            {"fraction", "ratio", "1"},
            "route_exposure_fraction",
        )
        exposure = impact.route_exposure.select(config.risk_mode, "benefit")
        if impact.route_exposure.lower < 0 or impact.route_exposure.upper > 1:
            raise MapQuboValidationError(
                f"{impact.od_pair_id}: route exposure must be between zero and one"
            )
        return exposure, "profile_route_exposure", impact.route_exposure
    if not od_pair.route_edge_ids and not od_pair.corridor_ids:
        return 1.0, "explicit_od_impact_no_route_geometry", None
    return 1.0, "explicit_od_impact", None


def _interaction_coefficient(
    interaction: CandidateInteractionRecord, config: MapQuboConfig
) -> InteractionCoefficient:
    annual_benefit = interaction.annual_economic_benefit.select(config.risk_mode, "benefit")
    analysis_benefit = annual_benefit * config.benefit_present_value_factor
    return InteractionCoefficient(
        left_candidate_id=interaction.left_candidate_id,
        right_candidate_id=interaction.right_candidate_id,
        kind=interaction.kind,
        annual_marginal_benefit_vnd=annual_benefit,
        analysis_period_benefit_vnd=analysis_benefit,
        quadratic_objective_scaled=-analysis_benefit / config.objective_scale_vnd,
        evidence=interaction.annual_economic_benefit.to_dict(),
        source_ids=interaction.source_ids,
        evidence_grade=interaction.evidence_grade,
        is_assumption=interaction.is_assumption,
    )


def _assemble_qubo_model(
    candidates: tuple[CandidateCoefficient, ...],
    interactions: tuple[InteractionCoefficient, ...],
    config: MapQuboConfig,
    budget_penalty: float,
    minimum_safe_penalty: float,
) -> QuboModel:
    candidate_variables = tuple(item.candidate_id for item in candidates)
    budget_units = int(
        (Decimal(str(config.budget_vnd)) / Decimal(str(config.budget_unit_vnd))).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    slack_weights = _bounded_binary_weights(budget_units)
    slack_variables = tuple(f"__budget_slack_{index:03d}" for index in range(len(slack_weights)))
    collision = set(candidate_variables).intersection(slack_variables)
    if collision:
        raise MapQuboValidationError(
            f"candidate ids collide with slack variables: {sorted(collision)}"
        )
    variables = candidate_variables + slack_variables
    weights: dict[str, int] = {item.candidate_id: item.budget_cost_units for item in candidates}
    weights.update(dict(zip(slack_variables, slack_weights, strict=True)))
    objective_linear = {item.candidate_id: item.linear_objective_scaled for item in candidates}
    linear = {
        variable: objective_linear.get(variable, 0.0)
        + budget_penalty * (weights[variable] ** 2 - 2 * budget_units * weights[variable])
        for variable in variables
    }
    pair_bias: dict[tuple[str, str], float] = {}
    for left_index, left in enumerate(variables):
        for right in variables[left_index + 1 :]:
            pair_bias[(left, right)] = 2.0 * budget_penalty * weights[left] * weights[right]
    for interaction in interactions:
        pair = (interaction.left_candidate_id, interaction.right_candidate_id)
        pair_bias[pair] = pair_bias.get(pair, 0.0) + interaction.quadratic_objective_scaled
    quadratic = tuple(
        QuadraticBias(left=left, right=right, value=value)
        for (left, right), value in sorted(pair_bias.items())
        if value != 0.0
    )
    return QuboModel(
        schema_version=MAP_AWARE_QUBO_MODEL_VERSION,
        variables=variables,
        candidate_variables=candidate_variables,
        slack_variables=slack_variables,
        slack_weights=slack_weights,
        linear_bias=linear,
        quadratic_bias=quadratic,
        constant=budget_penalty * budget_units**2,
        budget_units=budget_units,
        budget_unit_vnd=config.budget_unit_vnd,
        budget_penalty=budget_penalty,
        minimum_safe_budget_penalty=minimum_safe_penalty,
        objective_scale_vnd=config.objective_scale_vnd,
    )


def _bounded_binary_weights(maximum: int) -> tuple[int, ...]:
    if maximum <= 0:
        return ()
    weights: list[int] = []
    represented = 0
    next_power = 1
    while represented < maximum:
        weight = min(next_power, maximum - represented)
        weights.append(weight)
        represented += weight
        next_power *= 2
    return tuple(weights)


def _slack_assignment(
    variables: tuple[str, ...], weights: tuple[int, ...], target: int
) -> dict[str, int]:
    result = {name: 0 for name in variables}
    remaining = target
    indexed = list(enumerate(weights))
    for index, weight in sorted(indexed, key=lambda item: (-item[1], item[0])):
        if weight <= remaining:
            result[variables[index]] = 1
            remaining -= weight
    if remaining != 0:
        raise RuntimeError(f"budget slack encoding cannot represent {target}")
    return result


def _is_better_solution(
    energy: float,
    capital_cost: float,
    ids: tuple[str, ...],
    best_energy: float,
    best_cost: float,
    best_ids: tuple[str, ...],
) -> bool:
    if energy < best_energy - 1e-9:
        return True
    if not math.isclose(energy, best_energy, rel_tol=1e-12, abs_tol=1e-9):
        return False
    return (capital_cost, ids) < (best_cost, best_ids)


def _cost_to_budget_units(cost_vnd: float, unit_vnd: float) -> int:
    if cost_vnd < 0:
        raise MapQuboValidationError("capital cost must be non-negative")
    return int(
        (Decimal(str(cost_vnd)) / Decimal(str(unit_vnd))).to_integral_value(rounding=ROUND_CEILING)
    )


def _parse_od_pair(
    raw: Mapping[str, Any],
    valuations: Mapping[str, Mapping[str, Any]],
    currency: str,
) -> OdEconomicRecord:
    od_pair_id = _required_string(raw, ("od_pair_id", "id"), "od_pair")
    origin_id = _location_id(raw.get("origin"), raw, "origin")
    destination_id = _location_id(raw.get("destination"), raw, "destination")
    valuation_id = _required_string(raw, ("valuation_id",), od_pair_id)
    if valuation_id not in valuations:
        raise MapQuboValidationError(
            f"{od_pair_id}: valuation_id references unknown valuation {valuation_id!r}"
        )
    valuation = valuations[valuation_id]
    od_pair = OdEconomicRecord(
        od_pair_id=od_pair_id,
        origin_id=origin_id,
        destination_id=destination_id,
        route_edge_ids=_string_tuple(
            raw, ("route_edge_ids", "route_edges", "edge_ids"), preserve_order=True
        ),
        corridor_ids=_string_tuple(raw, ("corridor_ids", "route_corridors")),
        annual_trips=_optional_evidence(raw, ("annual_trips",), f"{od_pair_id}.annual_trips"),
        persons_per_trip=(
            _optional_evidence(raw, ("persons_per_trip",), f"{od_pair_id}.persons_per_trip")
            or _optional_evidence(
                valuation,
                ("persons_per_trip",),
                f"valuations.{valuation_id}.persons_per_trip",
            )
        ),
        value_of_time=(
            _optional_evidence(
                raw,
                ("value_of_time_vnd_per_person_hour", "value_of_time"),
                f"{od_pair_id}.value_of_time",
            )
            or _optional_evidence(
                valuation,
                ("value_of_time_vnd_per_person_hour", "value_of_time"),
                f"valuations.{valuation_id}.value_of_time",
            )
        ),
        reliability_value=(
            _optional_evidence(
                raw,
                ("reliability_value_vnd_per_person_hour", "reliability_value"),
                f"{od_pair_id}.reliability_value",
            )
            or _optional_evidence(
                valuation,
                ("reliability_value_vnd_per_person_hour", "reliability_value"),
                f"valuations.{valuation_id}.reliability_value",
            )
        ),
    )
    for value, label in (
        (od_pair.annual_trips, "annual_trips"),
        (od_pair.persons_per_trip, "persons_per_trip"),
        (od_pair.value_of_time, "value_of_time"),
        (od_pair.reliability_value, "reliability_value"),
    ):
        if value is not None:
            _require_non_negative(value, f"{od_pair_id}.{label}")
    if od_pair.annual_trips is not None:
        _require_unit(
            od_pair.annual_trips,
            {"trips/year", "trip/year"},
            f"{od_pair_id}.annual_trips",
        )
    if od_pair.persons_per_trip is not None:
        _require_unit(
            od_pair.persons_per_trip,
            {"persons/trip", "person/trip"},
            f"{od_pair_id}.persons_per_trip",
        )
    if od_pair.value_of_time is not None:
        _require_rate_unit(od_pair.value_of_time, f"{od_pair_id}.value_of_time", currency)
    if od_pair.reliability_value is not None:
        _require_rate_unit(
            od_pair.reliability_value,
            f"{od_pair_id}.reliability_value",
            currency,
        )
    return od_pair


def _parse_candidate(raw: Mapping[str, Any], currency: str) -> InvestmentCandidateRecord:
    candidate_id = _required_string(raw, ("candidate_id", "id"), "candidate")
    capital_cost = _required_evidence(
        raw,
        ("capital_cost_vnd", "capex_vnd", "capital_cost"),
        f"{candidate_id}.capital_cost_vnd",
    )
    _require_unit(capital_cost, {currency, "VND"}, f"{candidate_id}.capital_cost_vnd")
    _require_non_negative(capital_cost, f"{candidate_id}.capital_cost_vnd")
    operating_cost = _optional_evidence(
        raw,
        ("annual_operating_cost_vnd", "annual_maintenance_vnd", "annual_operating_cost"),
        f"{candidate_id}.annual_operating_cost_vnd",
    )
    if operating_cost is not None:
        _require_unit(
            operating_cost,
            {currency, f"{currency}/year", "VND", "VND/year"},
            f"{candidate_id}.annual_operating_cost_vnd",
        )
        _require_non_negative(operating_cost, f"{candidate_id}.annual_operating_cost_vnd")
    impact_items = _required_object_list(raw.get("od_impacts", []), f"{candidate_id}.od_impacts")
    impacts = tuple(
        sorted((_parse_impact(item) for item in impact_items), key=lambda x: x.od_pair_id)
    )
    _require_unique([item.od_pair_id for item in impacts], f"{candidate_id}.od_pair_id")
    return InvestmentCandidateRecord(
        candidate_id=candidate_id,
        junction_ids=_string_tuple(raw, ("junction_ids", "intersection_ids")),
        edge_ids=_string_tuple(raw, ("edge_ids",)),
        corridor_ids=_string_tuple(raw, ("corridor_ids",)),
        capital_cost=capital_cost,
        annual_operating_cost=operating_cost,
        od_impacts=impacts,
    )


def _parse_impact(raw: Mapping[str, Any]) -> CandidateOdImpact:
    od_pair_id = _required_string(raw, ("od_pair_id", "flow_id"), "od_impact")
    source_ids, evidence_grade, is_assumption = _container_evidence_metadata(raw)
    impact = CandidateOdImpact(
        od_pair_id=od_pair_id,
        route_exposure=_optional_evidence(
            raw,
            ("route_exposure_fraction", "route_exposure"),
            f"{od_pair_id}.route_exposure",
        ),
        annual_economic_benefit=_optional_evidence(
            raw,
            ("annual_economic_benefit_vnd", "annual_marginal_benefit_vnd"),
            f"{od_pair_id}.annual_economic_benefit_vnd",
        ),
        annual_person_delay_saved_hours=_optional_evidence(
            raw,
            ("annual_person_delay_saved_hours",),
            f"{od_pair_id}.annual_person_delay_saved_hours",
        ),
        annual_person_reliability_saved_hours=_optional_evidence(
            raw,
            ("annual_person_reliability_saved_hours",),
            f"{od_pair_id}.annual_person_reliability_saved_hours",
        ),
        delay_reduction_seconds_per_trip=_optional_evidence(
            raw,
            ("delay_reduction_seconds_per_trip",),
            f"{od_pair_id}.delay_reduction_seconds_per_trip",
        ),
        reliability_reduction_seconds_per_trip=_optional_evidence(
            raw,
            ("reliability_reduction_seconds_per_trip",),
            f"{od_pair_id}.reliability_reduction_seconds_per_trip",
        ),
        annual_trips=_optional_evidence(raw, ("annual_trips",), f"{od_pair_id}.annual_trips"),
        persons_per_trip=_optional_evidence(
            raw, ("persons_per_trip",), f"{od_pair_id}.persons_per_trip"
        ),
        source_ids=source_ids,
        evidence_grade=evidence_grade,
        is_assumption=is_assumption,
    )
    for value, label in (
        (impact.route_exposure, "route_exposure_fraction"),
        (impact.annual_trips, "annual_trips"),
        (impact.persons_per_trip, "persons_per_trip"),
    ):
        if value is not None:
            _require_non_negative(value, f"{od_pair_id}.{label}")
    decomposed = (
        impact.annual_person_delay_saved_hours,
        impact.annual_person_reliability_saved_hours,
        impact.delay_reduction_seconds_per_trip,
        impact.reliability_reduction_seconds_per_trip,
    )
    if impact.annual_economic_benefit is not None and any(v is not None for v in decomposed):
        raise MapQuboValidationError(
            f"{od_pair_id}: aggregate and decomposed benefits are ambiguous"
        )
    for annual, per_trip in ((decomposed[0], decomposed[2]), (decomposed[1], decomposed[3])):
        if annual is not None and per_trip is not None:
            raise MapQuboValidationError(
                f"{od_pair_id}: annual and per-trip benefit double counting"
            )
    return impact


def _parse_interaction(raw: Mapping[str, Any], currency: str) -> CandidateInteractionRecord:
    left = _required_string(
        raw,
        ("left_candidate_id", "candidate_id_a", "candidate_a"),
        "interaction.left_candidate_id",
    )
    right = _required_string(
        raw,
        ("right_candidate_id", "candidate_id_b", "candidate_b"),
        "interaction.right_candidate_id",
    )
    if left == right:
        raise MapQuboValidationError("candidate interaction cannot reference itself")
    left, right = sorted((left, right))
    kind = _required_string(raw, ("kind", "interaction_type", "type"), "interaction.kind")
    aliases = {"synergy": "complementarity", "double_counting": "overlap"}
    kind = aliases.get(kind, kind)
    if kind not in {"complementarity", "overlap", "bottleneck"}:
        raise MapQuboValidationError(f"interaction {left}/{right}: unsupported kind {kind!r}")
    benefit = _required_evidence(
        raw,
        ("annual_economic_benefit_vnd", "annual_interaction_benefit_vnd"),
        f"interaction {left}/{right}.annual_economic_benefit_vnd",
    )
    _require_unit(
        benefit,
        {currency, f"{currency}/year", "VND", "VND/year"},
        f"interaction {left}/{right}.annual_economic_benefit_vnd",
    )
    if kind == "overlap" and benefit.upper > 0:
        raise MapQuboValidationError(
            f"interaction {left}/{right}: overlap benefit range must be non-positive"
        )
    if kind == "complementarity" and benefit.lower < 0:
        raise MapQuboValidationError(
            f"interaction {left}/{right}: complementarity benefit range must be non-negative"
        )
    source_ids, evidence_grade, is_assumption = _container_evidence_metadata(raw)
    return CandidateInteractionRecord(
        left_candidate_id=left,
        right_candidate_id=right,
        kind=kind,
        annual_economic_benefit=benefit,
        source_ids=source_ids or benefit.source_ids,
        evidence_grade=evidence_grade or benefit.evidence_grade,
        is_assumption=is_assumption or benefit.is_assumption,
    )


def _load_profile_mapping(source: Mapping[str, Any] | Path | str | object) -> Mapping[str, Any]:
    if isinstance(source, Mapping):
        return cast(Mapping[str, Any], source)
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MapQuboValidationError(f"cannot load economic profile {path}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise MapQuboValidationError("economic profile root must be a JSON object")
        return cast(dict[str, Any], parsed)
    to_dict = getattr(source, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return cast(Mapping[str, Any], converted)
    raise MapQuboValidationError(
        "profile source must be a mapping, JSON path, or typed to_dict model"
    )


def _required_evidence(raw: Mapping[str, Any], keys: tuple[str, ...], label: str) -> EvidenceValue:
    value = _optional_evidence(raw, keys, label)
    if value is None:
        raise MapQuboValidationError(f"{label} is required")
    return value


def _optional_evidence(
    raw: Mapping[str, Any], keys: tuple[str, ...], label: str
) -> EvidenceValue | None:
    value = _first_present(raw, keys)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise MapQuboValidationError(f"{label} must be an evidence value object")
    record = cast(Mapping[str, Any], value)
    source_ids, evidence_grade, is_assumption = _evidence_metadata(record)
    estimate_raw = _first_present(record, ("estimate", "value"))
    if estimate_raw is None:
        raise MapQuboValidationError(f"{label}.estimate is required")
    estimate = _finite_float(estimate_raw, f"{label}.estimate")
    lower = _finite_float(record.get("lower", estimate), f"{label}.lower")
    upper = _finite_float(record.get("upper", estimate), f"{label}.upper")
    unit = _required_string(record, ("unit",), label)
    return EvidenceValue(
        estimate=estimate,
        lower=lower,
        upper=upper,
        unit=unit,
        evidence_grade=evidence_grade,
        source_ids=source_ids,
        is_assumption=is_assumption,
        price_year=_optional_int(record.get("price_year"), f"{label}.price_year"),
        notes=str(record.get("notes", "")),
    )


def _evidence_metadata(raw: Mapping[str, Any]) -> tuple[tuple[str, ...], str, bool]:
    source_value = raw.get("source_ids", [])
    if not isinstance(source_value, list):
        raise MapQuboValidationError("source_ids must be an array")
    source_ids = tuple(sorted(str(value) for value in source_value))
    grade = str(raw.get("evidence_grade", "unrated"))
    is_assumption = bool(raw.get("is_assumption", not source_ids))
    return source_ids, grade, is_assumption


def _container_evidence_metadata(
    raw: Mapping[str, Any],
) -> tuple[tuple[str, ...], str, bool]:
    if not any(key in raw for key in ("source_ids", "evidence_grade", "is_assumption")):
        return (), "", False
    return _evidence_metadata(raw)


def _least_evidence_grade(grades: Sequence[str]) -> str:
    if not grades:
        return "unrated"
    order = {"A": 0, "B": 1, "C": 2, "D": 3, "U": 4, "unrated": 5}
    return max(grades, key=lambda value: order.get(value, 5))


def _all_profile_evidence_values(
    candidates: Sequence[InvestmentCandidateRecord],
    od_pairs: Sequence[OdEconomicRecord],
    interactions: Sequence[CandidateInteractionRecord],
) -> tuple[EvidenceValue, ...]:
    values: list[EvidenceValue] = []
    for od_pair in od_pairs:
        values.extend(
            value
            for value in (
                od_pair.annual_trips,
                od_pair.persons_per_trip,
                od_pair.value_of_time,
                od_pair.reliability_value,
            )
            if value is not None
        )
    for candidate in candidates:
        values.append(candidate.capital_cost)
        if candidate.annual_operating_cost is not None:
            values.append(candidate.annual_operating_cost)
        for impact in candidate.od_impacts:
            values.extend(
                value
                for value in (
                    impact.route_exposure,
                    impact.annual_economic_benefit,
                    impact.annual_person_delay_saved_hours,
                    impact.annual_person_reliability_saved_hours,
                    impact.delay_reduction_seconds_per_trip,
                    impact.reliability_reduction_seconds_per_trip,
                    impact.annual_trips,
                    impact.persons_per_trip,
                )
                if value is not None
            )
    values.extend(item.annual_economic_benefit for item in interactions)
    return tuple(values)


def _required_od_value(
    value: EvidenceValue | None, od_pair_id: str, field_name: str
) -> EvidenceValue:
    if value is None:
        raise MapQuboValidationError(
            f"{od_pair_id}: {field_name} is required to annualize the marginal impact"
        )
    return value


def _require_non_negative(value: EvidenceValue, label: str) -> None:
    if value.lower < 0:
        raise MapQuboValidationError(f"{label} range must be non-negative")


def _require_unit(value: EvidenceValue, allowed: set[str], label: str) -> None:
    if value.unit not in allowed:
        raise MapQuboValidationError(
            f"{label} has unit {value.unit!r}; expected one of {sorted(allowed)}"
        )


def _require_rate_unit(value: EvidenceValue, label: str, currency: str) -> None:
    accepted = {
        f"{currency}/person_hour",
        f"{currency}/person-hour",
        "VND/person_hour",
        "VND/person-hour",
    }
    if value.unit not in accepted:
        raise MapQuboValidationError(
            f"{label} has unit {value.unit!r}; expected one of {sorted(accepted)}"
        )


def _required_object_list(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise MapQuboValidationError(f"{label} must be an array")
    result: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise MapQuboValidationError(f"{label}[{index}] must be an object")
        result.append(cast(Mapping[str, Any], item))
    return result


def _optional_mapping(value: object, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MapQuboValidationError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_string(raw: Mapping[str, Any], keys: tuple[str, ...], label: str) -> str:
    value = _first_present(raw, keys)
    if value is None or not str(value).strip():
        raise MapQuboValidationError(f"{label}.{keys[0]} is required")
    return str(value)


def _first_string(
    primary: Mapping[str, Any], secondary: Mapping[str, Any], keys: tuple[str, ...]
) -> str:
    value = _first_value(primary, secondary, keys)
    return "" if value is None else str(value)


def _first_value(
    primary: Mapping[str, Any], secondary: Mapping[str, Any], keys: tuple[str, ...]
) -> object | None:
    value = _first_present(primary, keys)
    return value if value is not None else _first_present(secondary, keys)


def _first_present(raw: Mapping[str, Any], keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


def _string_tuple(
    raw: Mapping[str, Any], keys: tuple[str, ...], *, preserve_order: bool = False
) -> tuple[str, ...]:
    value = _first_present(raw, keys)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise MapQuboValidationError(f"{keys[0]} must be an array")
    items = tuple(str(item) for item in value)
    return items if preserve_order else tuple(sorted(items))


def _location_id(nested: object, raw: Mapping[str, Any], prefix: str) -> str:
    if isinstance(nested, str) and nested:
        return nested
    if isinstance(nested, Mapping):
        nested_mapping = cast(Mapping[str, Any], nested)
        nested_id = _first_present(nested_mapping, ("building_id", "zone_id", "location_id", "id"))
        if nested_id is not None and str(nested_id):
            return str(nested_id)
    for key in (
        f"{prefix}_building_id",
        f"{prefix}_zone_id",
        f"{prefix}_location_id",
        f"{prefix}_id",
    ):
        direct = raw.get(key)
        if direct is not None and str(direct):
            return str(direct)
    raise MapQuboValidationError(f"OD pair {prefix} location id is required")


def _optional_int(value: object | None, label: str) -> int | None:
    if value is None:
        return None
    try:
        result = int(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise MapQuboValidationError(f"{label} must be an integer") from exc
    return result


def _finite_float(value: object, label: str) -> float:
    try:
        result = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise MapQuboValidationError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise MapQuboValidationError(f"{label} must be finite")
    return result


def _require_unique(values: Sequence[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise MapQuboValidationError(f"duplicate {label}: {sorted(duplicates)}")
