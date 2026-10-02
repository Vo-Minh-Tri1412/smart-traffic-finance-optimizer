from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

from ai_quantum_hvtc.reports import (
    baseline_comparison_rows,
    baseline_comparison_to_csv,
    result_to_json,
    result_to_trace_jsonl,
    write_baseline_comparison_report,
)
from ai_quantum_hvtc.reports.export import metrics_summary
from ai_quantum_hvtc.simulation.metrics import SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec


def test_baseline_comparison_rows_measure_improvement_against_fixed_time() -> None:
    rows = baseline_comparison_rows(
        [
            _result("fixed_time", waiting=100.0, throughput=10, emergency=25.0),
            _result(
                "rule_based",
                waiting=70.0,
                throughput=11,
                emergency=10.0,
                controller_interventions=3,
            ),
        ]
    )

    assert rows[0]["interpretation"] == "Mốc so sánh"
    assert rows[1]["waiting_time_saved_vs_fixed_seconds"] == 30.0
    assert rows[1]["waiting_time_saved_vs_fixed_pct"] == 30.0
    assert rows[1]["throughput_gain_vs_fixed"] == 1
    assert rows[1]["emergency_delay_saved_vs_fixed_seconds"] == 15.0
    assert rows[1]["controller_interventions"] == 3
    assert rows[1]["interpretation"] == "Tốt hơn fixed-time trên metric chính"


def test_baseline_comparison_report_writes_csv_and_markdown(tmp_path: Path) -> None:
    rows = baseline_comparison_rows(
        [
            _result("fixed_time", waiting=100.0, throughput=10, emergency=25.0),
            _result("rule_based", waiting=120.0, throughput=9, emergency=30.0),
        ]
    )
    csv_path = tmp_path / "baseline.csv"
    report_path = tmp_path / "baseline.md"

    baseline_comparison_to_csv(rows, csv_path)
    write_baseline_comparison_report(rows, report_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    assert "waiting_time_saved_vs_fixed_seconds" in csv_text
    assert "rule_based" in csv_text
    assert "Báo cáo baseline: normal_weekday" in report_text
    assert "Chưa tốt hơn fixed-time" in report_text


def test_unavailable_sumo_metrics_stay_null_in_reports_and_traces(tmp_path: Path) -> None:
    baseline = replace(
        _result("fixed_time", waiting=100.0, throughput=10, emergency=25.0),
        bus_passenger_delay_seconds=None,
        reroute_count=None,
        failed_route_count=None,
    )
    alternative = replace(
        _result("rule_based", waiting=70.0, throughput=11, emergency=10.0),
        bus_passenger_delay_seconds=None,
        reroute_count=None,
        failed_route_count=None,
    )

    result_path = tmp_path / "result.json"
    result_to_json(baseline, result_path)
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["bus_passenger_delay_seconds"] is None
    assert result_payload["reroute_count"] is None
    assert result_payload["failed_route_count"] is None
    assert metrics_summary(baseline)["bus_passenger_delay_seconds"] is None
    assert metrics_summary(baseline)["reroute_count"] is None
    assert metrics_summary(baseline)["failed_route_count"] is None

    rows = baseline_comparison_rows([baseline, alternative])
    assert rows[0]["bus_passenger_delay_seconds"] is None
    assert rows[1]["bus_passenger_delay_seconds"] is None
    assert rows[1]["bus_passenger_delay_saved_vs_fixed_seconds"] is None
    csv_path = tmp_path / "comparison.csv"
    baseline_comparison_to_csv(rows, csv_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[1]["bus_passenger_delay_seconds"] == ""
    assert csv_rows[1]["bus_passenger_delay_saved_vs_fixed_seconds"] == ""

    trace_path = tmp_path / "trace.jsonl"
    result_to_trace_jsonl(
        baseline,
        load_district_spec(Path("tests/fixtures/specs/toy_public_district_v1.json")),
        trace_path,
    )
    frames = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert frames
    assert all(
        event["type"] != "failed_routes_observed"
        for frame in frames
        for event in frame["events"]
    )


def _result(
    controller_id: str,
    *,
    waiting: float,
    throughput: int,
    emergency: float,
    controller_interventions: int = 0,
) -> SimulationResult:
    return SimulationResult(
        scenario_id="normal_weekday",
        controller_id=controller_id,
        engine_id="sumo_fixture",
        seed=42,
        total_vehicles=12,
        throughput=throughput,
        total_waiting_time_seconds=waiting,
        average_waiting_time_seconds=waiting / 12.0,
        max_queue_vehicles=4.0,
        average_queue_vehicles=2.0,
        stopped_vehicles=2,
        emergency_delay_seconds=emergency,
        bus_passenger_delay_seconds=40.0,
        truck_delay_seconds=30.0,
        reroute_count=0,
        failed_route_count=0,
        controller_interventions=controller_interventions,
    )
