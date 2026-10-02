"""Run the retained-net adapter with frozen identity; research execution is not yet supported."""

from __future__ import annotations

import json
import math
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.engines.sumo.config import SumoRuntimeConfig, resolve_sumo_binary
from ai_quantum_hvtc.simulation.engines.sumo.existing_net import (
    prepare_existing_sumo_net_run,
    run_existing_sumo_net,
)
from ai_quantum_hvtc.simulation.engines.sumo.parser import parse_existing_sumo_net_result
from ai_quantum_hvtc.simulation.maps.source import SumoProjectDescriptor, load_sumo_project
from ai_quantum_hvtc.simulation.traces import VEHICLE_TRACE_SCHEMA_VERSION
from ai_quantum_hvtc.simulation.vehicle_geometry import FRONT_BUMPER_REFERENCE_POINT

from .render_inputs import write_render_inputs
from .runtime_accounting import (
    build_runtime_trip_accounting,
    validate_intended_demand_routes,
)
from .store import (
    ExperimentError,
    create_run,
    file_record,
    seal_run,
    validate_id,
    verify_experiment,
    verify_run,
)


def required_source_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return sorted((root / "ai_quantum_hvtc").rglob("*.py")) + [
        root / "pyproject.toml",
        root / "uv.lock",
    ]


def _execution_gate(experiment: dict[str, Any]) -> None:
    if experiment["protocol"]["mode"] != "debug":
        raise ExperimentError(
            "research execution unavailable: retained-map intended/served-demand and "
            "route-failure ledgers plus verified runtime safety are missing; a manifest cannot "
            "waive these gates"
        )
    frozen_paths = {record["path"] for record in experiment["source_files"]}
    missing = {str(path.resolve()) for path in required_source_paths()} - frozen_paths
    if missing:
        raise ExperimentError(
            "managed executor requires all ai_quantum_hvtc Python sources, pyproject.toml "
            f"and uv.lock to be frozen; missing {len(missing)} files"
        )


def debug_outputs(case_id: str) -> dict[str, str]:
    validate_id(case_id)
    prefix = f"sumo/{case_id}/fixed_time"
    return {
        "result": "result.json",
        "vehicle_trace": "vehicle_trace.jsonl",
        "geometry_manifest": "geometry_manifest.json",
        "render_run_manifest": "render_run_manifest.json",
        "execution_result": "execution_result.json",
        "runtime_accounting": "runtime_accounting.json",
        **{
            role: f"{prefix}/{name}"
            for role, name in {
                "sumo_config": "district.sumocfg",
                "additional": "additional.xml",
                "tripinfo": "tripinfo.xml",
                "summary": "summary.xml",
                "statistic": "statistic.xml",
                "edge_data": "edge_data.xml",
                "fcd": "fcd.xml",
                "controller_log": "controller_interventions.jsonl",
                "stdout": "stdout.log",
                "stderr": "stderr.log",
            }.items()
        },
    }


def _validate_settings(settings: dict[str, Any]) -> None:
    if set(settings) != {"executor", "horizon_seconds", "step_length_seconds"}:
        raise ExperimentError("debug settings must explicitly specify executor/horizon/step")
    horizon = settings["horizon_seconds"]
    step = settings["step_length_seconds"]
    if settings["executor"] != "existing_net_debug.v1":
        raise ExperimentError("unsupported executor version")
    if type(horizon) is not int or horizon <= 0:
        raise ExperimentError("horizon_seconds must be a positive integer")
    if (
        isinstance(step, bool)
        or not isinstance(step, (int, float))
        or not math.isfinite(step)
        or step <= 0
    ):
        raise ExperimentError("step_length_seconds must be finite and positive")


def _validate_standalone_routes(path: Path) -> None:
    # SUMO include/file references would otherwise be mutable, unhashed side inputs.
    try:
        for _, element in ET.iterparse(path, events=("start",)):
            if element.tag.rsplit("}", 1)[-1] == "include" or "file" in element.attrib:
                raise ExperimentError(
                    "managed debug routes must be standalone; external files unsupported"
                )
    except ET.ParseError as exc:
        raise ExperimentError(f"invalid route XML: {exc}") from exc


