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

GODOT_SMOKE_SCRIPT = "res://scripts/smoke/test_lod_regression.gd"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Godot headless LOD regression smoke test.")
    parser.add_argument("--godot-project", default=str(DEFAULT_GODOT_PROJECT))
    parser.add_argument("--godot-exe", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    godot_project = Path(args.godot_project).resolve()
    godot_exe = find_godot_executable(args.godot_exe)

    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1
    if not godot_project.is_dir():
        print(f"[FAIL] Godot project not found: {godot_project}")
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="aiq_godot_lod_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            overlay_path = temp_dir_path / "fixture_overlay.json"

            # Write minimal overlay fixture
            overlay_data = {
                "zones": [
                    {
                        "id": "zone_1",
                        "type": "residential",
                        "geometry": {
                            "type": "polygon",
                            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                            "coordinate_system": "sumo",
                        },
                    },
                    {
                        "id": "zone_2",
                        "type": "residential",
                        "geometry": {
                            "type": "polygon",
                            "coordinates": [
                                [[200, 200], [210, 200], [210, 210], [200, 210], [200, 200]]
                            ],
                            "coordinate_system": "sumo",
                        },
                    },
                ]
            }
            with overlay_path.open("w", encoding="utf-8") as f:
                json.dump(overlay_data, f)

            command = [
                str(godot_exe),
                "--headless",
                "--path",
                str(godot_project),
                "--script",
                GODOT_SMOKE_SCRIPT,
                "--",
                "--overlay",
                overlay_path.as_posix(),
            ]

            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] Godot LOD regression smoke failed with exit code {completed.returncode}")
        return completed.returncode

    if "[LOD_TEST] SUCCESS" not in completed.stdout:
        print("[FAIL] Godot LOD regression smoke did not report SUCCESS")
        return 1

    print("[OK] Godot LOD regression smoke valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
