from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.simulation.specs import load_district_spec  # noqa: E402
from scripts.render.godot_synthetic_cv_smoke import (  # noqa: E402
    DEFAULT_GODOT_PROJECT,
    find_godot_executable,
)

DEFAULT_SCENE = "res://scenes/authoring/DistrictAuthoringMap.tscn"
GODOT_EXPORT_SCRIPT = "res://scripts/authoring/export_district_spec.gd"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a Godot-authored district scene to backend district_spec JSON."
    )
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--out", required=True)
    parser.add_argument("--godot-project", default=str(DEFAULT_GODOT_PROJECT))
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--district-id", default="godot_authoring_district_v1")
    parser.add_argument("--district-name", default="Godot Authored District V1")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--horizon-seconds", type=int, default=3600)
    parser.add_argument("--time-step-seconds", type=int, default=1)
    return parser


def run_godot_export(
    *,
    godot_exe: Path,
    godot_project: Path,
    scene: str,
    out: Path,
    district_id: str,
    district_name: str,
    version: str,
    horizon_seconds: int,
    time_step_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(godot_exe),
        "--headless",
        "--path",
        str(godot_project),
        "--script",
        GODOT_EXPORT_SCRIPT,
        "--",
        "--scene",
        scene,
        "--out",
        out.as_posix(),
        "--district-id",
        district_id,
        "--district-name",
        district_name,
        "--version",
        version,
        "--horizon-seconds",
        str(horizon_seconds),
        "--time-step-seconds",
        str(time_step_seconds),
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _summary(spec_path: Path) -> dict[str, object]:
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    return {
        "district_id": data["metadata"]["id"],
        "intersections": len(data.get("intersections", [])),
        "roads": len(data.get("roads", [])),
        "zones": len(data.get("zones", [])),
        "flows": len(data.get("flows", [])),
        "investment_candidates": len(data.get("investment_candidates", [])),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    godot_project = Path(args.godot_project).resolve()
    godot_exe = find_godot_executable(args.godot_exe)
    out = Path(args.out).resolve()

    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1
    if not godot_project.is_dir():
        print(f"[FAIL] Godot project not found: {godot_project}")
        return 1

    completed = run_godot_export(
        godot_exe=godot_exe,
        godot_project=godot_project,
        scene=args.scene,
        out=out,
        district_id=args.district_id,
        district_name=args.district_name,
        version=args.version,
        horizon_seconds=args.horizon_seconds,
        time_step_seconds=args.time_step_seconds,
    )
    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] Godot authoring export failed with exit code {completed.returncode}")
        return completed.returncode
    if not out.is_file():
        print(f"[FAIL] Godot authoring export did not write {out}")
        return 1

    try:
        load_district_spec(out)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Exported district spec failed backend validation: {exc}")
        return 1

    print(f"[OK] Godot authoring export valid: {json.dumps(_summary(out), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
