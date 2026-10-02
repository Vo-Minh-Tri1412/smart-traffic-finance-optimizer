from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.core import ensure_parent_dir
from ai_quantum_hvtc.policy import InvestmentOption
from ai_quantum_hvtc.public_finance import CandidateScore
from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.metrics import SimulationResult
from ai_quantum_hvtc.simulation.traces import trace_frames_from_result

BASELINE_COMPARISON_FIELDS = [
    "scenario_id",
    "controller_id",
    "engine_id",
    "total_vehicles",
    "throughput",
    "average_waiting_time_seconds",
    "total_waiting_time_seconds",
    "max_queue_vehicles",
    "average_queue_vehicles",
    "stopped_vehicles",
    "emergency_delay_seconds",
    "bus_passenger_delay_seconds",
    "truck_delay_seconds",
    "controller_interventions",
    "waiting_time_saved_vs_fixed_seconds",
    "waiting_time_saved_vs_fixed_pct",
    "throughput_gain_vs_fixed",
    "emergency_delay_saved_vs_fixed_seconds",
    "bus_passenger_delay_saved_vs_fixed_seconds",
    "truck_delay_saved_vs_fixed_seconds",
    "interpretation",
]


def result_to_json(result: SimulationResult, path: Path) -> None:
    ensure_parent_dir(path).write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def result_to_trace_jsonl(result: SimulationResult, spec: DistrictSpec, path: Path) -> None:
    ensure_parent_dir(path).write_text(
        "\n".join(
            json.dumps(frame, ensure_ascii=False, sort_keys=True)
            for frame in trace_frames_from_result(result, spec)
        )
        + "\n",
        encoding="utf-8",
    )


def result_vehicle_trace_to_jsonl(result: SimulationResult, path: Path) -> None:
    if not result.vehicle_trace_frames:
        frames: list[dict[str, Any]] = []
    else:
        frames = result.vehicle_trace_frames
    ensure_parent_dir(path).write_text(
        "\n".join(json.dumps(frame, ensure_ascii=False, sort_keys=True) for frame in frames)
        + ("\n" if frames else ""),
        encoding="utf-8",
    )


def candidate_scores_to_csv(scores: list[CandidateScore], path: Path) -> None:
    ensure_parent_dir(path)
    fieldnames = list(scores[0].to_dict()) if scores else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in scores:
            writer.writerow(score.to_dict())


def baseline_comparison_rows(results: list[SimulationResult]) -> list[dict[str, Any]]:
    """Build a controller-vs-fixed-time metric table for baseline review."""

    if not results:
        return []
    baseline = next(
        (result for result in results if result.controller_id == "fixed_time"),
        results[0],
    )
    rows: list[dict[str, Any]] = []
    for result in results:
        waiting_saved = baseline.total_waiting_time_seconds - result.total_waiting_time_seconds
        emergency_saved = baseline.emergency_delay_seconds - result.emergency_delay_seconds
        bus_saved = (
            baseline.bus_passenger_delay_seconds - result.bus_passenger_delay_seconds
            if baseline.bus_passenger_delay_seconds is not None
            and result.bus_passenger_delay_seconds is not None
            else None
        )
        truck_saved = baseline.truck_delay_seconds - result.truck_delay_seconds
        throughput_gain = result.throughput - baseline.throughput
        rows.append(
            {
                "scenario_id": result.scenario_id,
                "controller_id": result.controller_id,
                "engine_id": result.engine_id,
                "total_vehicles": result.total_vehicles,
                "throughput": result.throughput,
                "average_waiting_time_seconds": result.average_waiting_time_seconds,
                "total_waiting_time_seconds": result.total_waiting_time_seconds,
                "max_queue_vehicles": result.max_queue_vehicles,
                "average_queue_vehicles": result.average_queue_vehicles,
                "stopped_vehicles": result.stopped_vehicles,
                "emergency_delay_seconds": result.emergency_delay_seconds,
                "bus_passenger_delay_seconds": result.bus_passenger_delay_seconds,
                "truck_delay_seconds": result.truck_delay_seconds,
                "controller_interventions": result.controller_interventions,
                "waiting_time_saved_vs_fixed_seconds": round(waiting_saved, 3),
                "waiting_time_saved_vs_fixed_pct": round(
                    _percent_saved(waiting_saved, baseline.total_waiting_time_seconds),
                    3,
                ),
                "throughput_gain_vs_fixed": throughput_gain,
                "emergency_delay_saved_vs_fixed_seconds": round(emergency_saved, 3),
                "bus_passenger_delay_saved_vs_fixed_seconds": (
                    round(bus_saved, 3) if bus_saved is not None else None
                ),
                "truck_delay_saved_vs_fixed_seconds": round(truck_saved, 3),
                "interpretation": _baseline_interpretation(
                    result=result,
                    baseline=baseline,
                    waiting_saved=waiting_saved,
                    throughput_gain=throughput_gain,
                ),
            }
        )
    return rows


