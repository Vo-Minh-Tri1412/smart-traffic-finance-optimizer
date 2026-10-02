"""Fail-closed runtime accounting for managed SUMO debug runs."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .store import ExperimentError, file_record, read_json

_TRIP_STATUSES = (
    "arrived",
    "unfinished",
    "vaporized",
    "not_routed",
    "not_observed",
    "unverified",
)
_SUMMARY_COUNTS = ("loaded", "inserted", "waiting", "arrived", "running", "ended")
_INTENDED_FIELDS = (
    "trip_id",
    "source_flow_id",
    "trip_purpose",
    "vehicle_type_id",
    "vehicle_class",
    "intended_departure_seconds",
    "origin_zone_id",
    "destination_zone_id",
    "origin_edge_id",
    "destination_edge_id",
)


def validate_intended_demand_routes(ledger_path: Path, routes_path: Path) -> None:
    """Reject a supplied ledger unless its routed IDs exactly match route input IDs."""
    ledger, rows, errors = _load_ledger(ledger_path)
    route_ids, route_error = _route_input_vehicle_ids(routes_path)
    if route_error:
        errors.append(route_error)
    if ledger is not None and route_ids is not None:
        routed_ids = {
            row["trip_id"]
            for row in rows
            if row["trip_id"] is not None and row["ledger_route_status"] == "routed"
        }
        if routed_ids != route_ids:
            errors.append("routed ledger IDs do not exactly match route input vehicle IDs")
    if errors:
        message = "; ".join(errors)
        raise ExperimentError("intended-demand ledger/route input validation failed: " + message)


def build_runtime_trip_accounting(
    *,
    run: dict[str, Any],
    identity: dict[str, Any],
    routes_path: Path,
    tripinfo_path: Path,
    summary_path: Path,
    statistic_path: Path,
    execution_status: str,
) -> dict[str, Any]:
    tripinfo_rows, tripinfo_error = _tripinfo_rows(tripinfo_path)
    summary = _summary_accounting(summary_path)
    statistic = _statistic_accounting(statistic_path)
    demand = _demand_accounting(
        run=run,
        routes_path=routes_path,
        tripinfo_rows=tripinfo_rows,
        tripinfo_error=tripinfo_error,
    )
    return {
        "schema_version": "runtime_trip_accounting.v1",
        **identity,
        "execution_status": execution_status,
        "evidence_scope": "managed_debug_runtime_accounting_only",
        "source_inputs": {
            "routes": run["inputs"].get("routes"),
            "intended_demand_ledger": run["inputs"].get("intended_demand_ledger"),
        },
        "source_outputs": {
            "tripinfo": _optional_file_record(tripinfo_path),
            "summary": _optional_file_record(summary_path),
            "statistic": _optional_file_record(statistic_path),
        },
        "demand_accounting": demand,
        "aggregate_simulation_accounting": {
            "scope": "whole_simulation_vehicle_and_event_counters",
            "status": _combined_status(summary["status"], statistic["status"]),
            "summary": summary,
            "statistic": statistic,
            "limitations": [
                "Vehicle and simulator event counters are not person or occupancy metrics.",
                "These outputs do not establish action-safety validation or research acceptance.",
            ],
        },
    }


def _demand_accounting(
    *,
    run: dict[str, Any],
    routes_path: Path,
    tripinfo_rows: dict[str, dict[str, str]],
    tripinfo_error: str | None,
) -> dict[str, Any]:
    ledger_record = run["inputs"].get("intended_demand_ledger")
    if ledger_record is None:
        return {
            "status": "unavailable",
            "scope": "per_intended_requested_vehicle_trip",
            "reason": "no_intended_demand_ledger_supplied",
            "intended_trip_count": None,
            "raw_ledger_row_count": None,
            "status_counts": {status: None for status in _TRIP_STATUSES},
            "trips": [],
            "errors": ["No intended-demand ledger was supplied; route input is not a ledger."],
        }

    ledger, rows, errors = _load_ledger(Path(ledger_record["path"]))
    route_ids, route_error = _route_input_vehicle_ids(routes_path)
    if route_error:
        errors.append(route_error)
    if ledger is not None and route_ids is not None:
        routed_ids = {
            row["trip_id"]
            for row in rows
            if row["trip_id"] is not None and row["ledger_route_status"] == "routed"
        }
        if routed_ids != route_ids:
            errors.append("routed ledger IDs do not exactly match route input vehicle IDs")

    contract_valid = not errors
    if tripinfo_error:
        errors.append(tripinfo_error)
    routed_ids = {
        row["trip_id"]
        for row in rows
        if row["trip_id"] is not None and row["ledger_route_status"] == "routed"
    }
    extra_tripinfo_ids = set(tripinfo_rows) - routed_ids
    if extra_tripinfo_ids:
        errors.append(
            "TripInfo contains IDs absent from routed intended-demand rows: "
            f"{sorted(extra_tripinfo_ids)[:5]}"
        )

    tripinfo_valid = tripinfo_error is None and not extra_tripinfo_ids
    for row in rows:
        route_status = row["ledger_route_status"]
        trip_id = row["trip_id"]
        if not contract_valid:
            row["status"] = "unverified"
            row["unverified_reason"] = "ledger_or_route_input_invalid"
            continue
        if route_status == "not_routed":
            row["status"] = "not_routed"
            continue
        if not tripinfo_valid:
            row["status"] = "unverified"
            row["unverified_reason"] = "tripinfo_unavailable_or_invalid"
            continue
        tripinfo = tripinfo_rows.get(trip_id)
        if tripinfo is None:
            row["status"] = "not_observed"
            row["tripinfo_evidence"] = None
            continue
        status, evidence, reason = _classify_tripinfo(tripinfo)
        row["status"] = status
        row["tripinfo_evidence"] = evidence
        if reason:
            row["unverified_reason"] = reason

    unverified_count = sum(row["status"] == "unverified" for row in rows)
    complete = contract_valid and tripinfo_valid and unverified_count == 0
    counts: dict[str, int | None]
    if complete:
        counts = {status: sum(row["status"] == status for row in rows) for status in _TRIP_STATUSES}
    else:
        counts = {status: None for status in _TRIP_STATUSES}
    status = (
        "available"
        if complete
        else "partial"
        if any(row["status"] != "unverified" for row in rows)
        else "unavailable"
    )
    return {
        "status": status,
        "scope": "per_intended_requested_vehicle_trip",
        "reason": None if complete else "one_or_more_sources_or_trip_rows_unverified",
        "intended_trip_count": len(rows) if contract_valid else None,
        "raw_ledger_row_count": len(rows),
        "status_counts": counts,
        "tripinfo_observed_count": len(tripinfo_rows) if tripinfo_error is None else None,
        "tripinfo_unfinished_requested": True,
        "trips": rows,
        "errors": errors,
    }


def _load_ledger(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        ledger = read_json(path)
    except (ExperimentError, OSError, ValueError) as exc:
        return None, [], [f"could not read intended-demand ledger: {exc}"]

    if ledger.get("schema_version") != "intended_demand_ledger.v1":
        errors.append("unsupported intended-demand ledger schema")
    if ledger.get("reconciliation_status") != "reconciled":
        errors.append("intended-demand ledger is not reconciled")
    if ledger.get("count_unit") != "requested_vehicle_trip":
        errors.append("intended-demand ledger count_unit is not requested_vehicle_trip")

    source_rows = ledger.get("trips")
    if not isinstance(source_rows, list):
        errors.append("intended-demand ledger trips must be an array")
        return ledger, [], errors

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, source_row in enumerate(source_rows):
        if not isinstance(source_row, dict):
            errors.append(f"intended-demand ledger row {index} is not an object")
            rows.append(
                {
                    "trip_id": None,
                    "ledger_route_status": None,
                    "status": "unverified",
                    "intended_trip": source_row,
                    "unverified_reason": "malformed_ledger_row",
                }
            )
            continue
        trip_id = source_row.get("trip_id")
        if not isinstance(trip_id, str) or not trip_id or trip_id != trip_id.strip():
            errors.append(f"intended-demand ledger row {index} has a malformed trip ID")
            trip_id = None
        elif trip_id in seen_ids:
            errors.append(f"intended-demand ledger contains duplicate trip ID {trip_id!r}")
        else:
            seen_ids.add(trip_id)
        route_status = source_row.get("route_status")
        if not isinstance(route_status, str) or route_status not in {"routed", "not_routed"}:
            errors.append(f"intended-demand ledger row {index} has invalid route_status")
            route_status = None
        rows.append(
            {
                "trip_id": trip_id,
                "ledger_route_status": route_status,
                "status": "unverified",
                "intended_trip": {key: source_row.get(key) for key in _INTENDED_FIELDS},
                "unverified_reason": None,
            }
        )
    return ledger, rows, errors


def _route_input_vehicle_ids(path: Path) -> tuple[set[str] | None, str | None]:
    if not path.is_file():
        return None, f"route input unavailable: {path.name}"
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return None, f"route input is malformed: {exc}"
    if _tag(root.tag) != "routes":
        return None, "route input root is not routes"
    vehicle_ids: set[str] = set()
    for element in root.iter():
        tag = _tag(element.tag)
        if tag == "trip":
            return None, "route input contains unresolved trip elements, expected routed vehicles"
        if tag in {"flow", "personFlow", "containerFlow"}:
            return None, "route input contains dynamic flow elements, expected explicit vehicle IDs"
        if tag != "vehicle":
            continue
        vehicle_id = element.attrib.get("id", "")
        if not vehicle_id or vehicle_id != vehicle_id.strip():
            return None, "route input contains a vehicle with malformed ID"
        if vehicle_id in vehicle_ids:
            return None, f"route input contains duplicate vehicle ID {vehicle_id!r}"
        vehicle_ids.add(vehicle_id)
    return vehicle_ids, None


def _tripinfo_rows(path: Path) -> tuple[dict[str, dict[str, str]], str | None]:
    if not path.is_file():
        return {}, f"TripInfo output unavailable: {path.name}"
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {}, f"TripInfo output is malformed: {exc}"
    if _tag(root.tag) != "tripinfos":
        return {}, "TripInfo output root is not tripinfos"
    rows: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if _tag(element.tag) != "tripinfo":
            continue
        trip_id = element.attrib.get("id", "")
        if not trip_id or trip_id != trip_id.strip():
            return rows, "TripInfo contains a row with malformed ID"
        if trip_id in rows:
            return rows, f"TripInfo contains duplicate ID {trip_id!r}"
        rows[trip_id] = dict(element.attrib)
    return rows, None


def _classify_tripinfo(
    row: dict[str, str],
) -> tuple[str, dict[str, Any], str | None]:
    arrival = _finite_float(row.get("arrival"))
    vaporized_value = row.get("vaporized")
    vaporized: bool | None
    if vaporized_value is None:
        vaporized = None
    elif vaporized_value == "":
        # SUMO 1.27 emits an empty attribute for a normally arrived vehicle.
        # Preserve that as absent evidence; arrival itself remains explicit.
        vaporized = None
    elif vaporized_value == "true":
        vaporized = True
    elif vaporized_value == "false":
        vaporized = False
    else:
        vaporized = None
    evidence = {"arrival_seconds": arrival, "vaporized": vaporized}
    if arrival is None:
        return "unverified", evidence, "TripInfo arrival is missing or non-finite"
    if vaporized_value not in (None, "") and vaporized is None:
        return "unverified", evidence, "TripInfo vaporized is not a valid boolean"
    if vaporized is True:
        if arrival >= 0:
            return (
                "unverified",
                evidence,
                "TripInfo marks a trip vaporized with nonnegative arrival",
            )
        return "vaporized", evidence, None
    if arrival >= 0:
        return "arrived", evidence, None
    if arrival == -1 and vaporized is False:
        return "unfinished", evidence, None
    return "unverified", evidence, "negative arrival lacks explicit non-vaporized evidence"


def _summary_accounting(path: Path) -> dict[str, Any]:
    values: dict[str, int | None] = {key: None for key in _SUMMARY_COUNTS}
    if not path.is_file():
        return {
            "status": "unavailable",
            "source": "summary.xml",
            "final_step_time_seconds": None,
            **values,
            "error": "summary output is missing",
        }
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {
            "status": "unavailable",
            "source": "summary.xml",
            "final_step_time_seconds": None,
            **values,
            "error": f"summary output is malformed: {exc}",
        }
    if _tag(root.tag) != "summary":
        return {
            "status": "unavailable",
            "source": "summary.xml",
            "final_step_time_seconds": None,
            **values,
            "error": "summary output root is not summary",
        }
    steps = [element for element in root if _tag(element.tag) == "step"]
    if not steps:
        return {
            "status": "unavailable",
            "source": "summary.xml",
            "final_step_time_seconds": None,
            **values,
            "error": "summary output has no step rows",
        }
    final_step = steps[-1]
    time_seconds = _finite_float(final_step.attrib.get("time"))
    for key in _SUMMARY_COUNTS:
        values[key] = _nonnegative_int(final_step.attrib.get(key))
    missing = [key for key, value in values.items() if value is None]
    if time_seconds is None:
        missing.append("time")
    return {
        "status": "available" if not missing else "partial",
        "source": "summary.xml final step",
        "final_step_time_seconds": time_seconds,
        **values,
        "error": None if not missing else f"summary fields missing or invalid: {missing}",
    }


def _statistic_accounting(path: Path) -> dict[str, Any]:
    values: dict[str, int | None] = {"total_teleports": None, "safety_collisions": None}
    if not path.is_file():
        return {
            "status": "unavailable",
            "source": "statistic.xml",
            **values,
            "error": "statistic output is missing",
        }
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {
            "status": "unavailable",
            "source": "statistic.xml",
            **values,
            "error": f"statistic output is malformed: {exc}",
        }
    if _tag(root.tag) != "statistics":
        return {
            "status": "unavailable",
            "source": "statistic.xml",
            **values,
            "error": "statistic output root is not statistics",
        }
    teleport_rows = [element for element in root if _tag(element.tag) == "teleports"]
    safety_rows = [element for element in root if _tag(element.tag) == "safety"]
    if len(teleport_rows) == 1:
        values["total_teleports"] = _nonnegative_int(teleport_rows[0].attrib.get("total"))
    if len(safety_rows) == 1:
        values["safety_collisions"] = _nonnegative_int(safety_rows[0].attrib.get("collisions"))
    missing = [key for key, value in values.items() if value is None]
    if len(teleport_rows) != 1:
        missing.append("teleports element")
    if len(safety_rows) != 1:
        missing.append("safety element")
    return {
        "status": "available" if not missing else "partial",
        "source": "statistic.xml",
        **values,
        "error": None if not missing else f"statistic fields missing or invalid: {missing}",
    }


def _optional_file_record(path: Path) -> dict[str, Any] | None:
    try:
        return file_record(path) if path.is_file() else None
    except (OSError, ExperimentError):
        return None


def _combined_status(*statuses: str) -> str:
    if all(status == "available" for status in statuses):
        return "available"
    if all(status == "unavailable" for status in statuses):
        return "unavailable"
    return "partial"


def _finite_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _nonnegative_int(value: str | None) -> int | None:
    if value is None or not value.isascii() or not value.isdigit():
        return None
    return int(value)


def _tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]
