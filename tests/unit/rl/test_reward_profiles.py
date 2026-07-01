from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ai_quantum_hvtc.rl import (
    build_sumo_rl_reward,
    load_reward_profile,
    training_blockers,
    validate_reward_profile_against_spec,
)
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/minh_khai_district_v1.json")
PROFILE_PATH = Path("configs/training/rl_reward_profile_v0.example.toml")


class _FakeLane:
    def getLastStepVehicleIDs(self, _lane_id: str) -> list[str]:
        return ["F_MEDICAL_EMERGENCY_AMBULANCE.0", "F_WORK_COMMUTE_PRIVATE_CAR.0"]


class _FakeVehicle:
    def getTypeID(self, vehicle_id: str) -> str:
        if "AMBULANCE" in vehicle_id:
            return "AMBULANCE"
        return "PRIVATE_CAR"

    def getAccumulatedWaitingTime(self, vehicle_id: str) -> float:
        if "AMBULANCE" in vehicle_id:
            return 10.0
        return 10.0


class _FakeSimulation:
    def getTime(self) -> float:
        return 100.0


class _FakeTrafficSignal:
    id = "I06"
    lanes = ["lane_0"]
    sumo = SimpleNamespace(
        lane=_FakeLane(),
        vehicle=_FakeVehicle(),
        simulation=_FakeSimulation(),
    )

    def get_total_queued(self) -> int:
        return 2

    def get_pressure(self) -> float:
        return 3.0

    def get_average_speed(self) -> float:
        return 0.5


def test_example_reward_profile_matches_spec() -> None:
    spec = load_district_spec(SPEC_PATH)
    profile = load_reward_profile(PROFILE_PATH)

    assert validate_reward_profile_against_spec(profile, spec) == []
    assert profile.status == "draft"


def test_training_blockers_keep_draft_and_pending_hard_constraints_from_training() -> None:
    spec = load_district_spec(SPEC_PATH)
    profile = load_reward_profile(PROFILE_PATH)

    blockers = training_blockers(profile, spec)

    assert any("requires 'approved'" in blocker for blocker in blockers)
    assert any("hard constraints require" in blocker for blocker in blockers)


def test_configured_reward_weights_priority_vehicles_more_heavily() -> None:
    spec = load_district_spec(SPEC_PATH)
    profile = load_reward_profile(PROFILE_PATH)
    reward_fn = build_sumo_rl_reward(profile, spec, scenario_id="hospital_emergency")

    reward = reward_fn(_FakeTrafficSignal())

    assert isinstance(reward, float)
    assert reward < -1.0


def test_reward_fn_accepts_sumolike_object() -> None:
    spec = load_district_spec(SPEC_PATH)
    profile = load_reward_profile(PROFILE_PATH)
    reward_fn = build_sumo_rl_reward(profile, spec, scenario_id="normal_weekday")

    reward: Any = reward_fn(_FakeTrafficSignal())

    assert isinstance(reward, float)
