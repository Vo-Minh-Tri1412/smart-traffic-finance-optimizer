from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from ai_quantum_hvtc.map_economics import map_economic_profile_from_mapping
from ai_quantum_hvtc.public_finance.map_qubo import (
    MapQuboConfig,
    MapQuboValidationError,
    build_map_aware_qubo,
    build_qubo_run_manifest,
    evaluate_portfolio,
    load_map_economic_profile,
    solve_map_qubo_exact,
)
from scripts.finance.solve_map_qubo import main as solve_cli


def _value(
    estimate: float,
    unit: str,
    *,
    lower: float | None = None,
    upper: float | None = None,
    assumption: bool = False,
) -> dict[str, Any]:
    return {
        "estimate": estimate,
        "lower": estimate if lower is None else lower,
        "upper": estimate if upper is None else upper,
        "unit": unit,
        "price_year": 2025 if unit.startswith("VND") else None,
        "evidence_grade": "D" if assumption else "B",
        "source_ids": ["SRC-ASSUMPTION" if assumption else "SRC-MEASURED"],
        "is_assumption": assumption,
        "notes": "test evidence",
    }


def _profile(
    *,
    budget_case: str = "normal",
    interaction_kind: str | None = None,
    interaction_value: float = 0.0,
) -> dict[str, Any]:
    cost_a = 250.0 if budget_case == "a_infeasible" else 100.0
    candidates = [
        {
            "candidate_id": "A",
            "name": "Junction A",
            "junction_ids": ["J-A"],
            "edge_ids": ["E-1"],
            "corridor_ids": ["C-WEST"],
            "capital_cost_vnd": _value(cost_a, "VND"),
            "annual_operating_cost_vnd": _value(0.0, "VND"),
            "od_impacts": [
                {
                    "od_pair_id": "OD-HOME-OFFICE",
                    "route_exposure_fraction": _value(1.0, "ratio"),
                    "annual_person_delay_saved_hours": _value(
                        2.0,
                        "person_hours/year",
                    ),
                    "derivation_method": "explicit_od_impact",
                }
            ],
        },
        {
            "candidate_id": "B",
            "name": "Junction B",
            "junction_ids": ["J-B"],
            "edge_ids": ["E-2"],
            "corridor_ids": ["C-WEST"],
            "capital_cost_vnd": _value(100.0, "VND"),
            "annual_operating_cost_vnd": _value(0.0, "VND"),
            "od_impacts": [
                {
                    "od_pair_id": "OD-HOME-SHOP",
                    "route_exposure_fraction": _value(1.0, "ratio"),
                    "delay_reduction_seconds_per_trip": _value(36.0, "seconds/trip"),
                    "annual_trips": _value(100.0, "trips/year"),
                    "persons_per_trip": _value(1.0, "persons/trip"),
                    "derivation_method": "explicit_od_impact",
                }
            ],
        },
    ]
    profile: dict[str, Any] = {
        "schema_version": "map_economic_profile.v1",
        "metadata": {
            "profile_id": "DISTRICT7-ECON-TEST",
            "currency": "VND",
            "price_year": 2025,
        },
        "sources": [
            {"source_id": "SRC-MEASURED", "title": "Measured test fixture"},
            {"source_id": "SRC-ASSUMPTION", "title": "Assumption test fixture"},
        ],
        "valuations": [
            {
                "valuation_id": "VAL-WORK",
                "value_of_time": _value(100.0, "VND/person_hour"),
                "reliability_value": _value(20.0, "VND/person_hour"),
                "persons_per_trip": _value(1.0, "persons/trip"),
                "essential_service_multiplier": _value(1.0, "ratio"),
                "economic_flow_multiplier": _value(1.0, "ratio"),
            }
        ],
        "od_pairs": [
            {
                "od_pair_id": "OD-HOME-OFFICE",
                "valuation_id": "VAL-WORK",
                "origin_building_id": "BLD-HOME",
                "destination_building_id": "BLD-OFFICE",
                "route_edge_ids": ["E-1", "E-2"],
                "corridor_ids": ["C-WEST"],
                "annual_trips": _value(100.0, "trips/year"),
            },
            {
                "od_pair_id": "OD-HOME-SHOP",
                "valuation_id": "VAL-WORK",
                "origin_zone_id": "ZONE-HOME",
                "destination_zone_id": "ZONE-SHOP",
                "route_edge_ids": ["E-2"],
                "corridor_ids": ["C-WEST"],
                "annual_trips": _value(100.0, "trips/year"),
            },
        ],
        "investment_candidates": candidates,
        "coverage": {
            "production_gate_passed": False,
            "non_global_valuation_ratio": 1.0,
        },
    }
    if interaction_kind is not None:
        profile["candidate_interactions"] = [
            {
                "left_candidate_id": "A",
                "right_candidate_id": "B",
                "kind": interaction_kind,
                "annual_economic_benefit_vnd": _value(interaction_value, "VND"),
            }
        ]
    return profile


