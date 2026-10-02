from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from ai_quantum_hvtc.experiments.store import (
    ExperimentError,
    validate_id,
    verify_experiment,
    verify_run,
    verify_run_output,
)

from ..context import DashboardContext, get_context
from ..schemas import (
    ExperimentListItem,
    ExperimentListResponse,
    ExperimentOutputSummary,
    ExperimentRuntimeAccountingResponse,
    ExperimentRunVerification,
    RuntimeAggregateAccountingView,
    RuntimeDemandAccountingView,
    RuntimeStatisticAccountingView,
    RuntimeSummaryAccountingView,
    RuntimeTripAccountingView,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])

Ctx = Annotated[DashboardContext, Depends(get_context)]

_DEMAND_STATUSES = {
    "arrived",
    "unfinished",
    "vaporized",
    "not_routed",
    "not_observed",
    "unverified",
}
_SUMMARY_COUNTERS = ("loaded", "inserted", "waiting", "arrived", "running", "ended")
_KNOWN_LIMITATIONS = (
    "Vehicle and simulator event counters are not person or occupancy metrics.",
    "These outputs do not establish action-safety validation or research acceptance.",
)
_COLLISION_SAFETY_LIMITATION = "Simulator collision counts do not establish complete action safety."


def _configured_root(
    ctx: DashboardContext,
) -> tuple[Path | None, Literal["not_configured", "unavailable", "available"]]:
    configured = ctx.config.experiments_dir
    if configured is None:
        return None, "not_configured"
    try:
        root = configured.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "unavailable"
    if not root.is_dir():
        return None, "unavailable"
    return root, "available"


def _direct_child_directory(root: Path, child_id: str) -> Path | None:
    candidate = root / child_id
    try:
        if candidate.is_symlink():
            return None
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if resolved.parent != root or not resolved.is_dir():
        return None
    return resolved


def _discover_run_ids(experiment_dir: Path) -> list[str]:
    runs_dir = _direct_child_directory(experiment_dir, "runs")
    if runs_dir is None:
        return []
    try:
        children = sorted(runs_dir.iterdir(), key=lambda path: path.name)
    except OSError:
        return []
    discovered: list[str] = []
    for child in children:
        try:
            run_id = validate_id(child.name)
        except ExperimentError:
            continue
        if _direct_child_directory(runs_dir, run_id) is not None:
            discovered.append(run_id)
    return discovered


def _read_accounting_json(payload: bytes) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise ValueError("non-finite JSON number")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExperimentError("runtime accounting JSON is invalid") from exc
    if not isinstance(value, dict):
        raise ExperimentError("runtime accounting JSON must be an object")
    return value


def _accounting_status(
    value: object,
) -> Literal["available", "partial", "unavailable"]:
    if value == "available":
        return "available"
    if value == "partial":
        return "partial"
    if value == "unavailable":
        return "unavailable"
    raise ExperimentError("runtime accounting status is invalid")


