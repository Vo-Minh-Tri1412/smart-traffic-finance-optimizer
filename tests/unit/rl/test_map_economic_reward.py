from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_quantum_hvtc.map_economics import (
    map_economic_profile_from_mapping,
    save_map_economic_profile,
)
from ai_quantum_hvtc.rl import build_sumo_map_economic_reward
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec
from scripts.training.rl_sumo_train import main


def _value(
    estimate: float,
    unit: str,
    *,
    price_year: int | None = None,
) -> dict[str, object]:
    return {
        "estimate": estimate,
        "lower": estimate,
        "upper": estimate,
        "unit": unit,
        "price_year": price_year,
        "evidence_grade": "D",
        "source_ids": ["TEST_ASSUMPTION"],
        "is_assumption": True,
    }


def _profile_mapping() -> dict[str, object]:
    return {
        "schema_version": "map_economic_profile.v1",
        "metadata": {
            "profile_id": "test_map_economics",
            "status": "draft",
            "map_project_id": "toy_public_district_v1",
            "currency": "VND",
            "price_year": 2025,
            "generated_at": "2026-09-04T00:00:00Z",
            "map_scope_status": "reviewed_roi",
            "source_net_sha256": "fixture-net",
            "semantic_overlay_sha256": "fixture-overlay",
            "caveats": ["Test-only assumptions."],
        },
        "sources": [
            {
                "source_id": "TEST_ASSUMPTION",
                "title": "Unit-test assumption",
                "source_type": "test_fixture",
            }
        ],
        "valuations": [
            {
                "valuation_id": "GLOBAL",
                "value_of_time": _value(36_000, "VND/person_hour", price_year=2025),
                "reliability_value": _value(0, "VND/person_hour", price_year=2025),
                "persons_per_trip": _value(1, "persons/trip"),
                "essential_service_multiplier": _value(1, "ratio"),
                "economic_flow_multiplier": _value(1, "ratio"),
            },
            {
                "valuation_id": "WORK_OD",
                "value_of_time": _value(36_000, "VND/person_hour", price_year=2025),
                "reliability_value": _value(0, "VND/person_hour", price_year=2025),
                "persons_per_trip": _value(1, "persons/trip"),
                "essential_service_multiplier": _value(1, "ratio"),
                "economic_flow_multiplier": _value(2, "ratio"),
            },
        ],
        "global_valuation_id": "GLOBAL",
        "buildings": [],
        "zones": [
            {
                "zone_id": "Z_RES_W",
                "name": "Residential fixture",
                "zone_type": "residential",
                "building_ids": [],
                "edge_ids": ["R01"],
                "valuation_id": "",
            },
            {
                "zone_id": "Z_PUBLIC",
                "name": "Office fixture",
                "zone_type": "office",
                "building_ids": [],
                "edge_ids": ["R01"],
                "valuation_id": "",
            },
        ],
        "edges": [
            {
                "edge_id": "R01",
                "zone_ids": ["Z_RES_W", "Z_PUBLIC"],
                "building_ids": [],
                "corridor_ids": [],
            }
        ],
        "corridors": [],
        "od_pairs": [
            {
                "od_pair_id": "F_WORK_COMMUTE",
                "valuation_id": "WORK_OD",
                "origin_zone_id": "Z_RES_W",
                "destination_zone_id": "Z_PUBLIC",
                "route_edge_ids": ["R01"],
                "corridor_ids": [],
                "annual_trips": None,
            }
        ],
        "investment_candidates": [],
        "reward_policy": {
            "normalization_vnd_per_step": _value(100, "VND", price_year=2025),
            "clip_min": -10,
            "clip_max": 10,
        },
        "coverage_policy": {
            "minimum_structural_edge_mapping_ratio": 0,
            "minimum_non_global_valuation_ratio": 0,
            "minimum_source_backed_valuation_ratio": 0,
            "require_demand_weighted_coverage": False,
            "minimum_demand_weighted_non_global_ratio": 0,
            "minimum_demand_weighted_source_backed_ratio": 0,
        },
        "coverage": None,
    }


class _LaneApi:
    def getLastStepVehicleIDs(self, _lane_id: str) -> list[str]:
        return ["F_WORK_COMMUTE.0"]


class _VehicleApi:
    def __init__(self) -> None:
        self.time_loss = 10.0

    def getTimeLoss(self, _vehicle_id: str) -> float:
        return self.time_loss

    def getTypeID(self, _vehicle_id: str) -> str:
        return "PRIVATE_CAR"

    def getRoute(self, _vehicle_id: str) -> tuple[str, ...]:
        return ("R01",)


class _SimulationApi:
    def __init__(self) -> None:
        self.time = 30.0

    def getTime(self) -> float:
        return self.time


