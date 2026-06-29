from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import string
import sys
from collections.abc import Iterable
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_NAME = "AI Quantum HVTC — Team Workspace"
DATA_HUB_RELATIVE = Path("02_CS_Workspace") / "00_Data_Management"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "drive_paths.example.json"

STREAM_TO_RUN_SUBDIR = {
    "yolo": Path("03_Training_Runs") / "yolo",
    "rl": Path("03_Training_Runs") / "rl",
    "finance_optimizer": Path("03_Training_Runs") / "finance_optimizer",
}
STREAM_TO_MODEL_SUBDIR = {
    "yolo": Path("04_Model_Artifacts") / "yolo",
    "rl_policy": Path("04_Model_Artifacts") / "rl_policy",
    "investment_optimizer": Path("04_Model_Artifacts") / "investment_optimizer",
}


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


def candidate_data_hub_roots() -> list[Path]:
    candidates: list[Path] = []
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:/")
        candidates.extend(
            [
                drive / "My Drive" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
                drive / "MyDrive" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
                drive / "Drive của tôi" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
                drive / "Shared drives" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
            ]
        )

    home = Path.home()
    candidates.extend(
        [
            home / "Google Drive" / "My Drive" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
            home / "Google Drive" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
            home / "My Drive" / WORKSPACE_NAME / DATA_HUB_RELATIVE,
        ]
    )
    return list(dict.fromkeys(candidates))


def load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_data_hub_root(value: str | None, config: dict[str, object]) -> Path:
    if value:
        root = Path(value).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Data hub root not found: {root}")
        return root

    configured = config.get("local_drive_desktop_data_hub")
    if isinstance(configured, str) and configured and not configured.startswith("<"):
        root = Path(configured).expanduser().resolve()
        if root.exists():
            return root

    for candidate in candidate_data_hub_roots():
        if candidate.exists():
            return candidate.resolve()

    checked = "\n".join(str(path) for path in candidate_data_hub_roots()[:10])
    raise FileNotFoundError(
        "Could not find Google Drive Desktop Data Hub folder.\n"
        "Pass --drive-root explicitly or set local_drive_desktop_data_hub in a local config.\n"
        f"Checked examples:\n{checked}"
    )


def iter_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return
    yield from (path for path in source.rglob("*") if path.is_file())


def copy_to_drive(source: Path, target: Path, *, apply: bool) -> int:
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    copied = 0
    for src_file in iter_files(source):
        relative = src_file.name if source.is_file() else str(src_file.relative_to(source))
        tgt_file = target / relative
        status = "same" if files_equal(src_file, tgt_file) else "planned"
        if status == "planned" and apply:
            tgt_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, tgt_file)
            status = "copied"
            copied += 1
        print(f"[{status.upper()}] {src_file} -> {tgt_file}")
    if not apply:
        print("[DRY-RUN] Add --apply to copy files.")
    return copied


def run_status(root: Path) -> None:
    print(f"[OK] Data Hub root: {root}")
    for rel_path in (
        "00_Registry",
        "01_Raw_Data",
        "02_Processed_Data",
        "03_Training_Runs",
        "04_Model_Artifacts",
        "05_Reports_For_Team",
    ):
        path = root / rel_path
        print(f"[{'OK' if path.exists() else 'MISS'}] {rel_path}: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy local data/model/output artifacts to Google Drive Desktop Data Hub."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to drive config JSON.")
    parser.add_argument("--drive-root", default=None, help="Explicit local Data Hub folder.")
    parser.add_argument(
        "--apply", action="store_true", help="Actually copy files; default is dry-run."
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Check Data Hub discovery and expected folders.")

    push_run = subparsers.add_parser("push-run", help="Push a local training run folder.")
    push_run.add_argument("--stream", required=True, choices=tuple(STREAM_TO_RUN_SUBDIR))
    push_run.add_argument("--run-id", required=True)
    push_run.add_argument("--source", required=True)

    push_model = subparsers.add_parser("push-model", help="Push selected model artifacts.")
    push_model.add_argument("--stream", required=True, choices=tuple(STREAM_TO_MODEL_SUBDIR))
    push_model.add_argument("--model-id", required=True)
    push_model.add_argument("--source", required=True)

    push_report = subparsers.add_parser("push-report", help="Push a report folder or file.")
    push_report.add_argument("--name", required=True)
    push_report.add_argument("--source", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(Path(args.config))

    try:
        root = resolve_data_hub_root(args.drive_root, config)
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.command == "status":
        run_status(root)
        return 0

    if args.command == "push-run":
        target = root / STREAM_TO_RUN_SUBDIR[args.stream] / args.run_id
        copy_to_drive(Path(args.source), target, apply=args.apply)
        return 0

    if args.command == "push-model":
        target = root / STREAM_TO_MODEL_SUBDIR[args.stream] / args.model_id
        copy_to_drive(Path(args.source), target, apply=args.apply)
        return 0

    if args.command == "push-report":
        target = root / "05_Reports_For_Team" / args.name
        copy_to_drive(Path(args.source), target, apply=args.apply)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
