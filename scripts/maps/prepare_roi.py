from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.simulation.maps.roi import (  # noqa: E402
    RoiPrepError,
    load_roi_config,
    prepare_roi,
    validate_roi_config_shape,
    write_roi_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a generic map ROI: OSM tag zoning, road review, and Godot/SUMO sync artifacts."
        )
    )
    parser.add_argument("--config", required=True, help="Path to ROI config JSON.")
    parser.add_argument("--output-root", required=True, help="Artifact output directory.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config shape only; do not require source files or write ROI artifacts.",
    )
    parser.add_argument(
        "--copy-source-net",
        action="store_true",
        help=(
            "Copy source SUMO net into output as a prepared-net placeholder. "
            "Use only for smoke/debug; real ROI clipping should be a later netconvert step."
        ),
    )
    parser.add_argument(
        "--clip-sumo-net",
        action="store_true",
        help=(
            "Clip the source SUMO net to the ROI polygon with netconvert "
            "--keep-edges.in-geo-boundary and write a prepared ROI net."
        ),
    )
    args = parser.parse_args()
    if args.copy_source_net and args.clip_sumo_net:
        parser.error("--copy-source-net and --clip-sumo-net are mutually exclusive")

    config = load_roi_config(args.config)
    output_root = Path(args.output_root)
    if args.dry_run:
        validate_roi_config_shape(config, require_sources=False)
        output_root.mkdir(parents=True, exist_ok=True)
        summary = {
            "status": "dry_run_ok",
            "roi_id": config.roi_id,
            "name": config.name,
            "polygon": [[point.lon, point.lat] for point in config.polygon.points],
            "osm_path": str(config.osm_path),
            "source_net_path": str(config.source_net_path or ""),
            "note": (
                "Dry-run validates polygon config shape only; "
                "it does not read map source files."
            ),
        }
        (output_root / "dry_run_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] ROI config dry-run: {config.roi_id}")
        return 0

    result = prepare_roi(
        config,
        copy_source_net=args.copy_source_net,
        clip_sumo_net=args.clip_sumo_net,
        output_root=output_root,
    )
    paths = write_roi_artifacts(result, output_root)
    print(f"[OK] ROI prepared: {config.roi_id}")
    print(f"  semantic_overlay={paths.semantic_overlay}")
    print(f"  road_review={paths.road_review}")
    print(f"  godot_preview={paths.godot_preview}")
    print(f"  qa_json={paths.qa_json}")
    if paths.prepared_net:
        print(f"  prepared_net={paths.prepared_net}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoiPrepError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
