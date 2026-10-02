from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "runs"
STREAMS = ("yolo", "rl", "finance_optimizer")
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def prepare_run_dir(run_id: str, stream: str, root: Path) -> Path:
    if (
        not isinstance(run_id, str)
        or RUN_ID_PATTERN.fullmatch(run_id) is None
        or run_id.endswith(".")
        or run_id.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(
            "run_id must be a portable filename (1-128 ASCII letters/digits/dot/dash/underscore, "
            "starting with a letter or digit; no trailing dot or reserved device name)"
        )
    if stream not in STREAMS:
        raise ValueError(f"unsupported run stream: {stream!r}; expected one of {STREAMS}")
    root = root.resolve()
    stream_dir = root / stream
    if not stream_dir.resolve().is_relative_to(root):
        raise ValueError(f"run stream directory escapes artifact root: {stream_dir}")
    stream_dir.mkdir(parents=True, exist_ok=True)
    run_dir = stream_dir / run_id
    # One writer owns this ID. Existing/partial folders are never interpreted as resumable runs.
    try:
        run_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"run ID already exists: {run_dir}; refusing to overwrite or resume; use a new ID"
        ) from exc
    for subdir in ("logs", "artifacts", "reports", "configs"):
        (run_dir / subdir).mkdir()

    created_at = datetime.now(UTC).isoformat()
    run_config: dict[str, object] = {
        "run_id": run_id,
        "stream": stream,
        "created_at": created_at,
        "artifact_kind": "management_scaffold",
        "code_commit": "",
        "dataset_id": "",
        "config_source": "",
        "notes": "Fill this before training or evaluation.",
    }
    metrics_placeholder: dict[str, object] = {
        "run_id": run_id,
        "stream": stream,
        "status": "not_started",
        "metrics": {},
        "notes": "Replace after the run finishes.",
    }

    write_json(run_dir / "run_config.json", run_config)
    write_json(run_dir / "metrics.placeholder.json", metrics_placeholder)
    with (run_dir / "README.md").open("x", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    f"# {run_id}",
                    "",
                    f"- Stream: `{stream}`",
                    "- Management scaffold only; "
                    "not an experiment manifest or completed result.",
                    "- Put logs in `logs/`.",
                    "- Put model files, predictions, traces, or other outputs in `artifacts/`.",
                    "- Put human-readable exports in `reports/`.",
                    "- After the run, push this folder to Google Drive "
                    "and update the registry sheet.",
                    "",
                ]
            )
        )
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a local training-run artifact folder.")
    parser.add_argument("--run-id", required=True, help="Stable run id, e.g. RUN-YOLO-V0-001.")
    parser.add_argument("--stream", required=True, choices=STREAMS)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ARTIFACT_ROOT),
        help="Local artifact root. Defaults to artifacts/runs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_dir = prepare_run_dir(args.run_id, args.stream, Path(args.root))
    except (OSError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Prepared run folder: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
