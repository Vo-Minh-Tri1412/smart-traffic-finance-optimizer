from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.public_finance.map_qubo import (  # noqa: E402
    MapQuboConfig,
    MapQuboValidationError,
    RiskMode,
    build_map_aware_qubo,
    build_qubo_run_manifest,
    load_map_economic_profile,
    solve_map_qubo_exact,
)

CONFIG_SCHEMA_VERSION = "map_aware_qubo_config.v1"


def _parse_flat_yaml(path: Path) -> dict[str, Any]:
    """Parse the deliberately flat, scalar-only QUBO config without a YAML dependency."""

    result: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MapQuboValidationError(f"cannot read config {path}: {exc}") from exc
    for line_number, original in enumerate(lines, start=1):
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if original[:1].isspace() or ":" not in stripped:
            raise MapQuboValidationError(
                f"{path}:{line_number}: config supports top-level key: scalar rows only"
            )
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.split(" #", 1)[0].strip()
        if not key or not raw_value:
            raise MapQuboValidationError(f"{path}:{line_number}: key and scalar value are required")
        if key in result:
            raise MapQuboValidationError(f"{path}:{line_number}: duplicate key {key!r}")
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        if isinstance(value, (dict, list)):
            raise MapQuboValidationError(
                f"{path}:{line_number}: nested config values are not supported"
            )
        result[key] = value
    if result.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise MapQuboValidationError(f"{path}: schema_version must be {CONFIG_SCHEMA_VERSION!r}")
    return result


def _setting(
    cli_value: object | None,
    config: dict[str, Any],
    key: str,
    *,
    required: bool = False,
) -> object | None:
    value = cli_value if cli_value is not None else config.get(key)
    if required and value is None:
        raise MapQuboValidationError(f"missing required setting: {key}")
    return value


def _setting_or_default(
    cli_value: object | None,
    config: dict[str, Any],
    key: str,
    default: object,
) -> object:
    value = _setting(cli_value, config, key)
    return default if value is None else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build and exactly verify a small map-aware investment QUBO from "
            "map_economic_profile.v1."
        )
    )
    parser.add_argument("--config", type=Path, help="Optional flat map_aware_qubo_config.v1 YAML")
    parser.add_argument("--profile", type=Path, help="map_economic_profile.v1 JSON")
    parser.add_argument("--output", type=Path, help="Output map_aware_qubo_run.v1 JSON")
    parser.add_argument("--run-id")
    parser.add_argument("--budget-vnd", type=float)
    parser.add_argument("--benefit-present-value-factor", type=float)
    parser.add_argument("--operating-cost-present-value-factor", type=float)
    parser.add_argument("--capital-cost-weight", type=float)
    parser.add_argument(
        "--risk-mode",
        choices=("estimate", "conservative", "optimistic"),
    )
    parser.add_argument("--budget-unit-vnd", type=float)
    parser.add_argument("--objective-scale-vnd", type=float)
    parser.add_argument("--budget-penalty", type=float)
    parser.add_argument("--penalty-margin", type=float)
    parser.add_argument("--max-exact-candidates", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config_data = _parse_flat_yaml(args.config) if args.config else {}
        profile_path = Path(
            cast(
                str | Path,
                _setting(args.profile, config_data, "profile", required=True),
            )
        )
        output_path = Path(
            cast(
                str | Path,
                _setting(args.output, config_data, "output", required=True),
            )
        )
        run_id = str(_setting(args.run_id, config_data, "run_id", required=True))
        budget_vnd = float(
            cast(float, _setting(args.budget_vnd, config_data, "budget_vnd", required=True))
        )
        benefit_factor = float(
            cast(
                float,
                _setting(
                    args.benefit_present_value_factor,
                    config_data,
                    "benefit_present_value_factor",
                    required=True,
                ),
            )
        )
        operating_factor = float(
            cast(
                float,
                _setting(
                    args.operating_cost_present_value_factor,
                    config_data,
                    "operating_cost_present_value_factor",
                    required=True,
                ),
            )
        )
        risk_mode = cast(
            RiskMode,
            str(_setting_or_default(args.risk_mode, config_data, "risk_mode", "conservative")),
        )
        if risk_mode not in ("estimate", "conservative", "optimistic"):
            raise MapQuboValidationError(f"unsupported risk_mode: {risk_mode!r}")
        raw_penalty = _setting(args.budget_penalty, config_data, "budget_penalty")
        qubo_config = MapQuboConfig(
            budget_vnd=budget_vnd,
            benefit_present_value_factor=benefit_factor,
            operating_cost_present_value_factor=operating_factor,
            capital_cost_weight=float(
                cast(
                    Any,
                    _setting_or_default(
                        args.capital_cost_weight,
                        config_data,
                        "capital_cost_weight",
                        1.0,
                    ),
                )
            ),
            risk_mode=risk_mode,
            budget_unit_vnd=float(
                cast(
                    Any,
                    _setting_or_default(
                        args.budget_unit_vnd,
                        config_data,
                        "budget_unit_vnd",
                        1_000_000.0,
                    ),
                )
            ),
            objective_scale_vnd=float(
                cast(
                    Any,
                    _setting_or_default(
                        args.objective_scale_vnd,
                        config_data,
                        "objective_scale_vnd",
                        1_000_000.0,
                    ),
                )
            ),
            budget_penalty=None if raw_penalty is None else float(cast(float, raw_penalty)),
            penalty_margin=float(
                cast(
                    Any,
                    _setting_or_default(
                        args.penalty_margin,
                        config_data,
                        "penalty_margin",
                        1.05,
                    ),
                )
            ),
            max_exact_candidates=int(
                cast(
                    Any,
                    _setting_or_default(
                        args.max_exact_candidates,
                        config_data,
                        "max_exact_candidates",
                        22,
                    ),
                )
            ),
        )
        profile = load_map_economic_profile(profile_path)
        build = build_map_aware_qubo(profile, qubo_config)
        solution = solve_map_qubo_exact(build)
        manifest = build_qubo_run_manifest(build, solution, run_id=run_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    except (MapQuboValidationError, OSError, TypeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    selected = ", ".join(solution.selected_candidate_ids) or "<empty portfolio>"
    print(f"[OK] QUBO manifest: {output_path}")
    print(f"[OK] Selected: {selected}")
    print(
        "[OK] Capital budget: "
        f"{solution.portfolio.capital_cost_vnd:.3f}/{qubo_config.budget_vnd:.3f} VND"
    )
    print(f"[CAVEAT] {manifest['claim_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
