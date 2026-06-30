from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from ai_quantum_hvtc.policy import optimize_exact, optimize_greedy, qubo_matrix
from ai_quantum_hvtc.public_finance import score_candidates
from ai_quantum_hvtc.reports import (
    baseline_comparison_rows,
    baseline_comparison_to_csv,
    candidate_scores_to_csv,
    load_candidate_options_from_csv,
    result_to_json,
    result_to_trace_jsonl,
    selected_options_to_csv,
    write_baseline_comparison_report,
    write_markdown_report,
)
from ai_quantum_hvtc.simulation.engines import ReferenceGraphEngine, SimulationEngine, SumoAdapter
from ai_quantum_hvtc.simulation.engines.sumo import SumoRuntimeError
from ai_quantum_hvtc.simulation.specs import load_district_spec


def _engine(engine_id: str, *, sumo_work_dir: Path | None = None) -> SimulationEngine:
    if engine_id == "reference":
        return ReferenceGraphEngine()
    if engine_id == "sumo":
        return SumoAdapter(work_dir=sumo_work_dir)
    raise ValueError(f"unknown engine: {engine_id}")


def _sumo_work_dir(base_dir: str | None, *, scenario_id: str, controller_id: str) -> Path | None:
    if not base_dir:
        return None
    return Path(base_dir) / scenario_id / controller_id


def _parse_controllers(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe_controllers(controllers: list[str]) -> list[str]:
    deduped: list[str] = []
    for controller_id in controllers:
        if controller_id not in deduped:
            deduped.append(controller_id)
    return deduped


def _expanded_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(pattern))
    return paths


