from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = PROJECT_ROOT / "tests" / "fixtures" / "specs" / "toy_public_district_v1.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "rl_training"


def materialize_spec(spec: Path, output_root: Path, dataset_id: str) -> Path:
    target = output_root / dataset_id
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spec, target / "district_spec.json")
    (target / "README.md").write_text(
        "\n".join(
            [
                f"# {dataset_id}",
                "",
                "This folder is a local processed-data handoff for SUMO/SUMO-RL training.",
                "Generated SUMO network/route/config files should be placed here or in Drive.",
                "Large generated files must not be committed to Git.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize SUMO-RL input spec into data area.")
    parser.add_argument("--dataset-id", default="RL-SUMO-SPEC-V0")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = Path(args.spec)
    if not spec.exists():
        print(f"[FAIL] Spec not found: {spec}")
        return 1
    target = materialize_spec(spec, Path(args.output_root), args.dataset_id)
    print(f"[OK] Materialized SUMO input: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
