from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ai_quantum_hvtc.experiments.executor import (
    execute_debug_run,
    prepare_debug_run,
    required_source_paths,
)
from ai_quantum_hvtc.experiments.store import (
    ExperimentError,
    create_experiment,
    file_record,
    verify_run,
)
from ai_quantum_hvtc.simulation.engines.sumo import (
    SumoRuntimeConfig,
    prepare_existing_sumo_net_run,
    run_existing_sumo_net,
)
from ai_quantum_hvtc.simulation.engines.sumo.config import resolve_sumo_binary
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.parser import parse_existing_sumo_net_result
from ai_quantum_hvtc.simulation.engines.sumo.runner import has_sumo_runtime, run_sumo_pipeline
from ai_quantum_hvtc.simulation.maps.snapshot import write_project_snapshot
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def _write_debug_vehicle_route(path: Path, *, vehicle_id: str, route_edges: str) -> None:
    routes_root = ET.Element("routes")
    ET.SubElement(
        routes_root,
        "vType",
        {
            "id": "toy_passenger",
            "vClass": "passenger",
            "length": "5",
            "maxSpeed": "13.89",
            "accel": "2.6",
            "decel": "4.5",
        },
    )
    ET.SubElement(routes_root, "route", {"id": "toy_route", "edges": route_edges})
    ET.SubElement(
        routes_root,
        "vehicle",
        {"id": vehicle_id, "type": "toy_passenger", "route": "toy_route", "depart": "0"},
    )
    ET.indent(routes_root, space="  ")
    ET.ElementTree(routes_root).write(path, encoding="utf-8", xml_declaration=True)