def _cmd_validate(args: argparse.Namespace) -> int:
    spec = load_district_spec(args.spec)
    print(
        json.dumps(
            {
                "status": "ok",
                "district_id": spec.metadata.district_id,
                "zones": len(spec.zones),
                "intersections": len(spec.intersections),
                "roads": len(spec.roads),
                "flows": len(spec.flows),
                "scenarios": len(spec.scenarios),
                "investment_candidates": len(spec.investment_candidates),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    spec = load_district_spec(args.spec)
    try:
        result = _engine(
            args.engine,
            sumo_work_dir=_sumo_work_dir(
                args.sumo_work_dir,
                scenario_id=args.scenario,
                controller_id=args.controller,
            ),
        ).run(
            spec=spec,
            scenario_id=args.scenario,
            controller_id=args.controller,
            seed=args.seed,
        )
    except SumoRuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1
    result_to_json(result, Path(args.out))
    if args.trace_out:
        result_to_trace_jsonl(result, spec, Path(args.trace_out))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    spec = load_district_spec(args.spec)
    controllers = _dedupe_controllers(_parse_controllers(args.controllers))
    if "fixed_time" not in controllers:
        controllers = ["fixed_time", *controllers]

    try:
        baseline = _engine(
            args.engine,
            sumo_work_dir=_sumo_work_dir(
                args.sumo_work_dir,
                scenario_id=args.scenario,
                controller_id="fixed_time",
            ),
        ).run(
            spec=spec,
            scenario_id=args.scenario,
            controller_id="fixed_time",
            seed=args.seed,
        )
    except SumoRuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1
    all_scores = []
    latest_result = baseline
    for controller_id in controllers:
        try:
            result = (
                baseline
                if controller_id == "fixed_time"
                else _engine(
                    args.engine,
                    sumo_work_dir=_sumo_work_dir(
                        args.sumo_work_dir,
                        scenario_id=args.scenario,
                        controller_id=controller_id,
                    ),
                ).run(
                    spec=spec,
                    scenario_id=args.scenario,
                    controller_id=controller_id,
                    seed=args.seed,
                )
            )
        except SumoRuntimeError as exc:
            print(f"[FAIL] {exc}")
            return 1
        latest_result = result
        all_scores.extend(score_candidates(spec, baseline, result))

    candidate_scores_to_csv(all_scores, Path(args.out))
    if args.report:
        write_markdown_report(result=latest_result, scores=all_scores, path=Path(args.report))
    print(f"wrote {len(all_scores)} candidate score rows to {args.out}")
    return 0


def _cmd_compare_baselines(args: argparse.Namespace) -> int:
    spec = load_district_spec(args.spec)
    controllers = _dedupe_controllers(_parse_controllers(args.controllers))
    if "fixed_time" not in controllers:
        controllers = ["fixed_time", *controllers]

    results = []
    for controller_id in controllers:
        try:
            result = _engine(
                args.engine,
                sumo_work_dir=_sumo_work_dir(
                    args.sumo_work_dir,
                    scenario_id=args.scenario,
                    controller_id=controller_id,
                ),
            ).run(
                spec=spec,
                scenario_id=args.scenario,
                controller_id=controller_id,
                seed=args.seed,
            )
        except SumoRuntimeError as exc:
            print(f"[FAIL] {exc}")
            return 1
        results.append(result)

    rows = baseline_comparison_rows(results)
    baseline_comparison_to_csv(rows, Path(args.out))
    if args.report:
        write_baseline_comparison_report(rows, Path(args.report))
    print(f"wrote {len(rows)} baseline comparison row(s) to {args.out}")
    return 0


def _cmd_optimize_investment(args: argparse.Namespace) -> int:
    options = load_candidate_options_from_csv(_expanded_paths(args.metrics))
    selected = (
        optimize_exact(options, args.budget)
        if args.algorithm == "exact"
        else optimize_greedy(options, args.budget)
    )
    selected_options_to_csv(
        selected,
        budget_vnd=args.budget,
        algorithm=args.algorithm,
        path=Path(args.out),
    )
    if args.qubo_out:
        matrix = qubo_matrix(options, budget_vnd=args.budget)
        Path(args.qubo_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.qubo_out).write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"selected {len(selected)} candidate(s) with {args.algorithm} optimizer")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ai_quantum_hvtc simulate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a district spec.")
    validate_parser.add_argument("--spec", required=True)
    validate_parser.set_defaults(func=_cmd_validate)

    run_parser = subparsers.add_parser("run", help="Run one scenario/controller.")
    run_parser.add_argument("--spec", required=True)
    run_parser.add_argument("--scenario", required=True)
    run_parser.add_argument("--controller", required=True)
    run_parser.add_argument(
        "--engine",
        default="sumo",
        choices=["sumo", "reference"],
        help="Simulation backend. Use sumo for project runs; reference is validation-only.",
    )
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--trace-out", default=None)
    run_parser.add_argument(
        "--sumo-work-dir",
        default=None,
        help="Keep SUMO artifacts under this directory when --engine sumo is used.",
    )
    run_parser.set_defaults(func=_cmd_run)

    compare_parser = subparsers.add_parser(
        "compare", help="Compare controllers and score candidates."
    )
    compare_parser.add_argument("--spec", required=True)
    compare_parser.add_argument("--scenario", required=True)
    compare_parser.add_argument("--controllers", required=True)
    compare_parser.add_argument(
        "--engine",
        default="sumo",
        choices=["sumo", "reference"],
        help="Simulation backend. Use sumo for project runs; reference is validation-only.",
    )
    compare_parser.add_argument("--seed", type=int, default=42)
    compare_parser.add_argument("--out", required=True)
    compare_parser.add_argument("--report", default=None)
    compare_parser.add_argument(
        "--sumo-work-dir",
        default=None,
        help="Keep SUMO artifacts under this directory when --engine sumo is used.",
    )
    compare_parser.set_defaults(func=_cmd_compare)

    baseline_parser = subparsers.add_parser(
        "compare-baselines",
        help="Compare fixed-time/rule-based technical baseline metrics.",
    )
    baseline_parser.add_argument("--spec", required=True)
    baseline_parser.add_argument("--scenario", required=True)
    baseline_parser.add_argument("--controllers", default="fixed_time,rule_based")
    baseline_parser.add_argument(
        "--engine",
        default="sumo",
        choices=["sumo", "reference"],
        help="Simulation backend. Use sumo for project runs; reference is validation-only.",
    )
    baseline_parser.add_argument("--seed", type=int, default=42)
    baseline_parser.add_argument("--out", required=True)
    baseline_parser.add_argument("--report", default=None)
    baseline_parser.add_argument(
        "--sumo-work-dir",
        default=None,
        help="Keep SUMO artifacts under this directory when --engine sumo is used.",
    )
    baseline_parser.set_defaults(func=_cmd_compare_baselines)

    optimize_parser = subparsers.add_parser(
        "optimize-investment",
        help="Select investment candidates under a budget.",
    )
    optimize_parser.add_argument("--metrics", nargs="+", required=True)
    optimize_parser.add_argument("--budget", type=float, required=True)
    optimize_parser.add_argument("--algorithm", default="exact", choices=["exact", "greedy"])
    optimize_parser.add_argument("--out", required=True)
    optimize_parser.add_argument("--qubo-out", default=None)
    optimize_parser.set_defaults(func=_cmd_optimize_investment)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
