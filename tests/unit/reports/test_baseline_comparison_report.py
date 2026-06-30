from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.reports import (
    baseline_comparison_rows,
    baseline_comparison_to_csv,
    write_baseline_comparison_report,
)
from ai_quantum_hvtc.simulation.metrics import SimulationResult


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
