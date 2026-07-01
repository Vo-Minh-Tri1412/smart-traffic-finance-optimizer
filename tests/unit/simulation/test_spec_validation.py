from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.specs import SpecValidationError, district_spec_from_dict
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_sample_district_spec_loads() -> None:
    spec = load_district_spec(SPEC_PATH)

    assert spec.metadata.district_id == "toy_public_district_v1"
    assert len(spec.intersections) == 16
    assert "F_LOGISTICS_DELIVERY" in spec.flows
    assert "C_HOSPITAL_ACCESS" in spec.investment_candidates


def test_unknown_road_endpoint_fails() -> None:
    raw = copy.deepcopy(load_district_spec(SPEC_PATH).raw)
    raw["roads"][0]["to"] = "I_DOES_NOT_EXIST"

    with pytest.raises(SpecValidationError, match="unknown to intersection"):
        district_spec_from_dict(raw)


def test_heavy_truck_fixed_route_cannot_use_restricted_road() -> None:
    raw = copy.deepcopy(load_district_spec(SPEC_PATH).raw)
    raw["flows"].append(
        {
            "id": "F_BAD_TRUCK_ROUTE",
            "origin_zone": "Z_LOGISTICS",
            "destination_zone": "Z_INDUSTRIAL",
            "trip_purpose": "BAD_TRUCK_TEST",
            "departure_start": 0,
            "departure_end": 3600,
            "base_volume": 1,
            "vehicle_mix": {"HEAVY_TRUCK": 1.0},
            "route_policy": "FIXED_ROUTE",
            "fixed_route": ["R43"],
        }
    )

    with pytest.raises(SpecValidationError, match="restricted road R43"):
        district_spec_from_dict(raw)