def _optional_nonnegative_count(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ExperimentError("runtime accounting count is invalid")
    return value


def _optional_finite_time(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentError("runtime accounting time is invalid")
    if not math.isfinite(value):
        raise ExperimentError("runtime accounting time is non-finite")
    if value < 0:
        raise ExperimentError("runtime accounting time is negative")
    return float(value)


def _sanitize_runtime_accounting(
    payload: bytes,
    *,
    experiment_id: str,
    run: dict[str, Any],
) -> RuntimeTripAccountingView:
    document = _read_accounting_json(payload)
    if (
        document.get("schema_version") != "runtime_trip_accounting.v1"
        or document.get("experiment_id") != experiment_id
        or document.get("run_id") != run.get("run_id")
        or document.get("run_sha256") != run.get("content_sha256")
    ):
        raise ExperimentError("runtime accounting identity or schema is invalid")
    raw_execution_status = document.get("execution_status")
    if raw_execution_status == "debug_simulation_finished":
        execution_status: Literal[
            "debug_simulation_finished",
            "debug_simulation_failed_or_partial",
        ] = "debug_simulation_finished"
    elif raw_execution_status == "debug_simulation_failed_or_partial":
        execution_status = "debug_simulation_failed_or_partial"
    else:
        raise ExperimentError("runtime accounting execution status is invalid")
    if document.get("evidence_scope") != "managed_debug_runtime_accounting_only":
        raise ExperimentError("runtime accounting evidence scope is invalid")
    if not isinstance(document.get("source_inputs"), dict) or not isinstance(
        document.get("source_outputs"), dict
    ):
        raise ExperimentError("runtime accounting provenance is malformed")

    demand = document.get("demand_accounting")
    aggregate = document.get("aggregate_simulation_accounting")
    if not isinstance(demand, dict) or not isinstance(aggregate, dict):
        raise ExperimentError("runtime accounting sections are malformed")
    if demand.get("scope") != "per_intended_requested_vehicle_trip":
        raise ExperimentError("runtime demand scope is invalid")
    demand_status = _accounting_status(demand.get("status"))
    reason = demand.get("reason")
    if reason is not None and (
        not isinstance(reason, str)
        or reason
        not in {
            "no_intended_demand_ledger_supplied",
            "one_or_more_sources_or_trip_rows_unverified",
        }
    ):
        raise ExperimentError("runtime demand reason is invalid")
    raw_status_counts = demand.get("status_counts")
    if not isinstance(raw_status_counts, dict) or set(raw_status_counts) != _DEMAND_STATUSES:
        raise ExperimentError("runtime demand status counts are malformed")
    trip_rows = demand.get("trips")
    if (
        not isinstance(trip_rows, list)
        or not all(isinstance(row, dict) for row in trip_rows)
        or not isinstance(demand.get("errors"), list)
    ):
        raise ExperimentError("runtime demand details are malformed")
    if not all(isinstance(error, str) for error in demand["errors"]):
        raise ExperimentError("runtime demand errors are malformed")
    unfinished_requested = demand.get("tripinfo_unfinished_requested")
    if unfinished_requested is not None and type(unfinished_requested) is not bool:
        raise ExperimentError("runtime TripInfo request flag is malformed")
    demand_view = RuntimeDemandAccountingView(
        status=demand_status,
        scope="per_intended_requested_vehicle_trip",
        reason=reason,
        intended_trip_count=_optional_nonnegative_count(demand.get("intended_trip_count")),
        raw_ledger_row_count=_optional_nonnegative_count(demand.get("raw_ledger_row_count")),
        status_counts={
            status: _optional_nonnegative_count(raw_status_counts[status])
            for status in sorted(_DEMAND_STATUSES)
        },
        tripinfo_observed_count=_optional_nonnegative_count(demand.get("tripinfo_observed_count")),
        tripinfo_unfinished_requested=unfinished_requested,
    )

    if aggregate.get("scope") != "whole_simulation_vehicle_and_event_counters":
        raise ExperimentError("runtime aggregate scope is invalid")
    summary = aggregate.get("summary")
    statistic = aggregate.get("statistic")
    if not isinstance(summary, dict) or not isinstance(statistic, dict):
        raise ExperimentError("runtime aggregate sections are malformed")
    raw_limitations = aggregate.get("limitations")
    if not isinstance(raw_limitations, list) or not all(
        isinstance(item, str) for item in raw_limitations
    ):
        raise ExperimentError("runtime accounting limitations are malformed")
    if not set(_KNOWN_LIMITATIONS).issubset(raw_limitations):
        raise ExperimentError("runtime accounting limitations are incomplete")
    if not isinstance(summary.get("source"), str) or not isinstance(statistic.get("source"), str):
        raise ExperimentError("runtime aggregate source labels are malformed")
    for section in (summary, statistic):
        error = section.get("error")
        if error is not None and not isinstance(error, str):
            raise ExperimentError("runtime aggregate error field is malformed")
    summary_view = RuntimeSummaryAccountingView(
        status=_accounting_status(summary.get("status")),
        final_step_time_seconds=_optional_finite_time(summary.get("final_step_time_seconds")),
        **{key: _optional_nonnegative_count(summary.get(key)) for key in _SUMMARY_COUNTERS},
    )
    statistic_view = RuntimeStatisticAccountingView(
        status=_accounting_status(statistic.get("status")),
        total_teleports=_optional_nonnegative_count(statistic.get("total_teleports")),
        safety_collisions=_optional_nonnegative_count(statistic.get("safety_collisions")),
    )
    return RuntimeTripAccountingView(
        execution_status=execution_status,
        evidence_scope="managed_debug_runtime_accounting_only",
        demand_accounting=demand_view,
        aggregate_simulation_accounting=RuntimeAggregateAccountingView(
            scope="whole_simulation_vehicle_and_event_counters",
            status=_accounting_status(aggregate.get("status")),
            summary=summary_view,
            statistic=statistic_view,
            limitations=[*_KNOWN_LIMITATIONS, _COLLISION_SAFETY_LIMITATION],
        ),
    )


def _verification_failed(experiment_id: str, run_id: str) -> ExperimentRunVerification:
    return ExperimentRunVerification(
        configured=True,
        state="verification_failed",
        experiment_id=experiment_id,
        run_id=run_id,
    )


@router.get("", response_model=ExperimentListResponse)
def list_experiments(ctx: Ctx) -> ExperimentListResponse:
    root, status = _configured_root(ctx)
    if root is None:
        return ExperimentListResponse(
            configured=status != "not_configured",
            status=status,
        )
    try:
        children = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return ExperimentListResponse(configured=True, status="unavailable")

    experiments: list[ExperimentListItem] = []
    for child in children:
        try:
            experiment_id = validate_id(child.name)
        except ExperimentError:
            continue
        experiment_dir = _direct_child_directory(root, experiment_id)
        if experiment_dir is None:
            continue
        try:
            manifest = verify_experiment(experiment_dir)
        except Exception:
            # Manifests can contain arbitrary source paths; never return verifier details.
            experiments.append(
                ExperimentListItem(
                    experiment_id=experiment_id,
                    state="verification_failed",
                )
            )
            continue
        protocol = manifest.get("protocol")
        mode = protocol.get("mode") if isinstance(protocol, dict) else None
        experiments.append(
            ExperimentListItem(
                experiment_id=experiment_id,
                state="verified",
                content_sha256=manifest.get("content_sha256"),
                project_id=manifest.get("project_id"),
                mode=mode if isinstance(mode, str) else None,
                discovered_run_ids=_discover_run_ids(experiment_dir),
            )
        )
    return ExperimentListResponse(
        configured=True,
        status="available",
        experiments=experiments,
    )


@router.get(
    "/{experiment_id}/runs/{run_id}",
    response_model=ExperimentRunVerification,
)
def verify_experiment_run(
    experiment_id: str,
    run_id: str,
    ctx: Ctx,
) -> ExperimentRunVerification:
    if ctx.config.experiments_dir is None:
        return ExperimentRunVerification(configured=False, state="not_configured")
    try:
        experiment_id = validate_id(experiment_id)
        run_id = validate_id(run_id)
    except ExperimentError as exc:
        raise HTTPException(status_code=422, detail="invalid experiment or run ID") from exc

    root, status = _configured_root(ctx)
    if root is None:
        return ExperimentRunVerification(
            configured=True,
            state="unavailable" if status == "unavailable" else "not_configured",
        )
    experiment_dir = _direct_child_directory(root, experiment_id)
    if experiment_dir is None:
        return ExperimentRunVerification(
            configured=True,
            state="not_found",
            experiment_id=experiment_id,
            run_id=run_id,
        )

    runs_resolved = _direct_child_directory(experiment_dir, "runs")
    if runs_resolved is None:
        return ExperimentRunVerification(
            configured=True,
            state="not_found",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    run_dir = _direct_child_directory(runs_resolved, run_id)
    if run_dir is None:
        return ExperimentRunVerification(
            configured=True,
            state="not_found",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    try:
        verified = verify_run(run_dir)
        run: dict[str, Any] = verified["run"]
        output_manifest = verified.get("outputs")
        expected_outputs = run["expected_outputs"]
        if not isinstance(expected_outputs, dict):
            raise ExperimentError("invalid expected outputs")
        outputs: list[ExperimentOutputSummary] = []
        for role in sorted(expected_outputs):
            role_id = validate_id(role)
            if verified["state"] == "outputs_verified":
                if not isinstance(output_manifest, dict):
                    raise ExperimentError("missing verified output manifest")
                output_files = output_manifest.get("files")
                if not isinstance(output_files, dict):
                    raise ExperimentError("invalid verified output manifest")
                record = output_files.get(role)
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("sha256"), str)
                    or type(record.get("bytes")) is not int
                ):
                    raise ExperimentError("invalid verified output record")
                outputs.append(
                    ExperimentOutputSummary(
                        role=role_id,
                        state="verified",
                        sha256=record["sha256"],
                        bytes=record["bytes"],
                    )
                )
            else:
                outputs.append(ExperimentOutputSummary(role=role_id, state="unverified"))
        return ExperimentRunVerification(
            configured=True,
            state=verified["state"],
            experiment_id=run["experiment_id"],
            run_id=run["run_id"],
            content_sha256=run["content_sha256"],
            mode=run["mode"],
            case_id=run["case_id"],
            split=run["split"],
            seed=run["seed"],
            controller_id=run["controller_id"],
            outputs=outputs,
        )
    except Exception:
        return _verification_failed(experiment_id, run_id)


@router.get(
    "/{experiment_id}/runs/{run_id}/runtime-accounting",
    response_model=ExperimentRuntimeAccountingResponse,
)
def runtime_trip_accounting_view(
    experiment_id: str,
    run_id: str,
    ctx: Ctx,
) -> ExperimentRuntimeAccountingResponse:
    if ctx.config.experiments_dir is None:
        return ExperimentRuntimeAccountingResponse(
            configured=False,
            state="not_configured",
        )
    try:
        experiment_id = validate_id(experiment_id)
        run_id = validate_id(run_id)
    except ExperimentError as exc:
        raise HTTPException(status_code=422, detail="invalid experiment or run ID") from exc

    root, status = _configured_root(ctx)
    if root is None:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="unavailable" if status == "unavailable" else "not_configured",
        )
    experiment_dir = _direct_child_directory(root, experiment_id)
    runs_dir = (
        _direct_child_directory(experiment_dir, "runs") if experiment_dir is not None else None
    )
    run_dir = _direct_child_directory(runs_dir, run_id) if runs_dir is not None else None
    if run_dir is None:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="not_found",
            experiment_id=experiment_id,
            run_id=run_id,
        )

    try:
        verified, payload = verify_run_output(run_dir, "runtime_accounting")
        run = verified["run"]
    except Exception:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="verification_failed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    if verified["state"] == "unsealed":
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="unsealed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    if verified["state"] != "outputs_verified":
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="verification_failed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    expected_outputs = run.get("expected_outputs")
    if not isinstance(expected_outputs, dict):
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="verification_failed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    if "runtime_accounting" not in expected_outputs:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="unavailable",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    if payload is None:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="verification_failed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    try:
        accounting = _sanitize_runtime_accounting(
            payload,
            experiment_id=experiment_id,
            run=run,
        )
    except Exception:
        return ExperimentRuntimeAccountingResponse(
            configured=True,
            state="verification_failed",
            experiment_id=experiment_id,
            run_id=run_id,
        )
    return ExperimentRuntimeAccountingResponse(
        configured=True,
        state="available",
        experiment_id=experiment_id,
        run_id=run_id,
        accounting=accounting,
    )
