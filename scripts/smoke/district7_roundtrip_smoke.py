from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.reports import result_to_json, result_vehicle_trace_to_jsonl  # noqa: E402
from ai_quantum_hvtc.simulation.engines.sumo import (  # noqa: E402
    SumoRuntimeConfig,
    prepare_existing_sumo_net_run,
    run_existing_sumo_net,
)
from ai_quantum_hvtc.simulation.engines.sumo.parser import (  # noqa: E402
    parse_existing_sumo_net_result,
)
from ai_quantum_hvtc.simulation.maps import (  # noqa: E402
    generate_sumo_demand,
    load_semantic_overlay,
    load_sumo_net_index,
    load_sumo_project,
)
from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError  # noqa: E402
from scripts.render.godot_sumo_trace_replay_smoke import main as godot_replay_main  # noqa: E402
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable  # noqa: E402

DEFAULT_PROJECT = PROJECT_ROOT / "simulation_projects" / "map_intake" / "district7.project.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the District 7 OSM/SUMO-first smoke pipeline: DVC data check, overlay demand, "
            "existing SUMO net run, trace export, optional Godot replay, and QA report."
        )
    )
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--controller", default="fixed_time")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--no-dvc-pull", action="store_true")
    parser.add_argument("--require-godot", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        project = load_sumo_project(args.project)
        if not project.source.net_path.is_file() and not args.no_dvc_pull:
            _dvc_pull(project.prepared_dvc_path)
        net_index = load_sumo_net_index(project.source.net_path)
        overlay = load_semantic_overlay(project.overlay_path, net_index)
        demand_config = _load_json(project.demand_config_path)
        scenario_id = args.scenario or str(demand_config.get("default_scenario", "normal_weekday"))
        seed = int(demand_config.get("seed", 42))
        horizon_seconds = int(demand_config.get("horizon_seconds", 900))
        step_length_seconds = float(demand_config.get("step_length_seconds", 1.0))

        demand_dir = output_root / "demand"
        demand = generate_sumo_demand(
            overlay=overlay,
            net_index=net_index,
            net_path=project.source.net_path,
            scenario_id=scenario_id,
            work_dir=demand_dir,
            seed=seed,
        )

        sumo_work_dir = output_root / "sumo_work"
        run_paths = prepare_existing_sumo_net_run(
            net=project.source.net_path,
            routes=demand.routes,
            work_dir=sumo_work_dir,
            scenario_id=scenario_id,
            controller_id=args.controller,
            seed=seed,
            horizon_seconds=horizon_seconds,
            step_length_seconds=step_length_seconds,
        )
        run_existing_sumo_net(run_paths, SumoRuntimeConfig())
        result = parse_existing_sumo_net_result(
            paths=run_paths,
            district_id=project.project_id,
            scenario_id=scenario_id,
            controller_id=args.controller,
            seed=seed,
        )
        result_path = output_root / "result.json"
        trace_path = output_root / "trace.jsonl"
        result_to_json(result, result_path)
        result_vehicle_trace_to_jsonl(result, trace_path)
    except (OSError, SumoMapSourceError, RuntimeError, ValueError) as exc:
        print(f"[FAIL] District 7 roundtrip failed: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - preserves clear CLI failure for SUMO errors.
        print(f"[FAIL] District 7 roundtrip failed: {exc}")
        return 1

    godot_status = _run_godot_replay(
        trace_path=trace_path,
        net_path=project.source.net_path,
        overlay_path=project.overlay_path,
        output_root=output_root / "godot_replay",
        max_frames=args.max_frames,
        godot_exe_arg=args.godot_exe,
        require_godot=args.require_godot,
    )
    if godot_status["status"] == "failed":
        _write_qa(
            output_root=output_root,
            project_id=project.project_id,
            scenario_id=scenario_id,
            net_index=net_index,
            demand=demand,
            result=_compact_result(result.to_dict()),
            godot_status=godot_status,
        )
        return 1

    qa_path = _write_qa(
        output_root=output_root,
        project_id=project.project_id,
        scenario_id=scenario_id,
        net_index=net_index,
        demand=demand,
        result=_compact_result(result.to_dict()),
        godot_status=godot_status,
    )
    print(f"[OK] District 7 SUMO/Godot roundtrip QA written: {qa_path}")
    return 0


def _run_godot_replay(
    *,
    trace_path: Path,
    net_path: Path,
    overlay_path: Path,
    output_root: Path,
    max_frames: int,
    godot_exe_arg: str | None,
    require_godot: bool,
) -> dict[str, Any]:
    godot_exe = find_godot_executable(godot_exe_arg)
    if godot_exe is None:
        if require_godot:
            return {"status": "failed", "reason": "Godot executable not found"}
        return {"status": "skipped", "reason": "Godot executable not found"}
    code = godot_replay_main(
        [
            "--trace",
            str(trace_path),
            "--net",
            str(net_path),
            "--overlay",
            str(overlay_path),
            "--spec",
            str(PROJECT_ROOT / "tests" / "fixtures" / "specs" / "toy_public_district_v1.json"),
            "--output-root",
            str(output_root),
            "--max-frames",
            str(max_frames),
            "--godot-exe",
            str(godot_exe),
        ]
    )
    summary_path = output_root / "replay_summary.json"
    summary = _load_json(summary_path) if summary_path.is_file() else {}
    if code != 0:
        return {"status": "failed", "exit_code": code, "summary": summary}
    return {"status": "ok", "summary": summary}


def _dvc_pull(path: Path | None) -> None:
    if path is None:
        return
    completed = subprocess.run(
        ["dvc", "pull", str(path)],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"dvc pull failed for {path}:\n{completed.stdout}")


def _write_qa(
    *,
    output_root: Path,
    project_id: str,
    scenario_id: str,
    net_index: Any,
    demand: Any,
    result: dict[str, Any],
    godot_status: dict[str, Any],
) -> Path:
    payload = {
        "project_id": project_id,
        "scenario_id": scenario_id,
        "net": {
            "edge_count": net_index.edge_count,
            "lane_count": net_index.lane_count,
            "junction_count": net_index.junction_count,
            "traffic_light_count": net_index.traffic_light_count,
            "bounds_min": list(net_index.bounds_min),
            "bounds_max": list(net_index.bounds_max),
        },
        "demand": {
            "attempted_trips": demand.attempted_trips,
            "routed_trips": demand.routed_trips,
            "failed_trips": demand.failed_trips,
            "routes": str(demand.routes),
        },
        "simulation": result,
        "godot_replay": godot_status,
        "caveat": "District 7 geometry is real OSM/SUMO; demand overlay is synthetic v1.",
    }
    qa_json = output_root / "district7_roundtrip_qa.json"
    qa_md = output_root / "district7_roundtrip_qa.md"
    qa_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa_md.write_text(_qa_markdown(payload), encoding="utf-8")
    return qa_json


def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
    intersections = result.get("intersections", {})
    return {
        key: value
        for key, value in result.items()
        if key not in {"intersections", "vehicle_trace_frames"}
    } | {"intersection_metric_count": len(intersections) if isinstance(intersections, dict) else 0}


def _qa_markdown(payload: dict[str, Any]) -> str:
    godot = payload["godot_replay"]
    replay_summary = godot.get("summary", {}) if isinstance(godot, dict) else {}
    zone_overlay = replay_summary.get("zone_overlay", {})
    zone_visual_count = (
        zone_overlay.get("spawned_zone_count", "n/a") if isinstance(zone_overlay, dict) else "n/a"
    )
    return "\n".join(
        [
            f"# District 7 roundtrip QA — {payload['scenario_id']}",
            "",
            f"- Project: `{payload['project_id']}`",
            f"- SUMO edges: {payload['net']['edge_count']}",
            f"- SUMO lanes: {payload['net']['lane_count']}",
            f"- SUMO traffic lights: {payload['net']['traffic_light_count']}",
            f"- Attempted trips: {payload['demand']['attempted_trips']}",
            f"- Routed trips: {payload['demand']['routed_trips']}",
            f"- Total vehicles observed: {payload['simulation']['total_vehicles']}",
            f"- Throughput: {payload['simulation']['throughput']}",
            f"- Godot replay status: `{godot.get('status', 'unknown')}`",
            f"- Off-lane vehicles: {replay_summary.get('off_lane_vehicle_count', 'n/a')}",
            f"- Zone visuals: {zone_visual_count}",
            "",
            "## Caveat",
            "",
            str(payload["caveat"]),
            "",
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
