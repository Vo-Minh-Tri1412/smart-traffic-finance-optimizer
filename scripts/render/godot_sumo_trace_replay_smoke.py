from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.render.godot_synthetic_cv_smoke import (  # noqa: E402
    DEFAULT_GODOT_PROJECT,
    find_godot_executable,
)

DEFAULT_SPEC = PROJECT_ROOT / "tests" / "fixtures" / "specs" / "toy_public_district_v1.json"
GODOT_REPLAY_SCRIPT = "res://scripts/replay/run_trace_replay_smoke.gd"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Godot headless smoke replay from a SUMO vehicle-level trace JSONL. "
            "If --trace is omitted, the wrapper generates a fixture SUMO trace first."
        )
    )
    parser.add_argument("--trace", default=None, help="Existing vehicle-level trace JSONL.")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="District spec JSON.")
    parser.add_argument("--net", default=None, help="Optional SUMO district.net.xml for geometry.")
    parser.add_argument(
        "--overlay",
        default=None,
        help="Optional semantic overlay JSON for zone visuals.",
    )
    parser.add_argument("--output-root", required=True, help="Directory for replay_summary.json.")
    parser.add_argument("--godot-project", default=str(DEFAULT_GODOT_PROJECT))
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--max-frames", type=int, default=60)
    parser.add_argument("--scenario", default="normal_weekday")
    parser.add_argument("--controller", default="fixed_time")
    return parser


def generate_fixture_trace(
    *,
    spec: Path,
    scenario: str,
    controller: str,
    work_dir: Path,
) -> tuple[Path, Path | None]:
    result_path = work_dir / "result.json"
    trace_path = work_dir / "trace.jsonl"
    sumo_work_dir = work_dir / "sumo_work"
    command = [
        sys.executable,
        "-m",
        "ai_quantum_hvtc",
        "simulate",
        "run",
        "--engine",
        "sumo",
        "--spec",
        str(spec),
        "--scenario",
        scenario,
        "--controller",
        controller,
        "--out",
        str(result_path),
        "--trace-out",
        str(trace_path),
        "--sumo-work-dir",
        str(sumo_work_dir),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Could not generate fixture SUMO trace.\n"
            f"command: {' '.join(command)}\n"
            f"output:\n{completed.stdout}"
        )
    net_path = sumo_work_dir / scenario / controller / "district.net.xml"
    return trace_path, net_path if net_path.is_file() else None


def run_godot_replay_smoke(
    *,
    godot_exe: Path,
    godot_project: Path,
    trace: Path,
    spec: Path,
    net: Path | None,
    overlay: Path | None,
    output_root: Path,
    max_frames: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(godot_exe),
        "--headless",
        "--path",
        str(godot_project),
        "--script",
        GODOT_REPLAY_SCRIPT,
        "--",
        "--trace",
        trace.as_posix(),
        "--spec",
        spec.as_posix(),
        "--output-root",
        output_root.as_posix(),
        "--max-frames",
        str(max_frames),
    ]
    if net is not None:
        command.extend(["--net", net.as_posix()])
    if overlay is not None:
        command.extend(["--overlay", overlay.as_posix()])
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _read_summary(output_root: Path) -> dict[str, object]:
    summary_path = output_root / "replay_summary.json"
    if not summary_path.is_file():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _summary_int(summary: dict[str, object], key: str) -> int:
    value = summary.get(key, 0)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


def _summary_float(summary: dict[str, object], key: str) -> float:
    value = summary.get(key, 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = Path(args.spec).resolve()
    output_root = Path(args.output_root).resolve()
    godot_project = Path(args.godot_project).resolve()
    godot_exe = find_godot_executable(args.godot_exe)

    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1
    if not godot_project.is_dir():
        print(f"[FAIL] Godot project not found: {godot_project}")
        return 1
    if not spec.is_file():
        print(f"[FAIL] District spec not found: {spec}")
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="aiq_godot_replay_") as temp_dir:
            if args.trace:
                trace = Path(args.trace).resolve()
                net = Path(args.net).resolve() if args.net else None
            else:
                trace, generated_net = generate_fixture_trace(
                    spec=spec,
                    scenario=args.scenario,
                    controller=args.controller,
                    work_dir=Path(temp_dir),
                )
                net = Path(args.net).resolve() if args.net else generated_net
            overlay = Path(args.overlay).resolve() if args.overlay else None
            if not trace.is_file():
                print(f"[FAIL] Trace file not found: {trace}")
                return 1
            if net is not None and not net.is_file():
                print(f"[FAIL] SUMO net file not found: {net}")
                return 1
            if overlay is not None and not overlay.is_file():
                print(f"[FAIL] Semantic overlay file not found: {overlay}")
                return 1
            completed = run_godot_replay_smoke(
                godot_exe=godot_exe,
                godot_project=godot_project,
                trace=trace,
                spec=spec,
                net=net,
                overlay=overlay,
                output_root=output_root,
                max_frames=args.max_frames,
            )
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] Godot replay smoke failed with exit code {completed.returncode}")
        return completed.returncode

    summary = _read_summary(output_root)
    if not summary:
        print(f"[FAIL] replay_summary.json was not written under {output_root}")
        return 1
    if _summary_int(summary, "loaded_frames") <= 0:
        print("[FAIL] replay_summary.json reports zero loaded frames")
        return 1
    if _summary_int(summary, "spawned_vehicle_count") <= 0:
        print("[FAIL] replay_summary.json reports zero spawned vehicles")
        return 1
    if _summary_int(summary, "parse_error_count") != 0:
        print("[FAIL] replay_summary.json reports trace parse errors")
        return 1
    if net is not None and _summary_int(summary, "lane_count") <= 0:
        print("[FAIL] replay_summary.json reports zero SUMO lanes")
        return 1
    if _summary_int(summary, "off_lane_vehicle_count") != 0:
        print("[FAIL] replay_summary.json reports vehicles outside SUMO lane geometry")
        return 1
    if (
        summary.get("trace_schema_version") == "vehicle_trace.v2"
        and _summary_int(summary, "vehicle_visual_fit_asset_count") > 0
        and _summary_float(summary, "vehicle_visual_fit_max_error_world_units") > 0.001
    ):
        print("[FAIL] replay_summary.json reports visual assets that do not match physical proxies")
        return 1
    zone_overlay = summary.get("zone_overlay", {})
    if args.overlay and isinstance(zone_overlay, dict):
        if _summary_int(zone_overlay, "spawned_zone_count") <= 0:
            print("[FAIL] replay_summary.json reports zero spawned zone visuals")
            return 1
        if _summary_int(zone_overlay, "overlay_parse_error_count") != 0:
            print("[FAIL] replay_summary.json reports semantic overlay parse errors")
            return 1

    print(f"[OK] Godot SUMO trace replay smoke valid: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
