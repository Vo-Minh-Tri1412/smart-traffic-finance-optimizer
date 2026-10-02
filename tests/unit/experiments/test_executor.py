from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ai_quantum_hvtc.experiments import executor
from ai_quantum_hvtc.experiments.store import (
    ExperimentError,
    create_experiment,
    create_run,
    read_json,
)
from ai_quantum_hvtc.simulation.maps.snapshot import write_project_snapshot

NET = """<net>
  <edge id="E1"><lane id="E1_0" index="0" shape="0,0 3,4"/></edge>
  <edge id="E2"><lane id="E2_0" index="0" shape="3,4 5,6"/></edge>
  <tlLogic id="TLS" type="static" programID="0" offset="0">
    <phase duration="10" state="G"/><phase duration="3" state="y"/>
    <phase duration="2" state="r"/>
  </tlLogic>
  <junction id="J" type="traffic_light" x="3" y="4"/>
  <connection from="E1" to="E2" fromLane="0" toLane="0"
              tl="TLS" linkIndex="0" dir="s" state="O"/>
</net>"""


def _make_debug_run(
    tmp_path: Path,
    *,
    run_id: str = "run_fixture",
    routes_xml: str = "<routes />",
    intended_demand_ledger: Path | None = None,
) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "map.net.xml").write_text(NET, encoding="utf-8")
    (project_dir / "overlay.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "overlay",
                "name": "Test overlay",
                "zones": [
                    {
                        "id": "Z",
                        "name": "Zone",
                        "type": "residential",
                        "anchor_edges": ["E1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "demand.json").write_text("{}", encoding="utf-8")
    project_path = project_dir / "project.json"
    project_path.write_text(
        json.dumps(
            {
                "id": "project",
                "name": "Test project",
                "version": "v1",
                "source": {"net_path": "map.net.xml"},
                "semantic_overlay_path": "overlay.json",
                "demand_config_path": "demand.json",
            }
        ),
        encoding="utf-8",
    )

    snapshot_path = tmp_path / "snapshot.json"
    write_project_snapshot(project_path, snapshot_path)
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(
        json.dumps(
            {
                "schema_version": "experiment_protocol.v1",
                "mode": "debug",
                "seed_splits": {
                    "rl_train": [11],
                    "rl_validation": [22],
                    "coefficient_fit": [33],
                    "surrogate_validation": [44],
                    "final_test": [55],
                },
                "cases": {
                    "case_train": {
                        "split": "rl_train",
                        "partition_group": "group_train",
                    }
                },
                "contracts": {
                    role: None
                    for role in (
                        "demand",
                        "observation",
                        "reward",
                        "economic",
                        "evaluator",
                        "safety",
                    )
                },
                "objective": None,
            }
        ),
        encoding="utf-8",
    )

    root = tmp_path / "experiments"
    experiment_dir = create_experiment(
        root=root,
        experiment_id="experiment_fixture",
        project_path=project_path,
        snapshot_path=snapshot_path,
        protocol_path=protocol_path,
        source_paths=executor.required_source_paths(),
    )
    routes = tmp_path / "routes.rou.xml"
    routes.write_text(routes_xml, encoding="utf-8")
    binary = tmp_path / "sumo.exe"
    binary.write_bytes(b"fake-sumo-binary")
    inputs = {"routes": routes, "sumo_binary": binary}
    if intended_demand_ledger is not None:
        inputs["intended_demand_ledger"] = intended_demand_ledger
    return create_run(
        experiment_dir=experiment_dir,
        run_id=run_id,
        case_id="case_train",
        seed=11,
        controller_id="fixed_time",
        mask=[],
        inputs=inputs,
        expected_outputs=executor.debug_outputs("case_train"),
        settings={
            "executor": "existing_net_debug.v1",
            "horizon_seconds": 60,
            "step_length_seconds": 1.0,
        },
    )


def test_prepare_debug_run_freezes_optional_intended_demand_ledger(
    tmp_path: Path, monkeypatch: Any
) -> None:
    existing_run = _make_debug_run(tmp_path)
    experiment_dir = existing_run.parents[1]
    existing_manifest = read_json(existing_run / "run.json")
    routes = Path(existing_manifest["inputs"]["routes"]["path"])
    binary = Path(existing_manifest["inputs"]["sumo_binary"]["path"])
    ledger_path = tmp_path / "intended_demand_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": [
                    {
                        "trip_id": "not_routed_trip",
                        "source_flow_id": "flow",
                        "trip_purpose": "commute",
                        "vehicle_type_id": "PRIVATE_CAR",
                        "vehicle_class": "passenger",
                        "intended_departure_seconds": 0.0,
                        "origin_zone_id": "origin",
                        "destination_zone_id": "destination",
                        "origin_edge_id": "E1",
                        "destination_edge_id": "E2",
                        "route_status": "not_routed",
                        "failure_reason": "unknown",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(executor, "resolve_sumo_binary", lambda _: str(binary))

    run_dir = executor.prepare_debug_run(
        experiment_dir=experiment_dir,
        run_id="run_with_ledger",
        case_id="case_train",
        seed=11,
        routes=routes,
        horizon_seconds=60,
        step_length_seconds=1.0,
        intended_demand_ledger=ledger_path,
    )

    manifest = read_json(run_dir / "run.json")
    assert manifest["inputs"]["intended_demand_ledger"] == {
        "path": str(ledger_path.resolve()),
        "sha256": executor.file_record(ledger_path)["sha256"],
        "bytes": ledger_path.stat().st_size,
    }


def test_execute_debug_run_writes_identity_bound_render_manifests(
    tmp_path: Path, monkeypatch: Any
) -> None:
    run_dir = _make_debug_run(tmp_path)

    def fake_run_sumo(paths: Any, _config: Any) -> None:
        for path, contents in (
            (paths.tripinfo, "<tripinfos />"),
            (
                paths.summary,
                '<summary><step time="0" loaded="0" inserted="0" waiting="0" '
                'arrived="0" running="0" ended="0"/></summary>',
            ),
            (
                paths.statistic,
                '<statistics><teleports total="0"/><safety collisions="0"/></statistics>',
            ),
            (paths.edge_data, "<meandata />"),
            (paths.fcd, "<fcd-export />"),
            (paths.stdout_log, ""),
            (paths.stderr_log, ""),
        ):
            path.write_text(contents, encoding="utf-8")

    class ParsedResult:
        vehicle_trace_frames = [
            {
                "schema_version": "vehicle_trace.v2",
                "time": 0,
                "vehicles": [
                    {
                        "length_m": 4.5,
                        "width_m": 1.8,
                        "height_m": 1.5,
                        "ground_clearance_m": 0.0,
                        "reference_point": "front_bumper_center",
                    }
                ],
            }
        ]

        def to_dict(self) -> dict[str, Any]:
            return {"engine_id": "sumo_net", "vehicle_count": 0}

    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="SUMO fake version", stderr=""
        ),
    )
    monkeypatch.setattr(executor, "run_existing_sumo_net", fake_run_sumo)
    monkeypatch.setattr(executor, "parse_existing_sumo_net_result", lambda **_: ParsedResult())

    result = executor.execute_debug_run(run_dir)

    geometry = read_json(run_dir / "geometry_manifest.json")
    render = read_json(run_dir / "render_run_manifest.json")
    accounting = read_json(run_dir / "runtime_accounting.json")
    result_manifest = read_json(run_dir / "result.json")
    assert result["status"] == "outputs_verified"
    assert geometry["experiment_id"] == render["experiment_id"] == "experiment_fixture"
    assert geometry["run_id"] == render["run_id"] == "run_fixture"
    assert geometry["geometry_source"] == "sumo_net_xml"
    assert render["vehicle_trace"] == "vehicle_trace.jsonl"
    assert render["render_executed"] is False
    assert render["render_status"] == "not_executed"
    assert accounting["schema_version"] == "runtime_trip_accounting.v1"
    assert accounting["run_id"] == "run_fixture"
    assert accounting["demand_accounting"]["status"] == "unavailable"
    assert accounting["demand_accounting"]["reason"] == "no_intended_demand_ledger_supplied"
    assert accounting["demand_accounting"]["raw_ledger_row_count"] is None
    assert accounting["demand_accounting"]["trips"] == []
    assert (
        "Demand accounting is unavailable when no intended-demand ledger is supplied"
        in result_manifest["limitations"]
    )
    assert accounting["aggregate_simulation_accounting"]["summary"]["arrived"] == 0
    assert accounting["aggregate_simulation_accounting"]["statistic"]["total_teleports"] == 0
    assert accounting["source_outputs"]["statistic"]["sha256"]
    output_manifest = read_json(run_dir / "outputs.json")
    assert set(output_manifest["files"]) == set(executor.debug_outputs("case_train"))
    assert (
        output_manifest["files"]["runtime_accounting"]["sha256"]
        == (executor.file_record(run_dir / "runtime_accounting.json")["sha256"])
    )


def test_execute_debug_run_rejects_legacy_trace_before_render_or_seal(
    tmp_path: Path, monkeypatch: Any
) -> None:
    run_dir = _make_debug_run(tmp_path, run_id="run_legacy_trace")

    def fake_run_sumo(paths: Any, _config: Any) -> None:
        for path, contents in (
            (paths.tripinfo, "<tripinfos />"),
            (
                paths.summary,
                '<summary><step time="0" loaded="0" inserted="0" waiting="0" '
                'arrived="0" running="0" ended="0"/></summary>',
            ),
            (
                paths.statistic,
                '<statistics><teleports total="0"/><safety collisions="0"/></statistics>',
            ),
            (paths.edge_data, "<meandata />"),
            (paths.fcd, "<fcd-export />"),
            (paths.stdout_log, ""),
            (paths.stderr_log, ""),
        ):
            path.write_text(contents, encoding="utf-8")

    class ParsedResult:
        vehicle_trace_frames = [
            {
                "schema_version": "simulation_trace_frame.v1",
                "time_seconds": 0,
                "vehicles": [{"vehicle_id": "car-1"}],
            }
        ]

        def to_dict(self) -> dict[str, Any]:
            return {"engine_id": "sumo_net", "vehicle_count": 1}

    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="SUMO fake version", stderr=""
        ),
    )
    monkeypatch.setattr(executor, "run_existing_sumo_net", fake_run_sumo)
    monkeypatch.setattr(executor, "parse_existing_sumo_net_result", lambda **_: ParsedResult())

    def unexpected_render(**_: Any) -> None:
        raise AssertionError("invalid vehicle trace must stop before render inputs")

    def unexpected_seal(_: Path) -> None:
        raise AssertionError("invalid vehicle trace must not seal the run")

    monkeypatch.setattr(executor, "write_render_inputs", unexpected_render)
    monkeypatch.setattr(executor, "seal_run", unexpected_seal)

    with pytest.raises(ExperimentError, match="explicit route vType geometry"):
        executor.execute_debug_run(run_dir)

    assert not (run_dir / "vehicle_trace.jsonl").exists()
    assert not (run_dir / "geometry_manifest.json").exists()
    assert not (run_dir / "render_run_manifest.json").exists()
    assert read_json(run_dir / "execution_result.json")["status"] == "failed"


def test_failed_execution_keeps_ledger_rows_in_unverified_accounting(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ledger = tmp_path / "intended_demand_ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": [
                    {
                        "trip_id": "trip-1",
                        "source_flow_id": "flow-1",
                        "trip_purpose": "commute",
                        "vehicle_type_id": "PRIVATE_CAR",
                        "vehicle_class": "passenger",
                        "intended_departure_seconds": 0.0,
                        "origin_zone_id": "origin",
                        "destination_zone_id": "destination",
                        "origin_edge_id": "E1",
                        "destination_edge_id": "E2",
                        "route_status": "routed",
                        "failure_reason": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run_dir = _make_debug_run(
        tmp_path,
        run_id="run_partial_output",
        routes_xml=(
            '<routes><route id="r1" edges="E1 E2"/>'
            '<vehicle id="trip-1" route="r1" depart="0"/></routes>'
        ),
        intended_demand_ledger=ledger,
    )
    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="SUMO fake version", stderr=""
        ),
    )

    def fake_run_sumo(paths: Any, _config: Any) -> None:
        for path, contents in (
            (
                paths.summary,
                '<summary><step time="0" loaded="1" inserted="1" waiting="0" '
                'arrived="0" running="1" ended="0"/></summary>',
            ),
            (
                paths.statistic,
                '<statistics><teleports total="0"/><safety collisions="0"/></statistics>',
            ),
            (paths.edge_data, "<meandata />"),
            (paths.fcd, "<fcd-export />"),
            (paths.stdout_log, ""),
            (paths.stderr_log, ""),
        ):
            path.write_text(contents, encoding="utf-8")

    monkeypatch.setattr(executor, "run_existing_sumo_net", fake_run_sumo)
    with pytest.raises(ExperimentError, match="did not produce required output: tripinfo.xml"):
        executor.execute_debug_run(run_dir)

    accounting = read_json(run_dir / "runtime_accounting.json")
    demand = accounting["demand_accounting"]
    assert demand["intended_trip_count"] == 1
    assert demand["raw_ledger_row_count"] == 1
    assert demand["trips"][0]["trip_id"] == "trip-1"
    assert demand["trips"][0]["status"] == "unverified"
    assert all(value is None for value in demand["status_counts"].values())
    assert accounting["source_outputs"]["tripinfo"] is None


def test_prepare_debug_run_fails_closed_for_research_before_sumo_or_reservation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        executor,
        "verify_experiment",
        lambda _: {"protocol": {"mode": "research_synthetic"}},
    )

    def unexpected_call(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("research run must stop before SUMO lookup or run reservation")

    monkeypatch.setattr(executor, "resolve_sumo_binary", unexpected_call)
    monkeypatch.setattr(executor, "create_run", unexpected_call)

    with pytest.raises(
        ExperimentError,
        match="retained-map intended/served-demand and route-failure ledgers",
    ):
        executor.prepare_debug_run(
            experiment_dir=tmp_path / "unused-experiment",
            run_id="research-run",
            case_id="case_train",
            seed=11,
            routes=tmp_path / "unused-routes.rou.xml",
            horizon_seconds=60,
            step_length_seconds=1.0,
        )
