"""Run the deterministic SUMO-trace geometry camera without a renderer or GPU."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.sensors import (
    GeometryObservationAdapter,
    VisibilityRecord,
    load_camera_calibrations,
    visibility_from_trace_frames,
    write_visibility_trace,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, type=Path, help="vehicle_trace.v2 JSONL")
    parser.add_argument(
        "--camera-calibration",
        required=True,
        type=Path,
        help="camera_calibration.v1 JSON",
    )
    parser.add_argument("--output", required=True, type=Path, help="visibility_trace.v1 JSONL")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional positive frame cap for a quick ROI smoke; default runs the complete trace.",
    )
    parser.add_argument(
        "--lane-to-approach",
        type=Path,
        help="Optional JSON object mapping SUMO lane IDs to fixed observation approaches.",
    )
    parser.add_argument(
        "--observation-output",
        type=Path,
        help="Optional sensor_observation.v1 JSONL written only from visible records.",
    )
    parser.add_argument("--summary-out", type=Path, help="Optional JSON summary artifact")
    return parser.parse_args()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: each JSONL row must be an object")
        frames.append(payload)
    if not frames:
        raise ValueError(f"{path}: trace is empty")
    return frames


def _load_lane_mapping(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: lane mapping must be a JSON object")
    return {str(lane_id): str(approach) for lane_id, approach in payload.items()}


def _write_observations(
    *,
    records: Iterable[VisibilityRecord],
    lane_to_approach: dict[str, str],
    output: Path,
) -> int:
    by_camera_time: dict[tuple[str, float], list] = defaultdict(list)
    for record in records:
        by_camera_time[(record.camera_id, record.time_seconds)].append(record)
    adapters: dict[str, GeometryObservationAdapter] = {}
    rows: list[str] = []
    for (camera_id, timestamp), grouped_records in sorted(by_camera_time.items()):
        adapter = adapters.setdefault(
            camera_id,
            GeometryObservationAdapter(
                sensor_id=camera_id,
                lane_to_approach=lane_to_approach,
            ),
        )
        rows.append(
            json.dumps(
                adapter.observe(timestamp_seconds=timestamp, records=grouped_records).to_dict(),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(rows)


def main() -> int:
    args = _parse_args()
    started = time.perf_counter()
    frames = _load_jsonl(args.trace)
    if args.max_frames < 0:
        raise ValueError("--max-frames must be non-negative")
    if args.max_frames:
        frames = frames[: args.max_frames]
    cameras = load_camera_calibrations(args.camera_calibration)
    records = visibility_from_trace_frames(frames=frames, cameras=cameras)
    write_visibility_trace(records, args.output)
    lane_to_approach = _load_lane_mapping(args.lane_to_approach)
    observation_count = 0
    if args.observation_output:
        observation_count = _write_observations(
            records=records,
            lane_to_approach=lane_to_approach,
            output=args.observation_output,
        )
    state_counts = Counter(record.visibility_state for record in records)
    summary = {
        "status": "ok",
        "visibility_schema_version": "visibility_trace.v1",
        "input_trace": str(args.trace),
        "camera_calibration": str(args.camera_calibration),
        "output": str(args.output),
        "frame_count": len(frames),
        "camera_count": len(cameras),
        "visibility_record_count": len(records),
        "state_counts": dict(sorted(state_counts.items())),
        "observation_count": observation_count,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "caveat": (
            "Deterministic vehicle-geometry visibility. It is not RGB, YOLO, or detector-noise "
            "simulation."
        ),
    }
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