def _config(*, budget: float = 100.0, penalty: float | None = None) -> MapQuboConfig:
    return MapQuboConfig(
        budget_vnd=budget,
        benefit_present_value_factor=1.0,
        operating_cost_present_value_factor=0.0,
        capital_cost_weight=1.0,
        risk_mode="estimate",
        budget_unit_vnd=50.0,
        objective_scale_vnd=1.0,
        budget_penalty=penalty,
    )


def _typed_profile() -> object:
    data = _profile()
    data["metadata"].update(
        {
            "status": "draft",
            "map_project_id": "district7-test",
            "generated_at": "2026-09-04T00:00:00Z",
            "map_scope_status": "reviewed_roi",
            "source_net_sha256": "fixture-net",
            "semantic_overlay_sha256": "fixture-overlay",
            "caveats": ["test only"],
        }
    )
    for source in data["sources"]:
        source["source_type"] = "test_fixture"
    data["global_valuation_id"] = "VAL-WORK"
    data["buildings"] = [
        {
            "building_id": "BLD-HOME",
            "name": "Home",
            "entity_kind": "residential",
            "zone_id": "ZONE-HOME",
            "edge_ids": ["E-1"],
            "mapping_method": "exact_anchor",
            "nearest_edge_distance_m": 0.0,
            "demand_enabled": True,
            "valuation_id": "VAL-WORK",
        },
        {
            "building_id": "BLD-OFFICE",
            "name": "Office",
            "entity_kind": "office",
            "zone_id": "ZONE-OFFICE",
            "edge_ids": ["E-2"],
            "mapping_method": "exact_anchor",
            "nearest_edge_distance_m": 0.0,
            "demand_enabled": True,
            "valuation_id": "VAL-WORK",
        },
    ]
    data["zones"] = [
        {
            "zone_id": "ZONE-HOME",
            "name": "Home zone",
            "zone_type": "residential",
            "building_ids": ["BLD-HOME"],
            "edge_ids": ["E-1"],
            "valuation_id": "VAL-WORK",
        },
        {
            "zone_id": "ZONE-OFFICE",
            "name": "Office zone",
            "zone_type": "office",
            "building_ids": ["BLD-OFFICE"],
            "edge_ids": ["E-2"],
            "valuation_id": "VAL-WORK",
        },
        {
            "zone_id": "ZONE-SHOP",
            "name": "Shop zone",
            "zone_type": "commercial",
            "building_ids": [],
            "edge_ids": ["E-2"],
            "valuation_id": "VAL-WORK",
        },
    ]
    data["edges"] = [
        {
            "edge_id": "E-1",
            "zone_ids": ["ZONE-HOME"],
            "building_ids": ["BLD-HOME"],
            "corridor_ids": ["C-WEST"],
        },
        {
            "edge_id": "E-2",
            "zone_ids": ["ZONE-OFFICE", "ZONE-SHOP"],
            "building_ids": ["BLD-OFFICE"],
            "corridor_ids": ["C-WEST"],
        },
    ]
    data["corridors"] = [
        {
            "corridor_id": "C-WEST",
            "name": "West corridor",
            "edge_ids": ["E-1", "E-2"],
            "zone_ids": ["ZONE-HOME", "ZONE-OFFICE", "ZONE-SHOP"],
            "valuation_id": "VAL-WORK",
        }
    ]
    data["reward_policy"] = {
        "normalization_vnd_per_step": _value(100.0, "VND"),
        "clip_min": -10.0,
        "clip_max": 10.0,
    }
    data["coverage_policy"] = {
        "minimum_structural_edge_mapping_ratio": 0.0,
        "minimum_non_global_valuation_ratio": 0.0,
        "minimum_source_backed_valuation_ratio": 0.0,
        "require_demand_weighted_coverage": False,
        "minimum_demand_weighted_non_global_ratio": 0.0,
        "minimum_demand_weighted_source_backed_ratio": 0.0,
    }
    data["coverage"] = None
    return map_economic_profile_from_mapping(data)


