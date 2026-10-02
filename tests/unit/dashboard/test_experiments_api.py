from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import ai_quantum_hvtc.experiments.store as experiment_store
from ai_quantum_hvtc.dashboard.app import create_app
from ai_quantum_hvtc.dashboard.config import DashboardConfig, config_from_env
from ai_quantum_hvtc.experiments.store import ExperimentError, read_json, seal_run
from tests.unit.experiments.test_store import _create_run, _make_fixture

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")
DEMAND_STATUS_KEYS = (
    "arrived",
    "unfinished",
    "vaporized",
    "not_routed",
    "not_observed",
    "unverified",
)
ACCOUNTING_LIMITATIONS = [
    "Vehicle and simulator event counters are not person or occupancy metrics.",
    "These outputs do not establish action-safety validation or research acceptance.",
]


def _accounting_document(fixture: object, run_id: str) -> dict[str, object]:
    # The fixture helper's manifest is the identity source bound into the output.
    experiment = fixture.experiment  # type: ignore[attr-defined]
    run = read_json(experiment / "runs" / run_id / "run.json")
    return {
        "schema_version": "runtime_trip_accounting.v1",
        "experiment_id": run["experiment_id"],
        "run_id": run["run_id"],
        "run_sha256": run["content_sha256"],
        "execution_status": "debug_simulation_finished",
        "evidence_scope": "managed_debug_runtime_accounting_only",
        "source_inputs": {"private": {"path": "D:/private/input.json"}},
        "source_outputs": {"private": {"path": "D:/private/output.xml"}},
        "demand_accounting": {
            "status": "partial",
            "scope": "per_intended_requested_vehicle_trip",
            "reason": "one_or_more_sources_or_trip_rows_unverified",
            "intended_trip_count": None,
            "raw_ledger_row_count": 2,
            "status_counts": {key: None for key in DEMAND_STATUS_KEYS},
            "tripinfo_observed_count": None,
            "tripinfo_unfinished_requested": True,
            "trips": [{"trip_id": "sensitive-trip-detail"}],
            "errors": ["D:/private/ledger.json"],
        },
        "aggregate_simulation_accounting": {
            "scope": "whole_simulation_vehicle_and_event_counters",
            "status": "partial",
            "summary": {
                "status": "partial",
                "source": "summary.xml final step",
                "final_step_time_seconds": 125.5,
                "loaded": None,
                "inserted": 4,
                "waiting": None,
                "arrived": 3,
                "running": 0,
                "ended": 3,
                "error": "D:/private/summary.xml",
            },
            "statistic": {
                "status": "partial",
                "source": "statistic.xml",
                "total_teleports": 0,
                "safety_collisions": None,
                "error": "D:/private/statistic.xml",
            },
            "limitations": [*ACCOUNTING_LIMITATIONS, "D:/private/limitation.txt"],
        },
    }


def _write_accounting_run(
    fixture: object,
    *,
    run_id: str = "run_accounting",
    include_role: bool = True,
    sealed: bool = True,
) -> tuple[Path, Path | None, dict[str, object]]:
    expected_outputs = (
        {"runtime_accounting": "runtime_accounting.json"}
        if include_role
        else {"metrics": "metrics/result.json"}
    )
    run_dir = _create_run(fixture, run_id=run_id, expected_outputs=expected_outputs)
    document = _accounting_document(fixture, run_id)
    output: Path | None
    if include_role:
        output = run_dir / "runtime_accounting.json"
        output.write_text(json.dumps(document), encoding="utf-8")
    else:
        output = None
        metric_output = run_dir / "metrics" / "result.json"
        metric_output.parent.mkdir(parents=True)
        metric_output.write_text('{"ok": true}\n', encoding="utf-8")
    if sealed:
        seal_run(run_dir)
    return run_dir, output, document


def _config(tmp_path: Path, experiments_dir: Path | None) -> DashboardConfig:
    return DashboardConfig(
        spec_path=SPEC_PATH,
        runs_dir=tmp_path / "legacy-dashboard-runs",
        frontend_dist=tmp_path / "missing-frontend",
        seed_demo_runs=False,
        experiments_dir=experiments_dir,
    )


def test_experiments_directory_is_opt_in_environment_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("AIQ_DASHBOARD_EXPERIMENTS_DIR", raising=False)
    assert config_from_env().experiments_dir is None

    configured = tmp_path / "explicit-experiments"
    monkeypatch.setenv("AIQ_DASHBOARD_EXPERIMENTS_DIR", str(configured))
    assert config_from_env().experiments_dir == configured


def test_unconfigured_experiment_api_has_no_fixture_fallback(tmp_path: Path) -> None:
    with TestClient(create_app(_config(tmp_path, None))) as client:
        listing = client.get("/api/experiments")
        verification = client.get("/api/experiments/exp_fixture/runs/run_fixture")

    assert listing.status_code == 200
    assert listing.json() == {
        "configured": False,
        "status": "not_configured",
        "experiments": [],
    }
    assert verification.json()["state"] == "not_configured"
    assert verification.json()["configured"] is False