def prepare_debug_run(
    *,
    experiment_dir: Path,
    run_id: str,
    case_id: str,
    seed: int,
    routes: Path,
    horizon_seconds: int,
    step_length_seconds: float,
    intended_demand_ledger: Path | None = None,
) -> Path:
    experiment = verify_experiment(experiment_dir)
    _execution_gate(experiment)
    settings = {
        "executor": "existing_net_debug.v1",
        "horizon_seconds": horizon_seconds,
        "step_length_seconds": step_length_seconds,
    }
    _validate_settings(settings)
    _validate_standalone_routes(routes)
    binary = resolve_sumo_binary("sumo")
    if binary is None:
        raise ExperimentError("SUMO binary unavailable")
    inputs = {"routes": routes, "sumo_binary": Path(binary)}
    if intended_demand_ledger is not None:
        inputs["intended_demand_ledger"] = intended_demand_ledger
    return create_run(
        experiment_dir=experiment_dir,
        run_id=run_id,
        case_id=case_id,
        seed=seed,
        controller_id="fixed_time",
        mask=[],
        inputs=inputs,
        expected_outputs=debug_outputs(case_id),
        settings=settings,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _write_runtime_accounting(
    *,
    directory: Path,
    run: dict[str, Any],
    identity: dict[str, Any],
    paths: Any | None,
    execution_status: str,
) -> None:
    output_path = directory / "runtime_accounting.json"
    if output_path.exists():
        return
    sumo_dir = (
        paths.work_dir if paths is not None else directory / "sumo" / run["case_id"] / "fixed_time"
    )
    payload = build_runtime_trip_accounting(
        run=run,
        identity=identity,
        routes_path=Path(run["inputs"]["routes"]["path"]),
        tripinfo_path=paths.tripinfo if paths is not None else sumo_dir / "tripinfo.xml",
        summary_path=paths.summary if paths is not None else sumo_dir / "summary.xml",
        statistic_path=paths.statistic if paths is not None else sumo_dir / "statistic.xml",
        execution_status=execution_status,
    )
    _write_json(output_path, payload)


def _validate_render_vehicle_trace(frames: Any) -> None:
    requirement = (
        "managed render requires non-empty vehicle_trace.v2 frames with canonical vehicle "
        "geometry; add explicit route vType geometry (length, width, and height) when "
        "unavailable"
    )
    if not isinstance(frames, (list, tuple)) or not frames:
        raise ExperimentError(f"SUMO vehicle trace is not renderable: {requirement}")

    for frame_index, frame in enumerate(frames):
        if (
            not isinstance(frame, dict)
            or frame.get("schema_version") != VEHICLE_TRACE_SCHEMA_VERSION
        ):
            raise ExperimentError(
                f"SUMO vehicle trace frame {frame_index} is not renderable: {requirement}"
            )
        vehicles = frame.get("vehicles")
        if not isinstance(vehicles, list):
            raise ExperimentError(
                f"SUMO vehicle trace frame {frame_index} has invalid vehicles: {requirement}"
            )
        for vehicle_index, vehicle in enumerate(vehicles):
            if not isinstance(vehicle, dict):
                raise ExperimentError(
                    f"SUMO vehicle trace frame {frame_index} vehicle {vehicle_index} is "
                    f"not renderable: {requirement}"
                )
            for field in ("length_m", "width_m", "height_m"):
                value = vehicle.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                ):
                    raise ExperimentError(
                        f"SUMO vehicle trace frame {frame_index} vehicle {vehicle_index} has "
                        f"invalid {field}: {requirement}"
                    )
            clearance = vehicle.get("ground_clearance_m")
            if (
                isinstance(clearance, bool)
                or not isinstance(clearance, (int, float))
                or not math.isfinite(clearance)
                or clearance < 0
            ):
                raise ExperimentError(
                    f"SUMO vehicle trace frame {frame_index} vehicle {vehicle_index} has "
                    f"invalid ground_clearance_m: {requirement}"
                )
            if vehicle.get("reference_point") != FRONT_BUMPER_REFERENCE_POINT:
                raise ExperimentError(
                    f"SUMO vehicle trace frame {frame_index} vehicle {vehicle_index} has "
                    f"a non-canonical reference_point: {requirement}"
                )