def test_map_reward_monetizes_only_incremental_time_loss_and_keeps_vnd_ledger() -> None:
    profile = map_economic_profile_from_mapping(_profile_mapping())
    spec = load_district_spec("tests/fixtures/specs/toy_public_district_v1.json")
    vehicle = _VehicleApi()
    simulation = _SimulationApi()
    traffic_signal = SimpleNamespace(
        id="I07",
        lanes=["lane-a", "lane-b"],
        sumo=SimpleNamespace(lane=_LaneApi(), vehicle=vehicle, simulation=simulation),
    )
    reward = build_sumo_map_economic_reward(profile, spec)

    assert reward(traffic_signal) == 0.0

    vehicle.time_loss = 20.0
    simulation.time = 60.0
    assert reward(traffic_signal) == pytest.approx(-2.0)

    ledger = reward.last_step_by_signal["I07"]
    assert ledger.observed_vehicle_count == 1
    assert ledger.monetized_vehicle_count == 1
    assert ledger.raw_public_cost_vnd_estimate == pytest.approx(200.0)
    assert ledger.normalized_unclipped == pytest.approx(-2.0)
    assert ledger.resolution_counts == {"od_pair": 1}
    assert ledger.assumption_vehicle_count == 1

    simulation.time = 90.0
    assert reward(traffic_signal) == 0.0


def test_map_reward_detects_episode_time_reset_and_rebaselines() -> None:
    profile = map_economic_profile_from_mapping(_profile_mapping())
    spec = load_district_spec("tests/fixtures/specs/toy_public_district_v1.json")
    vehicle = _VehicleApi()
    simulation = _SimulationApi()
    traffic_signal = SimpleNamespace(
        id="I07",
        lanes=["lane-a"],
        sumo=SimpleNamespace(lane=_LaneApi(), vehicle=vehicle, simulation=simulation),
    )
    reward = build_sumo_map_economic_reward(profile, spec)
    reward(traffic_signal)
    vehicle.time_loss = 20.0
    simulation.time = 60.0
    assert reward(traffic_signal) < 0

    vehicle.time_loss = 1.0
    simulation.time = 0.0
    assert reward(traffic_signal) == 0.0
    assert reward.cumulative_public_cost_vnd_by_signal["I07"] == 0.0


def test_training_dry_run_reports_map_economic_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile_path = tmp_path / "map_economic_profile.json"
    save_map_economic_profile(map_economic_profile_from_mapping(_profile_mapping()), profile_path)

    exit_code = main(
        [
            "--spec",
            "tests/fixtures/specs/toy_public_district_v1.json",
            "--scenario",
            "normal_weekday",
            "--reward-profile",
            "configs/training/rl_reward_profile_v0.example.toml",
            "--map-economic-profile",
            str(profile_path),
            "--out-dir",
            str(tmp_path / "training"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"reward_mode": "map_economic_incremental"' in captured.out
    assert '"map_economic_profile_id": "test_map_economics"' in captured.out
    assert "map-economic production gate: profile status is not approved" in captured.out


def test_recreated_signal_starts_new_episode_at_same_time() -> None:
    profile = map_economic_profile_from_mapping(_profile_mapping())
    spec = load_district_spec("tests/fixtures/specs/toy_public_district_v1.json")
    reward = build_sumo_map_economic_reward(profile, spec)
    vehicle = _VehicleApi()
    connection = SimpleNamespace(lane=_LaneApi(), vehicle=vehicle, simulation=_SimulationApi())
    first = SimpleNamespace(id="I07", lanes=["a"], sumo=connection)
    reward(first)
    vehicle.time_loss = 20
    second = SimpleNamespace(id="I07", lanes=["a"], sumo=connection)
    assert reward(second) == 0
    vehicle.time_loss = 25
    assert reward(second) == pytest.approx(-1)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1])
def test_invalid_sumo_measurements_fail_closed(invalid: float) -> None:
    profile = map_economic_profile_from_mapping(_profile_mapping())
    spec = load_district_spec("tests/fixtures/specs/toy_public_district_v1.json")
    reward = build_sumo_map_economic_reward(profile, spec)
    vehicle = _VehicleApi()
    vehicle.time_loss = invalid
    signal = SimpleNamespace(
        id="I07",
        lanes=["a"],
        sumo=SimpleNamespace(lane=_LaneApi(), vehicle=vehicle, simulation=_SimulationApi()),
    )
    with pytest.raises(ValueError, match="finite non-negative"):
        reward(signal)


def test_map_mismatch_cannot_be_bypassed_by_draft_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = map_economic_profile_from_mapping(_profile_mapping())
    profile = replace(profile, metadata=replace(profile.metadata, map_project_id="other_map"))
    path = save_map_economic_profile(profile, tmp_path / "wrong_map.json")
    main(
        [
            "--spec",
            "tests/fixtures/specs/toy_public_district_v1.json",
            "--scenario",
            "normal_weekday",
            "--reward-profile",
            "configs/training/rl_reward_profile_v0.example.toml",
            "--map-economic-profile",
            str(path),
            "--allow-unreviewed-map-economics",
            "--out-dir",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert "does not match the training district_id" in capsys.readouterr().out