def test_profile_resolves_od_valuation_and_building_specific_benefit() -> None:
    profile = load_map_economic_profile(_profile())
    build = build_map_aware_qubo(profile, _config())

    candidate_a = build.candidate_coefficients[0]
    candidate_b = build.candidate_coefficients[1]

    assert candidate_a.candidate_id == "A"
    assert candidate_a.annual_marginal_benefit_vnd == pytest.approx(200.0)
    assert candidate_a.contributions[0].origin_id == "BLD-HOME"
    assert candidate_a.contributions[0].destination_id == "BLD-OFFICE"
    assert candidate_b.annual_marginal_benefit_vnd == pytest.approx(100.0)
    assert candidate_b.contributions[0].origin_id == "ZONE-HOME"


def test_loader_accepts_canonical_typed_profile_to_dict_contract() -> None:
    profile = load_map_economic_profile(_typed_profile())
    build = build_map_aware_qubo(profile, _config())

    assert [item.candidate_id for item in build.candidate_coefficients] == ["A", "B"]
    assert build.candidate_coefficients[0].annual_marginal_benefit_vnd == pytest.approx(200.0)


def test_route_edges_preserve_travel_order_and_revisited_edges() -> None:
    data = _profile()
    data["od_pairs"][0]["route_edge_ids"] = ["E-2", "E-1", "E-2"]
    loaded = load_map_economic_profile(data)
    assert loaded.od_pairs[0].route_edge_ids == ("E-2", "E-1", "E-2")


def test_exact_solver_obeys_capital_budget() -> None:
    build = build_map_aware_qubo(load_map_economic_profile(_profile()), _config())

    solution = solve_map_qubo_exact(build)

    assert solution.selected_candidate_ids == ("A",)
    assert solution.portfolio.budget_feasible
    assert solution.portfolio.capital_cost_vnd == 100.0
    assert solution.energy == pytest.approx(-100.0)


def test_exact_solver_rejects_profitable_but_infeasible_candidate() -> None:
    profile_data = _profile(budget_case="a_infeasible")
    profile_data["investment_candidates"] = profile_data["investment_candidates"][:1]
    profile_data["investment_candidates"][0]["od_impacts"][0]["annual_person_delay_saved_hours"] = (
        _value(10.0, "person_hours/year")
    )
    build = build_map_aware_qubo(load_map_economic_profile(profile_data), _config())

    solution = solve_map_qubo_exact(build)

    assert solution.selected_candidate_ids == ()
    assert solution.portfolio.budget_feasible


def test_overlap_interaction_prevents_double_counting() -> None:
    build = build_map_aware_qubo(
        load_map_economic_profile(_profile(interaction_kind="overlap", interaction_value=-250.0)),
        _config(budget=200.0),
    )

    solution = solve_map_qubo_exact(build)

    assert solution.selected_candidate_ids == ("A",)
    assert evaluate_portfolio(build, ("A", "B")).interaction_benefit_vnd == -250.0


