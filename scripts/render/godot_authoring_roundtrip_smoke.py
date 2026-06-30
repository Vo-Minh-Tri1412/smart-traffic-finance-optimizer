from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.render.godot_authoring_export import DEFAULT_SCENE  # noqa: E402
from scripts.render.godot_synthetic_cv_smoke import find_godot_executable  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full Godot-authoring roundtrip: Godot scene -> district spec -> SUMO -> "
            "vehicle trace -> Godot SUMO-geometry replay summary."
        )
    )
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--scenario", default="normal_weekday")
    parser.add_argument("--controller", default="fixed_time")
    parser.add_argument("--max-frames", type=int, default=60)
    return parser


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _print_and_check(label: str, completed: subprocess.CompletedProcess[str]) -> bool:
    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] {label} failed with exit code {completed.returncode}")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root).resolve()
    godot_exe = find_godot_executable(args.godot_exe)
    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1

    output_root.mkdir(parents=True, exist_ok=True)
    spec_path = output_root / "district_spec.generated.json"
    result_path = output_root / "sumo_result.json"
    trace_path = output_root / "trace.jsonl"
    sumo_work_dir = output_root / "sumo_work"
    replay_root = output_root / "godot_replay"
    roundtrip_summary_path = output_root / "roundtrip_summary.json"

    export_cmd = [
        sys.executable,
        "scripts/render/godot_authoring_export.py",
        "--scene",
        args.scene,
        "--out",
        str(spec_path),
        "--godot-exe",
        str(godot_exe),
    ]
    if not _print_and_check("Godot authoring export", _run(export_cmd)):
        return 1

    simulate_cmd = [
        sys.executable,
        "-m",
        "ai_quantum_hvtc",
        "simulate",
        "run",
        "--engine",
        "sumo",
        "--spec",
        str(spec_path),
        "--scenario",
        args.scenario,
        "--controller",
        args.controller,
        "--out",
        str(result_path),
        "--trace-out",
        str(trace_path),
        "--sumo-work-dir",
        str(sumo_work_dir),
    ]
    if not _print_and_check("SUMO simulation", _run(simulate_cmd)):
        return 1

    net_path = sumo_work_dir / args.scenario / args.controller / "district.net.xml"
    replay_cmd = [
        sys.executable,
        "scripts/render/godot_sumo_trace_replay_smoke.py",
        "--trace",
        str(trace_path),
        "--spec",
        str(spec_path),
        "--net",
        str(net_path),
        "--output-root",
        str(replay_root),
        "--max-frames",
        str(args.max_frames),
        "--godot-exe",
        str(godot_exe),
    ]
    if not _print_and_check("Godot SUMO geometry replay", _run(replay_cmd)):
        return 1

    replay_summary = json.loads((replay_root / "replay_summary.json").read_text(encoding="utf-8"))
    sim_result = json.loads(result_path.read_text(encoding="utf-8"))
    summary = {
        "success": True,
        "spec": spec_path.as_posix(),
        "net": net_path.as_posix(),
        "trace": trace_path.as_posix(),
        "replay_summary": (replay_root / "replay_summary.json").as_posix(),
        "total_vehicles": sim_result.get("total_vehicles", 0),
        "throughput": sim_result.get("throughput", 0),
        "lane_count": replay_summary.get("lane_count", 0),
        "spawned_vehicle_count": replay_summary.get("spawned_vehicle_count", 0),
        "off_lane_vehicle_count": replay_summary.get("off_lane_vehicle_count", 0),
        "max_off_lane_distance_m": replay_summary.get("max_off_lane_distance_m", 0.0),
    }
    roundtrip_summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] Godot authoring roundtrip valid: {roundtrip_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
