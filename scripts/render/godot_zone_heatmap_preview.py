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

from scripts.render.godot_synthetic_cv_smoke import (  # noqa: E402
    DEFAULT_GODOT_PROJECT,
    find_godot_executable,
)

GODOT_CAPTURE_SCRIPT = "res://scripts/replay/capture_render_preview.gd"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "render" / "outputs" / "godot_zone_heatmap"
DEFAULT_OSM_PATH = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "01_raw_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.osm"
)
DEFAULT_NET_PATH = (
    PROJECT_ROOT
    / "simulation_projects"
    / "map_intake"
    / "02_prepared_sources"
    / "district7_osm_seed_20260702"
    / "district7_seed.net.xml"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a production-path Godot semantic heatmap preview: OSM/SUMO map "
            "-> buildable semantic overlay -> Godot Main.tscn heatmap layer screenshot."
        )
    )
    parser.add_argument("--osm", default=str(DEFAULT_OSM_PATH))
    parser.add_argument("--net", default=str(DEFAULT_NET_PATH))
    parser.add_argument("--overlay", default=None, help="Use an existing semantic overlay JSON.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--prefix", default="full_map")
    parser.add_argument("--godot-project", default=str(DEFAULT_GODOT_PROJECT))
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--camera", choices=["topdown", "angled"], default="topdown")
    parser.add_argument("--camera-size", type=float, default=0.0)
    parser.add_argument("--show-roads", action="store_true")
    parser.add_argument("--road-buffer-m", type=float, default=7.0)
    parser.add_argument("--road-neighborhood-buffer-m", type=float, default=120.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    osm_path = Path(args.osm).resolve()
    net_path = Path(args.net).resolve()
    godot_project = Path(args.godot_project).resolve()
    godot_exe = find_godot_executable(args.godot_exe)

    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1
    for path, label in [
        (osm_path, "OSM source"),
        (net_path, "SUMO net"),
        (godot_project, "Godot project"),
    ]:
        if not path.exists():
            print(f"[FAIL] {label} not found: {path}")
            return 1

    overlay_path = Path(args.overlay).resolve() if args.overlay else None
    if overlay_path is None:
        overlay_path = _generate_buildable_overlay(
            osm_path=osm_path,
            net_path=net_path,
            output_root=output_root,
            prefix=args.prefix,
            road_buffer_m=args.road_buffer_m,
            road_neighborhood_buffer_m=args.road_neighborhood_buffer_m,
        )
    if not overlay_path.is_file():
        print(f"[FAIL] Semantic overlay not found: {overlay_path}")
        return 1

    image_path = output_root / f"{args.prefix}_godot_zone_heatmap.png"
    completed = _run_godot_capture(
        godot_exe=godot_exe,
        godot_project=godot_project,
        net_path=net_path,
        overlay_path=overlay_path,
        image_path=image_path,
        width=args.width,
        height=args.height,
        camera=args.camera,
        camera_size=args.camera_size,
        show_roads=args.show_roads,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] Godot heatmap preview failed with exit code {completed.returncode}")
        return completed.returncode

    summary_path = image_path.with_suffix(".summary.json")
    if not image_path.is_file() or not summary_path.is_file():
        print(f"[FAIL] Godot preview did not write expected files under {output_root}")
        return 1
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    zone_summary = summary.get("zone_heatmap", summary.get("zone_overlay", {}))
    if _summary_int(zone_summary, "rendered_polygon_count") <= 0:
        print("[FAIL] Godot heatmap rendered zero zone polygons.")
        return 1
    if _summary_int(zone_summary, "overlay_parse_error_count") != 0:
        print("[FAIL] Godot heatmap reported semantic overlay parse errors.")
        return 1

    print(f"[OK] Godot zone heatmap image: {image_path}")
    print(f"[OK] Godot zone heatmap summary: {summary_path}")
    print(f"[OK] Semantic overlay: {overlay_path}")
    return 0


def _generate_buildable_overlay(
    *,
    osm_path: Path,
    net_path: Path,
    output_root: Path,
    prefix: str,
    road_buffer_m: float,
    road_neighborhood_buffer_m: float,
) -> Path:
    command = [
        sys.executable,
        "scripts/maps/render_buildable_zone_heatmap.py",
        "--osm",
        str(osm_path),
        "--net",
        str(net_path),
        "--output-root",
        str(output_root),
        "--prefix",
        prefix,
        "--road-buffer-m",
        str(road_buffer_m),
        "--road-neighborhood-buffer-m",
        str(road_neighborhood_buffer_m),
    ]
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return output_root / f"{prefix}_buildable_semantic_overlay.generated.json"


def _run_godot_capture(
    *,
    godot_exe: Path,
    godot_project: Path,
    net_path: Path,
    overlay_path: Path,
    image_path: Path,
    width: int,
    height: int,
    camera: str,
    camera_size: float,
    show_roads: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(godot_exe),
        "--path",
        str(godot_project),
        "--script",
        GODOT_CAPTURE_SCRIPT,
        "--",
        "--net",
        net_path.as_posix(),
        "--overlay",
        overlay_path.as_posix(),
        "--out",
        image_path.as_posix(),
        "--zone-render-mode",
        "heatmap",
        "--show-roads",
        "true" if show_roads else "false",
        "--show-zones",
        "true",
        "--show-vehicles",
        "false",
        "--show-traffic-lights",
        "false",
        "--camera",
        camera,
        "--width",
        str(width),
        "--height",
        str(height),
    ]
    if camera_size > 0:
        command.extend(["--camera-size", str(camera_size)])
    return subprocess.run(  # noqa: S603
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _summary_int(summary: Any, key: str) -> int:
    if not isinstance(summary, dict):
        return 0
    value = summary.get(key, 0)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
