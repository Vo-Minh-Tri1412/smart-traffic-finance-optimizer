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


def candidate_scores_to_csv(scores: list[CandidateScore], path: Path) -> None:
    ensure_parent_dir(path)
    fieldnames = list(scores[0].to_dict()) if scores else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in scores:
            writer.writerow(score.to_dict())


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
        "truck_delay_seconds": result.truck_delay_seconds,
        "failed_route_count": result.failed_route_count,
    }