def baseline_comparison_to_csv(rows: list[dict[str, Any]], path: Path) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASELINE_COMPARISON_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_baseline_comparison_report(rows: list[dict[str, Any]], path: Path) -> None:
    ensure_parent_dir(path)
    if not rows:
        path.write_text(
            "# Baseline comparison\n\nNo controller results were provided.\n", encoding="utf-8"
        )
        return

    scenario_id = str(rows[0]["scenario_id"])
    best_row = max(rows, key=lambda row: float(row["waiting_time_saved_vs_fixed_seconds"]))
    lines = [
        f"# Báo cáo baseline: {scenario_id}",
        "",
        "Báo cáo này chỉ so sánh kỹ thuật điều khiển đèn giao thông trong SUMO.",
        "Nó chưa kết luận reward/public-value cuối cùng vì phần đó cần nhóm Kinh tế chốt.",
        "",
        "## Đọc nhanh",
        "",
        f"- Controller có tổng thời gian chờ tốt nhất: `{best_row['controller_id']}`.",
        "- `fixed_time` là mốc so sánh: đèn chạy theo chu kỳ cố định.",
        "- `rule_based` là baseline phi-RL dùng đèn actuated của SUMO, không phải policy học máy.",
        (
            "- Nếu rule-based thua fixed-time ở một scenario, đó vẫn là kết quả hợp lệ "
            "để debug map/flow."
        ),
        "",
        "## Bảng so sánh",
        "",
        (
            "| Controller | Avg wait (s) | Total wait (s) | Saved vs fixed (s) | "
            "Throughput gain | Emergency saved (s) | Custom interventions | Nhận xét |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['controller_id']} | "
            f"{_fmt(row['average_waiting_time_seconds'])} | "
            f"{_fmt(row['total_waiting_time_seconds'])} | "
            f"{_fmt(row['waiting_time_saved_vs_fixed_seconds'])} | "
            f"{row['throughput_gain_vs_fixed']} | "
            f"{_fmt(row['emergency_delay_saved_vs_fixed_seconds'])} | "
            f"{row['controller_interventions']} | "
            f"{row['interpretation']} |"
        )
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            (
                "Baseline này dùng metric mô phỏng từ SUMO. Chưa được dùng như bằng chứng "
                "chính sách cuối cùng nếu chưa có reward/public-value, giả định chi phí, "
                "và scenario được review."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_candidate_options_from_csv(paths: list[Path]) -> list[InvestmentOption]:
    best_by_candidate: dict[str, InvestmentOption] = {}
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                candidate_id = row["candidate_id"]
                cost = float(row["capex_vnd"]) + float(row["annual_maintenance_vnd"])
                value = float(row["net_public_value_vnd"])
                option = InvestmentOption(
                    candidate_id=candidate_id,
                    cost_vnd=cost,
                    value_vnd=value,
                    source_row=row,
                )
                current = best_by_candidate.get(candidate_id)
                if current is None or option.value_vnd > current.value_vnd:
                    best_by_candidate[candidate_id] = option
    return list(best_by_candidate.values())


def selected_options_to_csv(
    selected: list[InvestmentOption],
    *,
    budget_vnd: float,
    algorithm: str,
    path: Path,
) -> None:
    ensure_parent_dir(path)
    fieldnames = [
        "algorithm",
        "budget_vnd",
        "candidate_id",
        "cost_vnd",
        "value_vnd",
        "scenario_id",
        "controller_id",
        "intersection_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for option in selected:
            writer.writerow(
                {
                    "algorithm": algorithm,
                    "budget_vnd": budget_vnd,
                    "candidate_id": option.candidate_id,
                    "cost_vnd": round(option.cost_vnd, 3),
                    "value_vnd": round(option.value_vnd, 3),
                    "scenario_id": option.source_row.get("scenario_id", ""),
                    "controller_id": option.source_row.get("controller_id", ""),
                    "intersection_id": option.source_row.get("intersection_id", ""),
                }
            )


def write_markdown_report(
    *,
    result: SimulationResult,
    scores: list[CandidateScore],
    path: Path,
) -> None:
    ensure_parent_dir(path)
    top_scores = sorted(scores, key=lambda score: score.net_public_value_vnd, reverse=True)[:5]
    lines = [
        f"# Simulation report: {result.scenario_id}",
        "",
        f"- Controller: `{result.controller_id}`",
        f"- Engine: `{result.engine_id}`",
        f"- Total vehicles: {result.total_vehicles}",
        f"- Throughput: {result.throughput}",
        f"- Average waiting time: {result.average_waiting_time_seconds:.2f} seconds",
        f"- Emergency delay: {result.emergency_delay_seconds:.2f} seconds",
        f"- Truck delay: {result.truck_delay_seconds:.2f} seconds",
        "",
        "## Top investment candidates",
        "",
        "| Candidate | Intersection | Net public value | B/C ratio | Caveat |",
        "|---|---|---:|---:|---|",
    ]
    for score in top_scores:
        lines.append(
            "| "
            f"{score.candidate_id} | {score.intersection_id} | "
            f"{score.net_public_value_vnd:.0f} | {score.benefit_cost_ratio:.3f} | "
            f"{score.caveat} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def metrics_summary(result: SimulationResult) -> dict[str, Any]:
    """Return the compact metrics object consumed by the future React UI."""

    return {
        "scenario_id": result.scenario_id,
        "controller_id": result.controller_id,
        "engine_id": result.engine_id,
        "seed": result.seed,
        "total_vehicles": result.total_vehicles,
        "throughput": result.throughput,
        "average_waiting_time_seconds": result.average_waiting_time_seconds,
        "max_queue_vehicles": result.max_queue_vehicles,
        "emergency_delay_seconds": result.emergency_delay_seconds,
        "bus_passenger_delay_seconds": result.bus_passenger_delay_seconds,
        "truck_delay_seconds": result.truck_delay_seconds,
        "reroute_count": result.reroute_count,
        "failed_route_count": result.failed_route_count,
        "controller_interventions": result.controller_interventions,
    }


def _percent_saved(saved: float, baseline_value: float) -> float:
    if baseline_value == 0:
        return 0.0
    return saved / baseline_value * 100.0


def _baseline_interpretation(
    *,
    result: SimulationResult,
    baseline: SimulationResult,
    waiting_saved: float,
    throughput_gain: int,
) -> str:
    if result.controller_id == baseline.controller_id:
        return "Mốc so sánh"
    if waiting_saved > 0 and throughput_gain >= 0:
        return "Tốt hơn fixed-time trên metric chính"
    if waiting_saved > 0:
        return "Giảm chờ nhưng cần xem throughput"
    if throughput_gain > 0:
        return "Tăng throughput nhưng chưa giảm chờ"
    return "Chưa tốt hơn fixed-time trong scenario này"


def _fmt(value: object) -> str:
    return f"{float(str(value)):.2f}"
