from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ai_quantum_hvtc.experiments.runtime_accounting import (
    build_runtime_trip_accounting,
    validate_intended_demand_routes,
)
from ai_quantum_hvtc.experiments.store import ExperimentError, file_record


def _ledger_path(tmp_path: Path) -> Path:
    path = tmp_path / "intended_demand_ledger.json"
    trips = [
        _trip("arrived", "routed"),
        _trip("unfinished", "routed"),
        _trip("vaporized", "routed"),
        _trip("not_routed", "not_routed"),
        _trip("not_observed", "routed"),
    ]
    path.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": trips,
            }
        ),
        encoding="utf-8",
    )
    return path


def _trip(trip_id: str, route_status: str) -> dict[str, Any]:
    return {
        "trip_id": trip_id,
        "source_flow_id": "flow",
        "trip_purpose": "commute",
        "vehicle_type_id": "PRIVATE_CAR",
        "vehicle_class": "passenger",
        "intended_departure_seconds": 0.0,
        "origin_zone_id": "origin",
        "destination_zone_id": "destination",
        "origin_edge_id": "E1",
        "destination_edge_id": "E2",
        "route_status": route_status,
        "failure_reason": "unknown" if route_status == "not_routed" else None,
    }


def _runtime_run(tmp_path: Path, *, ledger_path: Path | None) -> dict[str, Any]:
    routes = tmp_path / "routes.rou.xml"
    routes.write_text(
        "<routes>"
        '<vehicle id="arrived" route="r1"/>'
        '<vehicle id="unfinished" route="r1"/>'
        '<vehicle id="vaporized" route="r1"/>'
        '<vehicle id="not_observed" route="r1"/>'
        "</routes>",
        encoding="utf-8",
    )
    inputs = {"routes": file_record(routes)}
    if ledger_path is not None:
        inputs["intended_demand_ledger"] = file_record(ledger_path)
    return {"inputs": inputs}


def _build(
    tmp_path: Path,
    *,
    run: dict[str, Any],
    tripinfo: str | None,
    summary: str | None = (
        '<summary><step time="10" loaded="5" inserted="4" waiting="0" '
        'arrived="1" running="3" ended="1"/></summary>'
    ),
    statistic: str | None = (
        '<statistics><teleports total="0"/><safety collisions="0"/></statistics>'
    ),
) -> dict[str, Any]:
    routes = Path(run["inputs"]["routes"]["path"])
    tripinfo_path = tmp_path / "tripinfo.xml"
    summary_path = tmp_path / "summary.xml"
    statistic_path = tmp_path / "statistic.xml"
    for path, contents in (
        (tripinfo_path, tripinfo),
        (summary_path, summary),
        (statistic_path, statistic),
    ):
        if contents is not None:
            path.write_text(contents, encoding="utf-8")
    return build_runtime_trip_accounting(
        run=run,
        identity={"experiment_id": "exp", "run_id": "run", "run_sha256": "a" * 64},
        routes_path=routes,
        tripinfo_path=tripinfo_path,
        summary_path=summary_path,
        statistic_path=statistic_path,
        execution_status="debug_simulation_finished",
    )


def test_no_ledger_is_explicitly_unavailable_and_never_synthesized(tmp_path: Path) -> None:
    run = _runtime_run(tmp_path, ledger_path=None)

    accounting = _build(
        tmp_path,
        run=run,
        tripinfo='<tripinfos><tripinfo id="arrived" arrival="10"/></tripinfos>',
    )

    demand = accounting["demand_accounting"]
    assert demand["status"] == "unavailable"
    assert demand["reason"] == "no_intended_demand_ledger_supplied"
    assert demand["intended_trip_count"] is None
    assert demand["trips"] == []
    assert all(value is None for value in demand["status_counts"].values())
    assert accounting["aggregate_simulation_accounting"]["summary"]["arrived"] == 1
    assert accounting["aggregate_simulation_accounting"]["statistic"]["total_teleports"] == 0


def test_ledger_join_classifies_supported_tripinfo_states_by_exact_id(tmp_path: Path) -> None:
    ledger_path = _ledger_path(tmp_path)
    run = _runtime_run(tmp_path, ledger_path=ledger_path)
    tripinfo = """<tripinfos>
      <tripinfo id="arrived" arrival="10.5" vaporized=""/>
      <tripinfo id="unfinished" arrival="-1" vaporized="false"/>
      <tripinfo id="vaporized" arrival="-1" vaporized="true"/>
    </tripinfos>"""

    accounting = _build(tmp_path, run=run, tripinfo=tripinfo)

    demand = accounting["demand_accounting"]
    by_id = {row["trip_id"]: row for row in demand["trips"]}
    assert demand["status"] == "available"
    assert by_id["arrived"]["status"] == "arrived"
    assert by_id["unfinished"]["status"] == "unfinished"
    assert by_id["vaporized"]["status"] == "vaporized"
    assert by_id["not_routed"]["status"] == "not_routed"
    assert by_id["not_observed"]["status"] == "not_observed"
    assert demand["status_counts"] == {
        "arrived": 1,
        "unfinished": 1,
        "vaporized": 1,
        "not_routed": 1,
        "not_observed": 1,
        "unverified": 0,
    }


