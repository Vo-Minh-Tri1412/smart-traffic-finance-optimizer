from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "cv_yolo"


def expected_paths(dataset_root: Path) -> list[Path]:
    return [
        dataset_root / "images" / "train",
        dataset_root / "images" / "val",
        dataset_root / "labels" / "train",
        dataset_root / "labels" / "val",
    ]


def init_yolo_template(dataset_id: str, output_root: Path) -> Path:
    dataset_root = output_root / dataset_id
    for path in expected_paths(dataset_root):
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").write_text("", encoding="utf-8")

    (dataset_root / "data.yaml").write_text(
        "\n".join(
            [
                "path: .",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: motorbike",
                "  1: car",
                "  2: bus",
                "  3: truck",
                "  4: ambulance",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest = {
        "dataset_id": dataset_id,
        "stream": "cv_yolo",
        "format": "ultralytics_yolo",
        "status": "template_only",
        "notes": "Replace template folders with real images/labels outside Git.",
    }
    (dataset_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset_root


def validate_yolo_dataset(dataset_root: Path) -> list[str]:
    problems: list[str] = []
    for path in expected_paths(dataset_root):
        if not path.exists():
            problems.append(f"Missing folder: {path}")
    if not (dataset_root / "data.yaml").exists():
        problems.append(f"Missing file: {dataset_root / 'data.yaml'}")
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize or validate a YOLO dataset folder layout."
    )
    parser.add_argument("--dataset-id", required=True, help="Dataset id, e.g. CV-YOLO-RAW-V0.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Root for processed YOLO datasets. Defaults to data/processed/cv_yolo.",
    )
    parser.add_argument("--init-template", action="store_true", help="Create empty YOLO layout.")
    parser.add_argument("--validate", action="store_true", help="Validate expected YOLO layout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root)
    dataset_root = output_root / args.dataset_id

    if args.init_template:
        dataset_root = init_yolo_template(args.dataset_id, output_root)
        print(f"[OK] YOLO template prepared: {dataset_root}")

    if args.validate:
        problems = validate_yolo_dataset(dataset_root)
        if problems:
            for problem in problems:
                print(f"[FAIL] {problem}")
            return 1
        print(f"[OK] YOLO dataset layout valid: {dataset_root}")

    if not args.init_template and not args.validate:
        build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
