from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_quantum_hvtc.dashboard.app import create_app
from ai_quantum_hvtc.dashboard.config import DashboardConfig
from ai_quantum_hvtc.dashboard.services import SpecCache, run_simulation
from ai_quantum_hvtc.dashboard.store import RunStore

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")
SCENARIO_ID = "normal_weekday"


@pytest.fixture(scope="module")
def seeded_runs_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    runs_dir = tmp_path_factory.mktemp("dashboard-runs")
    store = RunStore(runs_dir)
    store.ensure_dirs()
    spec = SpecCache(SPEC_PATH).get()
    for controller_id in ("fixed_time", "rule_based"):
        result = run_simulation(
            spec=spec,
            scenario_id=SCENARIO_ID,
            controller_id=controller_id,
            engine_id="reference",
            seed=42,
        )
        store.save_run(
            result=result,
            spec=spec,
            district_id=spec.metadata.district_id,
            label="test seed",
        )
    return runs_dir


@pytest.fixture(scope="module")
def client(seeded_runs_dir: Path) -> Iterator[TestClient]:
    config = DashboardConfig(
        spec_path=SPEC_PATH,
        runs_dir=seeded_runs_dir,
        frontend_dist=seeded_runs_dir / "missing-frontend",
        seed_demo_runs=False,
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["district_id"] == "toy_public_district_v1"
    assert payload["run_count"] >= 2
    engines = {item["engine_id"]: item["available"] for item in payload["engines"]}
    assert engines["reference"] is True
    assert "sumo" in engines


def test_district_payload(client: TestClient) -> None:
    response = client.get("/api/district")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["id"] == "toy_public_district_v1"
    assert len(payload["zones"]) == 11
    assert len(payload["intersections"]) == 16
    assert len(payload["roads"]) == 48
    assert len(payload["scenarios"]) == 8
    assert len(payload["investment_candidates"]) == 6
    assert payload["finance_assumptions"]["value_of_time_vnd_per_hour"] == 120000


def test_runs_list_and_detail(client: TestClient) -> None:
    listing = client.get("/api/runs")
    assert listing.status_code == 200
    runs = listing.json()["runs"]
    assert len(runs) >= 2
    controllers = {run["controller_id"] for run in runs}
    assert {"fixed_time", "rule_based"} <= controllers

    run_id = runs[0]["run_id"]
    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["run_id"] == run_id
    assert len(payload["intersections"]) == 16
    assert payload["metrics"]["scenario_id"] == SCENARIO_ID


def test_trace_pagination(client: TestClient) -> None:
    runs = client.get("/api/runs").json()["runs"]
    run = runs[0]
    assert run["trace_frames"] > 0

    page = client.get(f"/api/runs/{run['run_id']}/trace", params={"offset": 0, "limit": 5})
    assert page.status_code == 200
    payload = page.json()
    assert payload["total_frames"] == run["trace_frames"]
    assert len(payload["frames"]) == min(5, run["trace_frames"])
    first_frame = payload["frames"][0]
    assert first_frame["schema_version"] == "simulation_trace_frame.v1"
    assert "traffic_lights" in first_frame

    tail = client.get(
        f"/api/runs/{run['run_id']}/trace",
        params={"offset": run["trace_frames"] - 1, "limit": 5},
    )
    assert len(tail.json()["frames"]) == 1


def test_trace_unknown_run(client: TestClient) -> None:
    response = client.get("/api/runs/does-not-exist/trace")
    assert response.status_code == 404


def test_coverage(client: TestClient) -> None:
    response = client.get("/api/runs/coverage")
    assert response.status_code == 200
    coverage = response.json()["coverage"]
    assert SCENARIO_ID in coverage["reference"]
    assert "fixed_time" in coverage["reference"][SCENARIO_ID]


def test_compare(client: TestClient) -> None:
    response = client.get(
        "/api/compare", params={"scenario_id": SCENARIO_ID, "engine_id": "reference"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline_controller_id"] == "fixed_time"
    controllers = [row["controller_id"] for row in payload["rows"]]
    assert controllers[0] == "fixed_time"
    assert "rule_based" in controllers
    for row in payload["rows"]:
        assert "waiting_time_saved_vs_fixed_seconds" in row
        assert "interpretation" in row


def test_compare_missing_scenario(client: TestClient) -> None:
    response = client.get(
        "/api/compare", params={"scenario_id": "missing", "engine_id": "reference"}
    )
    assert response.status_code == 404


def test_finance_optimize(client: TestClient) -> None:
    response = client.post(
        "/api/finance/optimize",
        json={
            "budget_vnd": 2_000_000,
            "algorithm": "greedy",
            "scenario_id": SCENARIO_ID,
            "controller_id": "rule_based",
            "engine_id": "reference",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["scores"]) == 6
    assert payload["total_cost_vnd"] <= 2_000_000
    assert payload["caveats"]
    assert payload["qubo"] is None
    selected_ids = {item["candidate_id"] for item in payload["selected"]}
    score_ids = {item["candidate_id"] for item in payload["scores"]}
    assert selected_ids <= score_ids


def test_finance_optimize_with_qubo(client: TestClient) -> None:
    response = client.post(
        "/api/finance/optimize",
        json={
            "budget_vnd": 1_500_000,
            "algorithm": "exact",
            "scenario_id": SCENARIO_ID,
            "controller_id": "rule_based",
            "engine_id": "reference",
            "include_qubo": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["qubo"] is not None
    assert len(payload["qubo"]) == 6


def test_launch_run_job(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        json={
            "scenario_id": "hospital_emergency",
            "controller_id": "fixed_time",
            "engine_id": "reference",
            "seed": 7,
            "label": "api test",
        },
    )
    assert response.status_code == 202
    job = response.json()
    job_id = job["job_id"]

    deadline = time.monotonic() + 60
    state = job["state"]
    run_id: str | None = None
    while time.monotonic() < deadline and state in {"queued", "running"}:
        time.sleep(0.1)
        polled = client.get(f"/api/jobs/{job_id}")
        assert polled.status_code == 200
        payload = polled.json()
        state = payload["state"]
        run_id = payload["run_id"]
    assert state == "succeeded"
    assert run_id

    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["scenario_id"] == "hospital_emergency"
    assert detail.json()["seed"] == 7


def test_launch_run_unknown_scenario(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        json={
            "scenario_id": "not-a-scenario",
            "controller_id": "fixed_time",
            "engine_id": "reference",
        },
    )
    assert response.status_code == 422


def test_delete_run(client: TestClient) -> None:
    launch = client.post(
        "/api/runs",
        json={
            "scenario_id": SCENARIO_ID,
            "controller_id": "fixed_time",
            "engine_id": "reference",
            "seed": 99,
            "label": "delete me",
        },
    )
    job_id = launch.json()["job_id"]
    deadline = time.monotonic() + 60
    run_id: str | None = None
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["state"] in {"succeeded", "failed"}:
            run_id = payload["run_id"]
            break
        time.sleep(0.1)
    assert run_id

    deleted = client.delete(f"/api/runs/{run_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/runs/{run_id}").status_code == 404
