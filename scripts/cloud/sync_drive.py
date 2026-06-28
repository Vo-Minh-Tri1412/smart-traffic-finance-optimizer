from __future__ import annotations

import argparse
import hashlib
import shutil
import string
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

DRIVE_WORKSPACE_NAME = "AI Quantum HVTC — Team Workspace"

ECON_TO_CS = Path("03_Shared_Handoffs") / "From_Econ_To_CS"
CS_TO_ECON = Path("03_Shared_Handoffs") / "From_CS_To_Econ"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(source: Path, target: Path) -> bool:
    if not source.exists() or not target.exists():
        return False
    if source.stat().st_size != target.stat().st_size:
        return False
    return sha256_file(source) == sha256_file(target)


def candidate_drive_roots() -> list[Path]:
    candidates: list[Path] = []
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:/")
        candidates.extend(
            [
                drive / "My Drive" / DRIVE_WORKSPACE_NAME,
                drive / "MyDrive" / DRIVE_WORKSPACE_NAME,
                drive / "Drive của tôi" / DRIVE_WORKSPACE_NAME,
                drive / "Shared drives" / DRIVE_WORKSPACE_NAME,
            ]
        )

    home = Path.home()
    candidates.extend(
        [
            home / "Google Drive" / "My Drive" / DRIVE_WORKSPACE_NAME,
            home / "Google Drive" / DRIVE_WORKSPACE_NAME,
            home / "My Drive" / DRIVE_WORKSPACE_NAME,
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def resolve_drive_root(value: str | None) -> Path:
    if value:
        root = Path(value).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Drive root not found: {root}")
        return root

    for candidate in candidate_drive_roots():
        if candidate.exists():
            return candidate.resolve()

    checked = "\n".join(str(path) for path in candidate_drive_roots()[:10])
    raise FileNotFoundError(
        f"Could not find '{DRIVE_WORKSPACE_NAME}' through Google Drive Desktop.\n"
        "Install Google Drive Desktop or pass --drive-root explicitly.\n"
        f"Checked examples:\n{checked}"
    )


def copy_tree_sync(
    source: Path,
    target: Path,
    *,
    apply: bool,
    description: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not source.exists():
        print(f"[SKIP] {description}: source does not exist: {source}")
        return rows

    for src_file in source.rglob("*"):
        if not src_file.is_file():
            continue

        rel_path = src_file.relative_to(source)
        tgt_file = target / rel_path
        status = "same" if tgt_file.exists() and files_equal(src_file, tgt_file) else "planned"

        if status == "planned" and apply:
            tgt_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, tgt_file)
            status = "copied"

        rows.append(
            {
                "action": description,
                "source": str(src_file),
                "target": str(tgt_file),
                "status": status,
            }
        )
        print(f"[{status.upper()}] {rel_path}")

    return rows


def pull_econ(drive_root: Path, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    pairs = [
        (
            drive_root / ECON_TO_CS / "01_Cost_Assumptions",
            DATA_DIR / "external" / "cost_assumptions",
            "pull_cost_assumptions",
        ),
        (
            drive_root / ECON_TO_CS / "02_Traffic_Scenarios",
            DATA_DIR / "external" / "traffic_scenarios",
            "pull_traffic_scenarios",
        ),
    ]
    for source, target, description in pairs:
        actions.extend(copy_tree_sync(source, target, apply=apply, description=description))
    return actions


def push_results(drive_root: Path, apply: bool) -> list[dict[str, str]]:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    source = OUTPUTS_DIR / "simulation_results"
    target = drive_root / CS_TO_ECON / "01_Simulation_Results" / f"Run_{timestamp}"
    return copy_tree_sync(source, target, apply=apply, description="push_simulation_results")


def push_finance_reports(drive_root: Path, apply: bool) -> list[dict[str, str]]:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    source = OUTPUTS_DIR / "public_finance_reports"
    target = drive_root / CS_TO_ECON / "02_Public_Finance_Summary" / f"Run_{timestamp}"
    return copy_tree_sync(source, target, apply=apply, description="push_public_finance_reports")


def push_models(drive_root: Path, apply: bool) -> list[dict[str, str]]:
    target = drive_root / "02_CS_Workspace" / "02_Training_Results"
    return copy_tree_sync(MODELS_DIR, target, apply=apply, description="push_rl_models")


def selected_actions(args: argparse.Namespace) -> Iterable[str]:
    if args.all:
        return ("pull_econ", "push_results", "push_finance_reports", "push_models")

    actions: list[str] = []
    if args.pull_econ:
        actions.append("pull_econ")
    if args.push_results:
        actions.append("push_results")
    if args.push_finance_reports:
        actions.append("push_finance_reports")
    if args.push_models:
        actions.append("push_models")
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync SUMO-RL traffic/public-finance handoffs with Google Drive Desktop."
    )
    parser.add_argument("--drive-root", default=None, help="Explicit local Drive workspace path.")
    parser.add_argument("--status", action="store_true", help="Check Drive workspace discovery.")
    parser.add_argument("--pull-econ", action="store_true", help="Pull Economics inputs for CS.")
    parser.add_argument("--push-results", action="store_true", help="Push simulation outputs.")
    parser.add_argument("--push-finance-reports", action="store_true", help="Push finance reports.")
    parser.add_argument("--push-models", action="store_true", help="Backup RL model artifacts.")
    parser.add_argument("--all", action="store_true", help="Run all sync flows.")
    parser.add_argument(
        "--apply", action="store_true", help="Actually copy files; otherwise dry-run."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        drive_root = resolve_drive_root(args.drive_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.status:
        print(f"[OK] Drive workspace found: {drive_root}")
        return 0

    actions = list(selected_actions(args))
    if not actions:
        parser.print_help()
        return 0

    ran: list[dict[str, str]] = []
    for action in actions:
        if action == "pull_econ":
            ran.extend(pull_econ(drive_root, args.apply))
        elif action == "push_results":
            ran.extend(push_results(drive_root, args.apply))
        elif action == "push_finance_reports":
            ran.extend(push_finance_reports(drive_root, args.apply))
        elif action == "push_models":
            ran.extend(push_models(drive_root, args.apply))

    if not args.apply and ran:
        print("\n[DRY-RUN] Add --apply to copy files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