def _write_intended_ledger(path: Path, *, trip_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": [
                    {
                        "trip_id": trip_id,
                        "source_flow_id": "toy_flow",
                        "trip_purpose": "integration_plumbing",
                        "vehicle_type_id": "PRIVATE_CAR",
                        "vehicle_class": "passenger",
                        "intended_departure_seconds": 0.0,
                        "origin_zone_id": "toy_origin",
                        "destination_zone_id": "toy_destination",
                        "origin_edge_id": "fixture_origin",
                        "destination_edge_id": "fixture_destination",
                        "route_status": "routed",
                        "failure_reason": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO runtime is not available")
def test_existing_sumo_net_runner_reuses_net_and_routes(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    seed_paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        work_dir=tmp_path / "seed",
    )
    run_sumo_pipeline(seed_paths, SumoRuntimeConfig(), controller_id="fixed_time")

    run_paths = prepare_existing_sumo_net_run(
        net=seed_paths.net,
        routes=seed_paths.routes,
        work_dir=tmp_path / "existing",
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
        horizon_seconds=600,
    )
    run_existing_sumo_net(run_paths, SumoRuntimeConfig())
    result = parse_existing_sumo_net_result(
        paths=run_paths,
        district_id="toy_public_district_v1",
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )

    assert result.engine_id == "sumo_net"
    assert result.total_vehicles > 0
    assert result.vehicle_trace_frames
    assert result.vehicle_trace_frames[0]["engine_id"] == "sumo_net"


@pytest.mark.skipif(not has_sumo_runtime(), reason="SUMO and netconvert runtime are not available")
def test_debug_experiment_runs_real_sumo_and_freezes_output_identity(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    fixture_paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=101,
        work_dir=tmp_path / "toy_sumo_fixture",
    )
    netconvert = resolve_sumo_binary(SumoRuntimeConfig().netconvert_binary)
    assert netconvert is not None
    subprocess.run(
        [
            netconvert,
            "--node-files",
            str(fixture_paths.nodes),
            "--edge-files",
            str(fixture_paths.edges),
            "--output-file",
            str(fixture_paths.net),
            "--no-turnarounds",
            "true",
        ],
        cwd=fixture_paths.work_dir,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    route_tree = ET.parse(fixture_paths.routes)
    fixture_route = next(route_tree.getroot().iter("route"), None)
    assert fixture_route is not None
    route_edges = fixture_route.attrib["edges"]
    routes = tmp_path / "toy_arrived_vehicle.rou.xml"
    unfinished_routes = tmp_path / "toy_unfinished_vehicle.rou.xml"
    _write_debug_vehicle_route(routes, vehicle_id="toy_vehicle_arrived", route_edges=route_edges)
    _write_debug_vehicle_route(
        unfinished_routes,
        vehicle_id="toy_vehicle_unfinished",
        route_edges=route_edges,
    )
    arrived_ledger = tmp_path / "arrived_intended_demand_ledger.json"
    unfinished_ledger = tmp_path / "unfinished_intended_demand_ledger.json"
    _write_intended_ledger(arrived_ledger, trip_id="toy_vehicle_arrived")
    _write_intended_ledger(unfinished_ledger, trip_id="toy_vehicle_unfinished")

    project_path = fixture_paths.work_dir / "toy_project.json"
    overlay_path = fixture_paths.work_dir / "toy_overlay.json"
    demand_path = fixture_paths.work_dir / "toy_demand.json"
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "toy_overlay",
                "name": "Toy fixture overlay",
                "zones": [
                    {
                        "id": "toy_zone",
                        "name": "Toy zone",
                        "type": "residential",
                        "anchor_edges": [next(iter(spec.roads))],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    demand_path.write_text("{}\n", encoding="utf-8")
    project_path.write_text(
        json.dumps(
            {
                "id": "toy_debug_project",
                "name": "Toy debug fixture",
                "version": "v1",
                "source": {"net_path": fixture_paths.net.name},
                "semantic_overlay_path": overlay_path.name,
                "demand_config_path": demand_path.name,
            }
        ),
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "toy_project_snapshot.json"
    snapshot = write_project_snapshot(project_path, snapshot_path)
    assert snapshot["project_id"] == "toy_debug_project"

    split_seeds = {
        "rl_train": [101],
        "rl_validation": [202],
        "coefficient_fit": [303],
        "surrogate_validation": [404],
        "final_test": [505],
    }
    protocol = {
        "schema_version": "experiment_protocol.v1",
        "mode": "debug",
        "seed_splits": split_seeds,
        "cases": {
            f"case_{split}": {"split": split, "partition_group": f"group_{split}"}
            for split in split_seeds
        },
        "contracts": {
            role: None
            for role in ("demand", "observation", "reward", "economic", "evaluator", "safety")
        },
        "objective": None,
    }
    protocol_path = tmp_path / "debug_protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    frozen_sources = required_source_paths()
    experiment_dir = create_experiment(
        root=tmp_path / "experiments",
        experiment_id="toy_debug_experiment",
        project_path=project_path,
        snapshot_path=snapshot_path,
        protocol_path=protocol_path,
        source_paths=frozen_sources,
    )

    run_dir = prepare_debug_run(
        experiment_dir=experiment_dir,
        run_id="toy_debug_run",
        case_id="case_rl_train",
        seed=split_seeds["rl_train"][0],
        routes=routes,
        intended_demand_ledger=arrived_ledger,
        horizon_seconds=600,
        step_length_seconds=1.0,
    )
    run_file = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    experiment_file = json.loads((experiment_dir / "experiment.json").read_text(encoding="utf-8"))
    frozen_paths = {record["path"] for record in experiment_file["source_files"]}
    assert frozen_paths >= {str(path.resolve()) for path in frozen_sources}
    assert experiment_file["protocol"]["seed_splits"] == split_seeds
    all_seeds = [seed for split in split_seeds.values() for seed in split]
    assert len(all_seeds) == len(set(all_seeds))
    assert run_file["contracts"] == protocol["contracts"]
    assert set(run_file["contracts"].values()) == {None}

    execution = execute_debug_run(run_dir)
    execution_result = json.loads(
        (run_dir / "execution_result.json").read_text(encoding="utf-8")
    )
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    trace_rows = [
        json.loads(line)
        for line in (run_dir / "vehicle_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert execution["status"] == "outputs_verified"
    assert execution["mode"] == "debug"
    assert execution["experiment_id"] == run_file["experiment_id"]
    assert execution["run_id"] == run_file["run_id"]
    assert execution_result["experiment_id"] == run_file["experiment_id"]
    assert execution_result["run_id"] == run_file["run_id"]
    assert result["experiment_id"] == run_file["experiment_id"]
    assert result["run_id"] == run_file["run_id"]
    assert result["metrics"]["total_vehicles"] == 1
    assert result["evaluator_cost"] is None
    assert all(
        result["metrics"][field] is None
        for field in ("bus_passenger_delay_seconds", "reroute_count", "failed_route_count")
    )
    assert trace_rows
    assert all(
        row["experiment_id"] == run_file["experiment_id"]
        and row["run_id"] == run_file["run_id"]
        for row in trace_rows
    )

    geometry = json.loads((run_dir / "geometry_manifest.json").read_text(encoding="utf-8"))
    render = json.loads((run_dir / "render_run_manifest.json").read_text(encoding="utf-8"))
    for manifest in (geometry, render):
        assert manifest["experiment_id"] == run_file["experiment_id"]
        assert manifest["run_id"] == run_file["run_id"]

    runtime_accounting = json.loads(
        (run_dir / "runtime_accounting.json").read_text(encoding="utf-8")
    )
    assert runtime_accounting["schema_version"] == "runtime_trip_accounting.v1"
    assert runtime_accounting["run_sha256"] == run_file["content_sha256"]
    assert runtime_accounting["source_inputs"]["intended_demand_ledger"]["sha256"] == (
        run_file["inputs"]["intended_demand_ledger"]["sha256"]
    )
    assert runtime_accounting["source_outputs"]["tripinfo"]["sha256"]
    assert runtime_accounting["source_outputs"]["summary"]["sha256"]
    assert runtime_accounting["source_outputs"]["statistic"]["sha256"]
    assert runtime_accounting["demand_accounting"]["status"] == "available"
    assert runtime_accounting["demand_accounting"]["trips"][0]["status"] == "arrived"
    aggregate = runtime_accounting["aggregate_simulation_accounting"]
    assert aggregate["summary"]["arrived"] == 1
    assert aggregate["statistic"]["total_teleports"] == 0
    assert aggregate["statistic"]["safety_collisions"] == 0

    unfinished_run_dir = prepare_debug_run(
        experiment_dir=experiment_dir,
        run_id="toy_debug_unfinished_run",
        case_id="case_rl_validation",
        seed=split_seeds["rl_validation"][0],
        routes=unfinished_routes,
        intended_demand_ledger=unfinished_ledger,
        horizon_seconds=15,
        step_length_seconds=1.0,
    )
    unfinished_execution = execute_debug_run(unfinished_run_dir)
    unfinished_run = json.loads((unfinished_run_dir / "run.json").read_text(encoding="utf-8"))
    unfinished_accounting = json.loads(
        (unfinished_run_dir / "runtime_accounting.json").read_text(encoding="utf-8")
    )
    assert unfinished_execution["status"] == "outputs_verified"
    assert unfinished_accounting["run_sha256"] == unfinished_run["content_sha256"]
    unfinished_row = unfinished_accounting["demand_accounting"]["trips"][0]
    assert unfinished_row["trip_id"] == "toy_vehicle_unfinished"
    # Local SUMO emits vaporized="end" at simulation end. Its meaning is not the documented
    # boolean, so this row must remain unverified instead of being guessed as unfinished.
    assert unfinished_row["status"] == "unverified"
    assert unfinished_row["tripinfo_evidence"]["arrival_seconds"] == -1.0
    assert unfinished_row["tripinfo_evidence"]["vaporized"] is None
    assert unfinished_accounting["demand_accounting"]["status"] == "unavailable"

    verified = verify_run(run_dir)
    outputs = json.loads((run_dir / "outputs.json").read_text(encoding="utf-8"))
    assert verified["state"] == "outputs_verified"
    assert verified["run"]["experiment_id"] == run_file["experiment_id"]
    assert verified["run"]["run_id"] == run_file["run_id"]
    assert outputs["experiment_id"] == run_file["experiment_id"]
    assert outputs["run_id"] == run_file["run_id"]
    assert verified["outputs"]["files"]["geometry_manifest"]["path"] == (
        "geometry_manifest.json"
    )
    assert verified["outputs"]["files"]["render_run_manifest"]["path"] == (
        "render_run_manifest.json"
    )
    assert verified["outputs"]["files"]["runtime_accounting"]["sha256"] == (
        file_record(run_dir / "runtime_accounting.json")["sha256"]
    )

    run_manifest_before = (run_dir / "run.json").read_bytes()
    result_before = (run_dir / "result.json").read_bytes()
    outputs_before = (run_dir / "outputs.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare_debug_run(
            experiment_dir=experiment_dir,
            run_id="toy_debug_run",
            case_id="case_rl_train",
            seed=split_seeds["rl_train"][0],
            routes=routes,
            horizon_seconds=15,
            step_length_seconds=1.0,
        )
    assert (run_dir / "run.json").read_bytes() == run_manifest_before
    assert (run_dir / "result.json").read_bytes() == result_before
    assert (run_dir / "outputs.json").read_bytes() == outputs_before

    (run_dir / "result.json").write_bytes(result_before + b" ")
    with pytest.raises(ExperimentError, match="output checksum mismatch"):
        verify_run(run_dir)
