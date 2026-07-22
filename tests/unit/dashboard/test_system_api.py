from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_quantum_hvtc.dashboard.app import create_app
from ai_quantum_hvtc.dashboard.config import DashboardConfig

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")
REWARD_PROFILE_PATH = Path("configs/training/rl_reward_profile_v0.example.toml")


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    runs_dir = tmp_path_factory.mktemp("system-runs")
    config = DashboardConfig(
        spec_path=SPEC_PATH,
        runs_dir=runs_dir,
        frontend_dist=runs_dir / "missing-frontend",
        reward_profile_path=REWARD_PROFILE_PATH,
        models_dir=runs_dir / "empty-models",
        seed_demo_runs=False,
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_pipeline(client: TestClient) -> None:
    response = client.get("/api/system/pipeline")
    assert response.status_code == 200
    payload = response.json()
    stage_ids = {stage["id"] for stage in payload["stages"]}
    assert {"engine", "scoring", "optimizer", "rl", "render"} <= stage_ids
    assert set(payload["status_legend"]) == {"implemented", "partial", "scaffold", "planned"}
    rl_stage = next(stage for stage in payload["stages"] if stage["id"] == "rl")
    assert rl_stage["status"] == "scaffold"
    for stage in payload["stages"]:
        assert stage["layer"] in payload["layers"]


def test_rl_reflects_draft_gate(client: TestClient) -> None:
    response = client.get("/api/system/rl")
    assert response.status_code == 200
    payload = response.json()
    # No trained policy artifact under an empty models dir.
    assert payload["policy_trained"] is False
    assert payload["training_ready"] is False
    # Draft reward + pending hard constraint should both block training.
    assert len(payload["blockers"]) >= 2
    assert any("approved" in blocker for blocker in payload["blockers"])

    profile = payload["reward_profile"]
    assert profile is not None
    assert profile["profile_id"] == "reward_profile_v0_draft"
    assert profile["status"] == "draft"
    base = {row["key"]: row["weight"] for row in profile["base_weights"]}
    assert base["waiting_time"] == 1.0
    vehicle = {row["key"]: row["weight"] for row in profile["vehicle_type_weights"]}
    assert vehicle["AMBULANCE"] == 20.0
    constraint_ids = {item["id"] for item in profile["hard_constraints"]}
    assert "emergency_vehicle_preemption" in constraint_ids

    assert payload["observation_space"]["version"] == "v1"
    assert "traffic_pressure" in payload["observation_space"]["feature_groups"]
    assert payload["action_space"]["action_type"] == "traffic_signal_phase_selection"
    assert payload["training_config"]["present"] is True
    assert payload["training_config"]["algorithm"] == "PPO"


def test_data(client: TestClient) -> None:
    response = client.get("/api/system/data")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_store"]["run_count"] == 0
    stream_ids = {stream["id"] for stream in payload["streams"]}
    assert {"sumo", "rl_sumo", "yolo", "finance"} <= stream_ids
    assert payload["dvc"]["registry_sheet"] == "00_Data_Model_Run_Registry"
    reward_config = next(
        item
        for item in payload["configs"]
        if item["name"].endswith("rl_reward_profile_v0.example.toml")
    )
    assert reward_config["present"] is True


def test_state(client: TestClient) -> None:
    response = client.get("/api/system/state")
    assert response.status_code == 200
    payload = response.json()
    names = {check["name"] for check in payload["checks"]}
    assert "District spec" in names
    assert "SUMO runtime" in names
    assert payload["fail_count"] == 0
    total = payload["ok_count"] + payload["warn_count"] + payload["fail_count"]
    assert total == len(payload["checks"])


def test_districts_registry(client: TestClient) -> None:
    response = client.get("/api/districts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_district_id"] == "toy_public_district_v1"
    by_id = {entry["district_id"]: entry for entry in payload["districts"]}
    assert by_id["toy_public_district_v1"]["active"] is True
    # Reserved slots keep room for real maps without being wired in.
    planned = [entry for entry in payload["districts"] if entry["status"] == "planned"]
    assert len(planned) >= 1
    assert all(entry["active"] is False for entry in planned)
