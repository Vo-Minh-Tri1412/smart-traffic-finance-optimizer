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

from ai_quantum_hvtc.sensors import (  # noqa: E402
    init_synthetic_yolo_dataset,
    validate_synthetic_yolo_dataset,
)
from scripts.render.godot_sumo_trace_replay_smoke import (  # noqa: E402
    DEFAULT_SPEC,
    generate_fixture_trace,
)
from scripts.render.godot_synthetic_cv_smoke import (  # noqa: E402
    DEFAULT_GODOT_PROJECT,
    find_godot_executable,
)

GODOT_SENSOR_SCRIPT = "res://scripts/sensors/run_sensor_dataset_smoke.gd"
DEFAULT_CAMERA_CATALOG = "res://resources/catalogs/CameraRigCatalog.tres"
DEFAULT_LABEL_MAPPING = "res://resources/catalogs/LabelMappingCatalog.tres"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Godot 3D replay sensor smoke export. This creates RGB frames, "
            "object-id mask smoke images, YOLO labels, and sensor frame manifests."
        )
    )
    parser.add_argument("--dataset-id", default="SYNTH-CV-GODOT-SENSOR-SMOKE")
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--output-root", default="data/processed/cv_yolo")
    parser.add_argument("--trace", default=None)
    parser.add_argument("--net", default=None)
    parser.add_argument("--overlay", default=None)
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--scenario", default="normal_weekday")
    parser.add_argument("--controller", default="fixed_time")
    parser.add_argument("--godot-project", default=str(DEFAULT_GODOT_PROJECT))
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--camera-catalog", default=DEFAULT_CAMERA_CATALOG)
    parser.add_argument("--label-mapping", default=DEFAULT_LABEL_MAPPING)
    parser.add_argument("--max-frames", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    return parser


def _resolve_dataset_root(args: argparse.Namespace) -> Path:
    if args.dataset_root:
        return Path(args.dataset_root).resolve()
    return (Path(args.output_root) / args.dataset_id).resolve()


def _run_godot_sensor_smoke(
    *,
    godot_exe: Path,
    godot_project: Path,
    dataset_root: Path,
    dataset_id: str,
    trace: Path,
    net: Path | None,
    overlay: Path | None,
    camera_catalog: str,
    label_mapping: str,
    max_frames: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(godot_exe),
        "--headless",
        "--path",
        str(godot_project),
        "--script",
        GODOT_SENSOR_SCRIPT,
        "--",
        "--trace",
        trace.as_posix(),
        "--dataset-root",
        dataset_root.as_posix(),
        "--dataset-id",
        dataset_id,
        "--camera-catalog",
        camera_catalog,
        "--label-mapping",
        label_mapping,
        "--max-frames",
        str(max_frames),
    ]
    if net is not None:
        command.extend(["--net", net.as_posix()])
    if overlay is not None:
        command.extend(["--overlay", overlay.as_posix()])
    return subprocess.run(  # noqa: S603
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _update_dataset_manifest(dataset_root: Path, *, dataset_id: str, frame_count: int) -> None:
    manifest_path = dataset_root / "dataset_manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_id"] = dataset_id
    manifest["status"] = "sensor_smoke_frames_generated"
    manifest["frame_count"] = frame_count
    manifest["class_names"] = _class_names_from_data_yaml(dataset_root / "data.yaml")
    manifest["source_type"] = "godot_3d_replay_camera"
    manifest["notes"] = (
        "Sensor smoke dataset generated from Godot replay cameras. "
        "Labels are synthetic ground truth and must not be used as inference inputs."
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _class_names_from_data_yaml(path: Path) -> list[str]:
    if not path.is_file():
        return []
    names: list[str] = []
    in_names = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.strip() == "names:":
            in_names = True
            continue
        if not in_names:
            continue
        if line.startswith("  ") and ":" in line:
            names.append(line.split(":", maxsplit=1)[1].strip())
        elif line.strip():
            break
    return names


def _count_manifest_frames(dataset_root: Path) -> int:
    frame_manifest = dataset_root / "sensor_frame_manifest.jsonl"
    if not frame_manifest.is_file():
        return 0
    return sum(1 for line in frame_manifest.read_text(encoding="utf-8").splitlines() if line)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_root = _resolve_dataset_root(args)
    godot_project = Path(args.godot_project).resolve()
    godot_exe = find_godot_executable(args.godot_exe)
    spec = Path(args.spec).resolve()

    if godot_exe is None:
        print("[FAIL] Godot executable not found. Pass --godot-exe or set GODOT_STANDARD_EXE.")
        return 1
    if not godot_project.is_dir():
        print(f"[FAIL] Godot project not found: {godot_project}")
        return 1

    init_dataset_id = dataset_root.name if args.dataset_root else args.dataset_id
    init_synthetic_yolo_dataset(
        dataset_id=init_dataset_id,
        output_root=dataset_root.parent,
        force=args.force,
        render_id="GODOT-SENSOR-SMOKE-001",
        source_run_id="godot-replay-sensor-smoke",
    )

    with tempfile.TemporaryDirectory(prefix="aiq_godot_sensor_") as temp_dir:
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

        completed = _run_godot_sensor_smoke(
            godot_exe=godot_exe,
            godot_project=godot_project,
            dataset_root=dataset_root,
            dataset_id=args.dataset_id,
            trace=trace,
            net=net,
            overlay=overlay,
            camera_catalog=args.camera_catalog,
            label_mapping=args.label_mapping,
            max_frames=args.max_frames,
        )

    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"[FAIL] Godot sensor smoke failed with exit code {completed.returncode}")
        return completed.returncode

    frame_count = _count_manifest_frames(dataset_root)
    if frame_count <= 0:
        print("[FAIL] sensor_frame_manifest.jsonl has no frames")
        return 1
    _update_dataset_manifest(dataset_root, dataset_id=args.dataset_id, frame_count=frame_count)

    result = validate_synthetic_yolo_dataset(dataset_root)
    for warning in result.warnings:
        print(f"[WARN] {warning}")
    if result.errors:
        for error in result.errors:
            print(f"[FAIL] {error}")
        return 1
    if not (dataset_root / "render_manifest.json").is_file():
        print("[FAIL] render_manifest.json missing")
        return 1

    print(f"[OK] Godot sensor dataset smoke valid: {dataset_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
