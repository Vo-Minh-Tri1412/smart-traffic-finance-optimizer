from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.sensors import (  # noqa: E402
    DEFAULT_SYNTHETIC_YOLO_CLASSES,
    init_synthetic_yolo_dataset,
    validate_synthetic_yolo_dataset,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "cv_yolo"


def _class_names(value: str | None) -> tuple[str, ...]:
    if value is None or not value.strip():
        return DEFAULT_SYNTHETIC_YOLO_CLASSES
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Initialize or validate the Unreal synthetic-camera YOLO dataset contract. "
            "This prepares folders/manifests only; generated images and labels stay outside Git."
        )
    )
    parser.add_argument("--dataset-id", help="Dataset id, e.g. SYNTH-CV-UE-V0.")
    parser.add_argument(
        "--dataset-root",
        default=None,
        help="Existing dataset root for validation. Defaults to output-root/dataset-id.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Root for processed YOLO datasets. Defaults to data/processed/cv_yolo.",
    )
    parser.add_argument("--init-template", action="store_true", help="Create template layout.")
    parser.add_argument("--validate", action="store_true", help="Validate layout and YOLO labels.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow reusing an existing dataset folder when initializing a template.",
    )
    parser.add_argument(
        "--class-names",
        default=None,
        help="Comma-separated YOLO class names. Defaults to the project synthetic vehicle classes.",
    )
    parser.add_argument("--render-id", default=None, help="Optional render id for manifest.")
    parser.add_argument("--source-run-id", default="", help="Optional SUMO/RL source run id.")
    return parser


def _resolve_dataset_root(args: argparse.Namespace) -> Path:
    if args.dataset_root:
        return Path(args.dataset_root)
    if not args.dataset_id:
        raise ValueError("--dataset-id is required when --dataset-root is not provided")
    return Path(args.output_root) / args.dataset_id


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.init_template:
        if not args.dataset_id:
            print("[FAIL] --dataset-id is required with --init-template")
            return 1
        paths = init_synthetic_yolo_dataset(
            dataset_id=args.dataset_id,
            output_root=Path(args.output_root),
            class_names=_class_names(args.class_names),
            force=args.force,
            render_id=args.render_id,
            source_run_id=args.source_run_id,
        )
        print(f"[OK] Synthetic CV dataset template prepared: {paths.root}")

    if args.validate:
        try:
            dataset_root = _resolve_dataset_root(args)
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        result = validate_synthetic_yolo_dataset(dataset_root)
        for warning in result.warnings:
            print(f"[WARN] {warning}")
        if result.errors:
            for error in result.errors:
                print(f"[FAIL] {error}")
            return 1
        print(f"[OK] Synthetic CV dataset contract valid: {result.dataset_root}")

    if not args.init_template and not args.validate:
        build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
