from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "runs"
STREAMS = ("yolo", "rl", "finance_optimizer")


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_run_dir(run_id: str, stream: str, root: Path) -> Path:
    run_dir = root / stream / run_id
    for subdir in ("logs", "artifacts", "reports", "configs"):
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(UTC).isoformat()
    run_config: dict[str, object] = {
        "run_id": run_id,
        "stream": stream,
        "created_at": created_at,
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
    (run_dir / "README.md").write_text(
        "\n".join(
            [
                f"# {run_id}",
                "",
                f"- Stream: `{stream}`",
                "- Put logs in `logs/`.",
                "- Put model files, predictions, traces, or other outputs in `artifacts/`.",
                "- Put human-readable exports in `reports/`.",
                "- After the run, push this folder to Google Drive and update the registry sheet.",
                "",
            ]
        ),
        encoding="utf-8",
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
    run_dir = prepare_run_dir(args.run_id, args.stream, Path(args.root))
    print(f"[OK] Prepared run folder: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