def test_experiment_listing_verifies_direct_child_and_keeps_legacy_runs_separate(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    _create_run(fixture)
    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        listing = client.get("/api/experiments")
        legacy_runs = client.get("/api/runs")

    assert listing.status_code == 200
    payload = listing.json()
    assert payload["configured"] is True
    assert payload["status"] == "available"
    assert payload["experiments"] == [
        {
            "experiment_id": "exp_fixture",
            "state": "verified",
            "content_sha256": json.loads(
                (fixture.experiment / "experiment.json").read_text(encoding="utf-8")
            )["content_sha256"],
            "project_id": "project",
            "mode": "debug",
            "discovered_run_ids": ["run_fixture"],
        }
    ]
    assert legacy_runs.json() == {"runs": []}
    assert str(tmp_path) not in listing.text
    assert "project_path" not in listing.text


def test_listing_skips_symlinked_experiment_directories(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    _create_run(fixture)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "experiment.json").write_text("{}", encoding="utf-8")
    link = fixture.experiment_root / "exp_link"
    run_link = fixture.experiment / "runs" / "run_link"
    try:
        link.symlink_to(outside, target_is_directory=True)
        run_link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        payload = client.get("/api/experiments").json()

    assert [item["experiment_id"] for item in payload["experiments"]] == ["exp_fixture"]
    assert payload["experiments"][0]["discovered_run_ids"] == ["run_fixture"]


def test_tampered_experiment_listing_is_generic_and_does_not_leak_paths(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    manifest_path = fixture.experiment / "experiment.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments")

    assert response.status_code == 200
    assert response.json()["experiments"] == [
        {
            "experiment_id": "exp_fixture",
            "state": "verification_failed",
            "content_sha256": None,
            "project_id": None,
            "mode": None,
            "discovered_run_ids": [],
        }
    ]
    assert str(tmp_path) not in response.text


def test_run_endpoint_reports_unsealed_and_sealed_states_with_only_output_identity(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    _create_run(fixture, run_id="run_unsealed")
    sealed_dir = _create_run(fixture, run_id="run_sealed")
    output = sealed_dir / "metrics" / "result.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"ok": true}\n', encoding="utf-8")
    seal_run(sealed_dir)

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        unsealed = client.get("/api/experiments/exp_fixture/runs/run_unsealed")
        sealed = client.get("/api/experiments/exp_fixture/runs/run_sealed")

    assert unsealed.status_code == 200
    assert unsealed.json()["state"] == "unsealed"
    assert unsealed.json()["outputs"] == [
        {"role": "metrics", "state": "unverified", "sha256": None, "bytes": None}
    ]
    sealed_payload = sealed.json()
    assert sealed_payload["state"] == "outputs_verified"
    assert sealed_payload["outputs"] == [
        {
            "role": "metrics",
            "state": "verified",
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "bytes": output.stat().st_size,
        }
    ]
    assert str(tmp_path) not in sealed.text
    assert "inputs" not in sealed_payload


def test_tampered_run_returns_generic_failure_without_input_paths(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    run_dir = _create_run(fixture)
    manifest_path = run_dir / "run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments/exp_fixture/runs/run_fixture")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "state": "verification_failed",
        "experiment_id": "exp_fixture",
        "run_id": "run_fixture",
        "content_sha256": None,
        "mode": None,
        "case_id": None,
        "split": None,
        "seed": None,
        "controller_id": None,
        "outputs": [],
    }
    assert str(tmp_path) not in response.text
    assert str(fixture.input) not in response.text


def test_run_id_traversal_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "run.json").write_text('{"content_sha256":"secret"}', encoding="utf-8")
    encoded_run_id = quote("../outside", safe="")

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get(f"/api/experiments/exp_fixture/runs/{encoded_run_id}")
        invalid_id = client.get("/api/experiments/exp_fixture/runs/CON")

    assert response.status_code in {404, 422}
    assert "secret" not in response.text
    assert str(tmp_path) not in response.text
    assert invalid_id.status_code == 422
    assert "invalid experiment or run ID" in invalid_id.text


