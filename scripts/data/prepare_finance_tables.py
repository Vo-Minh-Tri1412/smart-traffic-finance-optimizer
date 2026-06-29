from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "finance_tables"


def write_template(path: Path, headers: list[str], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerow(row)


def prepare_finance_templates(dataset_id: str, output_root: Path) -> Path:
    target = output_root / dataset_id
    target.mkdir(parents=True, exist_ok=True)
    write_template(
        target / "public_value_assumptions.csv",
        [
            "assumption_id",
            "metric",
            "value",
            "unit",
            "source",
            "confidence",
            "caveat",
        ],
        [
            "A-001",
            "value_of_time",
            "",
            "VND/hour",
            "",
            "placeholder",
            "Nhóm Kinh tế cần điền nguồn hoặc ghi rõ là giả định.",
        ],
    )
    write_template(
        target / "investment_candidates.csv",
        [
            "candidate_id",
            "intersection_id",
            "estimated_cost_vnd",
            "expected_benefit_metric",
            "caveat",
        ],
        ["C-001", "", "", "", "Điền sau khi có scenario/metric."],
    )
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create finance-table templates for Drive handoff."
    )
    parser.add_argument("--dataset-id", default="FINANCE-ASSUMPTIONS-V0")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = prepare_finance_templates(args.dataset_id, Path(args.output_root))
    print(f"[OK] Finance templates prepared: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
