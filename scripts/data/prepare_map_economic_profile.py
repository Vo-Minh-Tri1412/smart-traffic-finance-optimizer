"""Materialize a versioned map-specific economic profile and coverage audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.map_economics import (  # noqa: E402
    coverage_payload,
    materialize_map_economic_profile,
    save_map_economic_profile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="SUMO project descriptor")
    parser.add_argument(
        "--assumptions", type=Path, required=True, help="Reviewed/assumption economic inputs"
    )
    parser.add_argument("--output", type=Path, required=True, help="Profile JSON output")
    parser.add_argument(
        "--coverage-output", type=Path, help="Optional standalone coverage-audit JSON"
    )
    parser.add_argument(
        "--fail-on-production-gate",
        action="store_true",
        help="Return status 2 after writing artifacts when the production gate fails",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profile = materialize_map_economic_profile(
        project_path=args.project,
        assumptions_path=args.assumptions,
    )
    save_map_economic_profile(profile, args.output)
    coverage = coverage_payload(profile)
    if args.coverage_output is not None:
        args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
        args.coverage_output.write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    report = profile.coverage
    if args.fail_on_production_gate and report is not None and not report.production_gate_passed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