def test_mismatched_route_ids_preserve_ledger_rows_as_unverified(tmp_path: Path) -> None:
    ledger_path = _ledger_path(tmp_path)
    run = _runtime_run(tmp_path, ledger_path=ledger_path)
    routes = Path(run["inputs"]["routes"]["path"])
    routes.write_text('<routes><vehicle id="unexpected"/></routes>', encoding="utf-8")

    with pytest.raises(ExperimentError, match="exactly match"):
        validate_intended_demand_routes(ledger_path, routes)

    accounting = _build(
        tmp_path,
        run=run,
        tripinfo='<tripinfos><tripinfo id="arrived" arrival="10"/></tripinfos>',
    )
    demand = accounting["demand_accounting"]
    assert demand["status"] == "unavailable"
    assert len(demand["trips"]) == 5
    assert demand["intended_trip_count"] is None
    assert demand["raw_ledger_row_count"] == 5
    assert all(row["status"] == "unverified" for row in demand["trips"])
    assert all(value is None for value in demand["status_counts"].values())


def test_invalid_ledger_contract_retains_raw_rows_but_not_trusted_count(
    tmp_path: Path,
) -> None:
    ledger_path = _ledger_path(tmp_path)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["count_unit"] = "person_trip"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    run = _runtime_run(tmp_path, ledger_path=ledger_path)

    accounting = _build(
        tmp_path,
        run=run,
        tripinfo='<tripinfos><tripinfo id="arrived" arrival="10"/></tripinfos>',
    )

    demand = accounting["demand_accounting"]
    assert demand["intended_trip_count"] is None
    assert demand["raw_ledger_row_count"] == 5
    assert len(demand["trips"]) == 5
    assert all(row["status"] == "unverified" for row in demand["trips"])


def test_valid_empty_ledger_and_route_input_report_zero_requested_trips(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "empty_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": [],
            }
        ),
        encoding="utf-8",
    )
    run = _runtime_run(tmp_path, ledger_path=ledger_path)
    routes = Path(run["inputs"]["routes"]["path"])
    routes.write_text("<routes />", encoding="utf-8")
    run["inputs"]["routes"] = file_record(routes)

    accounting = _build(
        tmp_path,
        run=run,
        tripinfo="<tripinfos />",
    )

    demand = accounting["demand_accounting"]
    assert demand["status"] == "available"
    assert demand["intended_trip_count"] == 0
    assert demand["raw_ledger_row_count"] == 0
    assert demand["trips"] == []
    assert all(value == 0 for value in demand["status_counts"].values())


def test_dynamic_route_flows_fail_closed_instead_of_appearing_as_zero_trips(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "empty_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": "intended_demand_ledger.v1",
                "reconciliation_status": "reconciled",
                "count_unit": "requested_vehicle_trip",
                "trips": [],
            }
        ),
        encoding="utf-8",
    )
    run = _runtime_run(tmp_path, ledger_path=ledger_path)
    routes = Path(run["inputs"]["routes"]["path"])
    routes.write_text(
        '<routes><flow id="dynamic" begin="0" end="10" number="1"/></routes>',
        encoding="utf-8",
    )
    run["inputs"]["routes"] = file_record(routes)

    with pytest.raises(ExperimentError, match="dynamic flow elements"):
        validate_intended_demand_routes(ledger_path, routes)

    accounting = _build(tmp_path, run=run, tripinfo="<tripinfos />")
    demand = accounting["demand_accounting"]
    assert demand["intended_trip_count"] is None
    assert demand["raw_ledger_row_count"] == 0
    assert all(value is None for value in demand["status_counts"].values())


@pytest.mark.parametrize(
    "tripinfo",
    [
        None,
        "<tripinfos>",
        '<tripinfos><tripinfo id="arrived" arrival="NaN"/></tripinfos>',
        '<tripinfos><tripinfo id="arrived" arrival="-1"/></tripinfos>',
        (
            '<tripinfos><tripinfo id="arrived" arrival="10"/>'
            '<tripinfo id="arrived" arrival="11"/></tripinfos>'
        ),
    ],
)
def test_invalid_or_incomplete_tripinfo_keeps_rows_and_counts_null(
    tmp_path: Path, tripinfo: str | None
) -> None:
    ledger_path = _ledger_path(tmp_path)
    run = _runtime_run(tmp_path, ledger_path=ledger_path)

    accounting = _build(tmp_path, run=run, tripinfo=tripinfo)

    demand = accounting["demand_accounting"]
    assert demand["status"] == "partial"
    assert len(demand["trips"]) == 5
    by_id = {row["trip_id"]: row for row in demand["trips"]}
    assert by_id["not_routed"]["status"] == "not_routed"
    assert all(value is None for value in demand["status_counts"].values())


def test_missing_or_malformed_aggregate_fields_remain_null(tmp_path: Path) -> None:
    ledger_path = _ledger_path(tmp_path)
    run = _runtime_run(tmp_path, ledger_path=ledger_path)
    accounting = _build(
        tmp_path,
        run=run,
        tripinfo='<tripinfos><tripinfo id="arrived" arrival="10"/></tripinfos>',
        summary=(
            '<summary><step time="NaN" loaded="bad" inserted="0" waiting="0" '
            'arrived="0" running="0" ended="0"/></summary>'
        ),
        statistic='<statistics><teleports/><safety collisions="-1"/></statistics>',
    )

    aggregate = accounting["aggregate_simulation_accounting"]
    assert aggregate["status"] == "partial"
    assert aggregate["summary"]["loaded"] is None
    assert aggregate["summary"]["inserted"] == 0
    assert aggregate["summary"]["final_step_time_seconds"] is None
    assert aggregate["statistic"]["total_teleports"] is None
    assert aggregate["statistic"]["safety_collisions"] is None