def execute_debug_run(directory: Path) -> dict[str, Any]:
    verified = verify_run(directory)
    run = verified["run"]
    if verified["state"] != "unsealed":
        raise ExperimentError("run already sealed; use verify-run to reuse verified artifacts")
    experiment = verify_experiment(directory.parent.parent)
    _execution_gate(experiment)
    if run["controller_id"] != "fixed_time" or run["mask"] or run["objective"]["reward_variant"]:
        raise ExperimentError("debug executor only supports the unchanged fixed_time controller")
    required_inputs = {"routes", "sumo_binary"}
    allowed_inputs = required_inputs | {"intended_demand_ledger"}
    if not required_inputs.issubset(run["inputs"]) or not set(run["inputs"]).issubset(
        allowed_inputs
    ):
        raise ExperimentError("debug executor requires routes and sumo_binary with optional ledger")
    if run["expected_outputs"] != debug_outputs(run["case_id"]):
        raise ExperimentError("unexpected debug output contract")
    _validate_settings(run["settings"])
    routes = Path(run["inputs"]["routes"]["path"])
    _validate_standalone_routes(routes)
    project: SumoProjectDescriptor = load_sumo_project(experiment["project_path"])
    binary = Path(run["inputs"]["sumo_binary"]["path"])
    # Exclusive reservation before any output generation. A failure is not an implicit retry.
    identity = {
        "experiment_id": run["experiment_id"],
        "run_id": run["run_id"],
        "run_sha256": run["content_sha256"],
    }
    paths: Any | None = None
    _write_json(
        directory / "execution.json",
        {
            "schema_version": "run_execution.v1",
            **identity,
            "started_at": datetime.now(UTC).isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "sumo_binary": file_record(binary),
            "evidence_scope": "debug_simulation_only",
        },
    )
    try:
        ledger_input = run["inputs"].get("intended_demand_ledger")
        if ledger_input is not None:
            validate_intended_demand_routes(Path(ledger_input["path"]), routes)
        version = subprocess.run(
            [str(binary), "--version"], check=True, capture_output=True, text=True, timeout=15
        ).stdout.strip()
        paths = prepare_existing_sumo_net_run(
            net=project.source.net_path,
            routes=routes,
            work_dir=directory / "sumo",
            scenario_id=run["case_id"],
            controller_id="fixed_time",
            seed=run["seed"],
            horizon_seconds=run["settings"]["horizon_seconds"],
            step_length_seconds=run["settings"]["step_length_seconds"],
        )
        run_existing_sumo_net(paths, SumoRuntimeConfig(sumo_binary=str(binary)))
        # Missing SUMO files are errors, never zero traffic in the legacy parser.
        for output in (
            paths.tripinfo,
            paths.summary,
            paths.statistic,
            paths.edge_data,
            paths.fcd,
        ):
            if not output.is_file():
                raise ExperimentError(f"SUMO did not produce required output: {output.name}")
        result = parse_existing_sumo_net_result(
            paths=paths,
            district_id=project.project_id,
            scenario_id=run["case_id"],
            controller_id="fixed_time",
            seed=run["seed"],
        )
        _validate_render_vehicle_trace(result.vehicle_trace_frames)
        metrics = result.to_dict()
        # Legacy parser placeholders must not become measured zeros/occupancy in a managed run.
        for field in ("bus_passenger_delay_seconds", "reroute_count", "failed_route_count"):
            metrics[field] = None
        _write_json(
            directory / "result.json",
            {
                "schema_version": "debug_sumo_result.v1",
                **identity,
                "mode": "debug",
                "evaluator_cost": None,
                "metrics": metrics,
                "limitations": [
                    "Debug output does not claim research evaluation or acceptance",
                    "Demand accounting is unavailable when no intended-demand ledger is supplied",
                    "Passenger/error/reroute accounting unavailable",
                    "SUMO legacy route-error and teleport settings retained explicitly",
                ],
            },
        )
        with (directory / "vehicle_trace.jsonl").open("x", encoding="utf-8") as handle:
            for frame in result.vehicle_trace_frames:
                handle.write(
                    json.dumps({**frame, **identity}, ensure_ascii=False, allow_nan=False) + "\n"
                )
        # Verify frozen source/map/routes/binary after execution before claiming artifacts reusable.
        verify_run(directory)
        write_render_inputs(directory=directory, run=run, project=project)
        _write_runtime_accounting(
            directory=directory,
            run=run,
            identity=identity,
            paths=paths,
            execution_status="debug_simulation_finished",
        )
        _write_json(
            directory / "execution_result.json",
            {
                "schema_version": "run_execution_result.v1",
                **identity,
                "status": "debug_simulation_finished",
                "sumo_version": version,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )
        seal_run(directory)
        return {"status": "outputs_verified", **identity, "mode": "debug"}
    except Exception as exc:
        accounting_error = None
        try:
            _write_runtime_accounting(
                directory=directory,
                run=run,
                identity=identity,
                paths=paths,
                execution_status="debug_simulation_failed_or_partial",
            )
        except Exception as error:
            accounting_error = error
        failure_path = directory / "execution_result.json"
        if not failure_path.exists():
            failure_result = {
                "schema_version": "run_execution_result.v1",
                **identity,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "finished_at": datetime.now(UTC).isoformat(),
            }
            if accounting_error is not None:
                failure_result["runtime_accounting_error"] = str(accounting_error)
            _write_json(failure_path, failure_result)
        raise