def test_complementarity_interaction_can_make_pair_optimal() -> None:
    profile_data = _profile(interaction_kind="complementarity", interaction_value=180.0)
    profile_data["investment_candidates"][0]["od_impacts"][0]["annual_person_delay_saved_hours"] = (
        _value(0.5, "person_hours/year")
    )
    profile_data["investment_candidates"][1]["od_impacts"][0][
        "delay_reduction_seconds_per_trip"
    ] = _value(9.0, "seconds/trip")
    build = build_map_aware_qubo(
        load_map_economic_profile(profile_data),
        _config(budget=200.0),
    )

    solution = solve_map_qubo_exact(build)

    assert solution.selected_candidate_ids == ("A", "B")


def test_unsafe_user_budget_penalty_is_rejected() -> None:
    with pytest.raises(MapQuboValidationError, match="does not dominate"):
        build_map_aware_qubo(load_map_economic_profile(_profile()), _config(penalty=1.0))


def test_matrix_is_deterministic_for_reordered_profile_rows() -> None:
    original = _profile(interaction_kind="complementarity", interaction_value=10.0)
    reordered = deepcopy(original)
    reordered["investment_candidates"].reverse()
    reordered["od_pairs"].reverse()

    first = build_map_aware_qubo(load_map_economic_profile(original), _config(budget=200.0))
    second = build_map_aware_qubo(load_map_economic_profile(reordered), _config(budget=200.0))

    assert first.model.to_dict() == second.model.to_dict()
    assert (
        solve_map_qubo_exact(first).selected_candidate_ids
        == solve_map_qubo_exact(second).selected_candidate_ids
    )


def test_manifest_carries_coverage_provenance_and_claim_status() -> None:
    build = build_map_aware_qubo(load_map_economic_profile(_profile()), _config())
    solution = solve_map_qubo_exact(build)

    manifest = build_qubo_run_manifest(build, solution, run_id="QUBO-TEST-001")

    assert manifest["schema_version"] == "map_aware_qubo_run.v1"
    assert (
        manifest["input_profile"]["economic_calibration_coverage"]["production_gate_passed"]
        is False
    )
    assert manifest["objective_contract"]["gross_trip_value_used"] is False
    assert manifest["candidate_coefficients"][0]["contributions"][0]["source_ids"]
    assert manifest["claim_status"] == "decision_support_only_requires_economic_review"


def test_missing_annualization_inputs_are_rejected() -> None:
    profile_data = _profile()
    impact = profile_data["investment_candidates"][1]["od_impacts"][0]
    impact.pop("annual_trips")
    profile_data["od_pairs"][1]["annual_trips"] = None

    profile = load_map_economic_profile(profile_data)
    with pytest.raises(MapQuboValidationError, match="annual_trips is required"):
        build_map_aware_qubo(profile, _config())


