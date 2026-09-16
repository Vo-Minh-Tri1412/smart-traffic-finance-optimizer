from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.map_economics import (
    MapEconomicProfileError,
    TripEconomicContext,
    assert_production_ready,
    audit_profile_coverage,
    load_map_economic_profile,
    map_economic_profile_from_mapping,
    resolve_trip_valuation,
)

TEMPLATE = Path("data/catalog/map_economic_profile.v1.template.json")


def test_template_loads_and_resolution_uses_specificity_order() -> None:
    profile = load_map_economic_profile(TEMPLATE)

    exact = resolve_trip_valuation(
        profile,
        TripEconomicContext(
            origin_building_id="BUILDING_A",
            destination_building_id="BUILDING_B",
            route_edge_ids=("EDGE_A", "EDGE_B"),
        ),
    )
    zone = resolve_trip_valuation(
        profile, TripEconomicContext(destination_building_id="BUILDING_B")
    )
    corridor = resolve_trip_valuation(profile, TripEconomicContext(route_edge_ids=("EDGE_A",)))
    global_value = resolve_trip_valuation(profile, TripEconomicContext())

    assert (exact.resolution_level, exact.matched_id) == ("od_pair", "OD_A_B")
    assert (zone.resolution_level, zone.matched_id) == ("zone", "ZONE_B")
    assert (corridor.resolution_level, corridor.matched_id) == (
        "corridor",
        "CORRIDOR_AB",
    )
    assert global_value.resolution_level == "global"


def test_assumption_only_demand_is_reported_and_blocked() -> None:
    profile = load_map_economic_profile(TEMPLATE)

    report = audit_profile_coverage(profile)
    reviewed_external = audit_profile_coverage(
        profile,
        demand_weights_by_od_pair={"OD_A_B": 10.0},
        demand_weights_are_reviewed=True,
    )

    assert report.demand_weighted_coverage_status == "assumption_only"
    assert reviewed_external.demand_weighted_coverage_status == "available_reviewed"
    assert report.source_backed_valuation_ratio == 0.0
    assert not report.production_gate_passed
    with pytest.raises(MapEconomicProfileError, match="production gate failed"):
        assert_production_ready(profile)


def test_empty_explicit_demand_weights_do_not_fall_back_to_profile_assumptions() -> None:
    profile = load_map_economic_profile(TEMPLATE)

    report = audit_profile_coverage(profile, demand_weights_by_od_pair={})

    assert report.demand_weighted_coverage_status == "unavailable"
    assert report.demand_weight_total is None


def test_loader_rejects_monetary_price_year_mismatch() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["valuations"][0]["value_of_time"]["price_year"] = 2010

    with pytest.raises(MapEconomicProfileError, match="price_year must match"):
        map_economic_profile_from_mapping(data)


def test_candidate_per_trip_impact_requires_explicit_annualization_inputs() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    impact = data["investment_candidates"][0]["od_impacts"][0]
    impact["annual_trips"] = None

    with pytest.raises(MapEconomicProfileError, match="needs annual_trips and persons_per_trip"):
        map_economic_profile_from_mapping(data)


def test_unknown_demand_remains_in_coverage_denominator() -> None:
    profile = load_map_economic_profile(TEMPLATE)
    report = audit_profile_coverage(
        profile,
        demand_weights_by_od_pair={"OD_A_B": 10.0, "UNMAPPED_OD": 90.0},
        demand_weights_are_reviewed=True,
    )
    assert report.demand_weight_total == 100.0
    assert report.demand_weighted_non_global_ratio == 0.1
    assert report.demand_weighted_source_backed_ratio == 0.0


def test_negative_marginal_savings_are_valid_but_overlapping_totals_are_not() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    impact = data["investment_candidates"][0]["od_impacts"][0]
    delay = impact["delay_reduction_seconds_per_trip"]
    delay.update(estimate=-10.0, lower=-20.0, upper=0.0)
    assert map_economic_profile_from_mapping(data).investment_candidates
    impact["annual_person_delay_saved_hours"] = {
        **delay,
        "unit": "person_hours/year",
        "price_year": None,
    }
    with pytest.raises(MapEconomicProfileError, match="one marginal benefit representation"):
        map_economic_profile_from_mapping(data)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_economic_inputs_and_demand_are_rejected(value: float) -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["valuations"][0]["value_of_time"]["estimate"] = value
    with pytest.raises(MapEconomicProfileError, match="finite"):
        map_economic_profile_from_mapping(data)
    with pytest.raises(MapEconomicProfileError, match="finite"):
        audit_profile_coverage(
            load_map_economic_profile(TEMPLATE), demand_weights_by_od_pair={"OD_A_B": value}
        )


def test_assumption_grade_cannot_be_relabelled_as_source_backed() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["valuations"][0]["value_of_time"]["is_assumption"] = False
    with pytest.raises(MapEconomicProfileError, match="must be marked as an assumption"):
        map_economic_profile_from_mapping(data)


@pytest.mark.parametrize("route", [("EDGE_A",), ("EDGE_B", "EDGE_A")])
def test_partial_or_reversed_route_does_not_match_declared_od(route: tuple[str, ...]) -> None:
    profile = load_map_economic_profile(TEMPLATE)
    resolved = resolve_trip_valuation(
        profile,
        TripEconomicContext(
            origin_building_id="BUILDING_A",
            destination_building_id="BUILDING_B",
            route_edge_ids=route,
        ),
    )
    assert resolved.resolution_level == "zone"