def test_runtime_accounting_view_is_sanitized_and_requires_sealed_verified_role(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    run_dir, output, _ = _write_accounting_run(fixture)
    assert output is not None
    assert experiment_store.read_verified_output(run_dir, "runtime_accounting") == (
        output.read_bytes()
    )

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments/exp_fixture/runs/run_accounting/runtime-accounting")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "available"
    accounting = payload["accounting"]
    assert accounting["execution_status"] == "debug_simulation_finished"
    assert accounting["evidence_scope"] == "managed_debug_runtime_accounting_only"
    demand = accounting["demand_accounting"]
    assert demand["status"] == "partial"
    assert demand["reason"] == "one_or_more_sources_or_trip_rows_unverified"
    assert demand["intended_trip_count"] is None
    assert demand["raw_ledger_row_count"] == 2
    assert demand["tripinfo_observed_count"] is None
    assert all(count is None for count in demand["status_counts"].values())
    assert "trips" not in demand
    aggregate = accounting["aggregate_simulation_accounting"]
    assert aggregate["scope"] == "whole_simulation_vehicle_and_event_counters"
    assert aggregate["summary"]["final_step_time_seconds"] == 125.5
    assert aggregate["summary"]["loaded"] is None
    assert aggregate["summary"]["inserted"] == 4
    assert aggregate["statistic"]["safety_collisions"] is None
    assert (
        "Simulator collision counts do not establish complete action safety."
        in (aggregate["limitations"])
    )
    assert "source_inputs" not in payload
    assert "source_outputs" not in payload
    assert "errors" not in payload
    assert "D:/private" not in response.text
    assert "sensitive-trip-detail" not in response.text


def test_unsealed_runtime_accounting_returns_without_reading_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    _write_accounting_run(fixture, run_id="run_unsealed_accounting", sealed=False)

    def fail_if_read(*_args: object, **_kwargs: object) -> bytes:
        pytest.fail("unsealed runtime accounting must not read its output")

    monkeypatch.setattr(experiment_store, "_read_verified_output_bytes", fail_if_read)
    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get(
            "/api/experiments/exp_fixture/runs/run_unsealed_accounting/runtime-accounting"
        )

    assert response.status_code == 200
    assert response.json()["state"] == "unsealed"
    assert response.json()["accounting"] is None


def test_runtime_accounting_without_declared_role_is_unavailable(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    _write_accounting_run(
        fixture,
        run_id="run_without_accounting",
        include_role=False,
    )
    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get(
            "/api/experiments/exp_fixture/runs/run_without_accounting/runtime-accounting"
        )

    assert response.status_code == 200
    assert response.json()["state"] == "unavailable"
    assert response.json()["accounting"] is None


def test_runtime_accounting_rejects_post_seal_tampering(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    _, output, _ = _write_accounting_run(fixture)
    assert output is not None
    output.write_text(
        '{"schema_version":"runtime_trip_accounting.v1","secret":"D:/private"}',
        encoding="utf-8",
    )

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments/exp_fixture/runs/run_accounting/runtime-accounting")

    assert response.status_code == 200
    assert response.json()["state"] == "verification_failed"
    assert response.json()["accounting"] is None
    assert "D:/private" not in response.text


def test_runtime_accounting_rejects_wrong_schema_after_seal(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    run_dir, output, document = _write_accounting_run(fixture, sealed=False)
    assert output is not None
    document["schema_version"] = "runtime_trip_accounting.v999"
    output.write_text(json.dumps(document), encoding="utf-8")
    seal_run(run_dir)

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments/exp_fixture/runs/run_accounting/runtime-accounting")

    assert response.status_code == 200
    assert response.json()["state"] == "verification_failed"
    assert response.json()["accounting"] is None
    assert "D:/private" not in response.text


@pytest.mark.parametrize("malformed_field", ["loaded", "negative_time"])
def test_runtime_accounting_rejects_malformed_aggregate_without_leaking_paths(
    tmp_path: Path,
    malformed_field: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    run_dir, output, document = _write_accounting_run(fixture, sealed=False)
    assert output is not None
    aggregate = document["aggregate_simulation_accounting"]
    assert isinstance(aggregate, dict)
    summary = aggregate["summary"]
    assert isinstance(summary, dict)
    if malformed_field == "loaded":
        summary["loaded"] = "zero"
    else:
        summary["final_step_time_seconds"] = -1
    output.write_text(json.dumps(document), encoding="utf-8")
    seal_run(run_dir)

    with TestClient(create_app(_config(tmp_path, fixture.experiment_root))) as client:
        response = client.get("/api/experiments/exp_fixture/runs/run_accounting/runtime-accounting")

    assert response.status_code == 200
    assert response.json()["state"] == "verification_failed"
    assert response.json()["accounting"] is None
    assert "D:/private" not in response.text


def test_verified_output_reader_rechecks_raw_bytes_after_manifest_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    run_dir, output, _ = _write_accounting_run(fixture)
    assert output is not None
    original_verify = experiment_store.verify_run

    def verify_then_tamper(directory: Path) -> dict[str, object]:
        verified = original_verify(directory)
        output.write_bytes(b"replaced after manifest verification")
        return verified  # type: ignore[return-value]

    monkeypatch.setattr(experiment_store, "verify_run", verify_then_tamper)
    with pytest.raises(ExperimentError, match="changed while being read"):
        experiment_store.read_verified_output(run_dir, "runtime_accounting")