def test_cli_emits_versioned_manifest(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    output_path = tmp_path / "run" / "manifest.json"
    config_path = tmp_path / "qubo.yaml"
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    config_path.write_text(
        "\n".join(
            (
                "schema_version: map_aware_qubo_config.v1",
                'run_id: "CLI-TEST"',
                f"profile: {json.dumps(str(profile_path))}",
                f"output: {json.dumps(str(output_path))}",
                "budget_vnd: 100",
                "benefit_present_value_factor: 1",
                "operating_cost_present_value_factor: 0",
                "budget_unit_vnd: 50",
                "objective_scale_vnd: 1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = solve_cli(["--config", str(config_path)])

    assert exit_code == 0
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "map_aware_qubo_run.v1"
    assert manifest["solution"]["selected_candidate_ids"] == ["A"]


@pytest.mark.parametrize("bad", [0.5, 1.9, "1", -1, 2, None])
def test_energy_rejects_non_binary_assignments(bad: Any) -> None:
    build = build_map_aware_qubo(load_map_economic_profile(_profile()), _config())
    with pytest.raises(MapQuboValidationError, match="binary"):
        build.model.energy({"A": bad})


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("conservative", -600.0),
        ("estimate", -100.0),
        ("optimistic", -10.0),
    ],
)
def test_signed_delay_intervals_include_adverse_rate_and_exposure(
    mode: Any,
    expected: float,
) -> None:
    data = _profile()
    impact = data["investment_candidates"][0]["od_impacts"][0]
    impact["annual_person_delay_saved_hours"] = _value(
        -2.0,
        "person_hours/year",
        lower=-3.0,
        upper=-1.0,
    )
    impact["route_exposure_fraction"] = _value(0.5, "ratio", lower=0.2, upper=1.0)
    data["valuations"][0]["value_of_time"] = _value(
        100.0,
        "VND/person_hour",
        lower=50.0,
        upper=200.0,
    )
    build = build_map_aware_qubo(
        load_map_economic_profile(data),
        replace(_config(), risk_mode=mode),
    )
    assert build.candidate_coefficients[0].annual_marginal_benefit_vnd == expected
    assert "A" not in solve_map_qubo_exact(build).selected_candidate_ids


@pytest.mark.parametrize(
    "extra",
    [
        {"delay_reduction_seconds_per_trip": _value(1.0, "seconds/trip")},
        {"annual_economic_benefit_vnd": _value(1.0, "VND")},
    ],
)
def test_ambiguous_duplicate_benefit_channels_rejected(extra: dict[str, Any]) -> None:
    data = _profile()
    data["investment_candidates"][0]["od_impacts"][0].update(extra)
    with pytest.raises(MapQuboValidationError, match="double counting|ambiguous"):
        load_map_economic_profile(data)


def test_every_qubo_assignment_matches_explicit_budget_objective() -> None:
    build = build_map_aware_qubo(
        load_map_economic_profile(_profile(interaction_kind="overlap", interaction_value=-20)),
        _config(budget=250),
    )
    model = build.model
    energies = []
    for bits in product((0, 1), repeat=len(model.variables)):
        assignment = dict(zip(model.variables, bits, strict=True))
        selected = [name for name in model.candidate_variables if assignment[name]]
        portfolio = evaluate_portfolio(build, selected)
        spent = sum(
            c.budget_cost_units * assignment[c.candidate_id] for c in build.candidate_coefficients
        )
        slack = sum(
            w * assignment[name]
            for name, w in zip(model.slack_variables, model.slack_weights, strict=True)
        )
        expected = (
            -portfolio.net_public_value_vnd / build.config.objective_scale_vnd
            + model.budget_penalty * (spent + slack - model.budget_units) ** 2
        )
        assert model.energy(assignment) == pytest.approx(expected)
        energies.append(expected)
    assert solve_map_qubo_exact(build).energy == pytest.approx(min(energies))


def test_budget_decimal_rounding_never_admits_tiny_overspend() -> None:
    data = _profile()
    data["investment_candidates"][0]["capital_cost_vnd"] = _value(100.00000000001, "VND")
    build = build_map_aware_qubo(load_map_economic_profile(data), _config())
    assert build.candidate_coefficients[0].budget_cost_units == 3
    assert "A" not in solve_map_qubo_exact(build).selected_candidate_ids
    smaller = build_map_aware_qubo(
        load_map_economic_profile(_profile()), _config(budget=99.99999999999)
    )
    assert smaller.model.budget_units == 1


def test_cli_accepts_checked_in_canonical_template(tmp_path: Path) -> None:
    output = tmp_path / "template_qubo.json"
    assert (
        solve_cli(
            [
                "--profile",
                "data/catalog/map_economic_profile.v1.template.json",
                "--output",
                str(output),
                "--run-id",
                "TEMPLATE-SMOKE",
                "--budget-vnd",
                "10",
                "--budget-unit-vnd",
                "1",
                "--benefit-present-value-factor",
                "1",
                "--operating-cost-present-value-factor",
                "1",
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["solution"]["portfolio"][
        "budget_feasible"
    ]
