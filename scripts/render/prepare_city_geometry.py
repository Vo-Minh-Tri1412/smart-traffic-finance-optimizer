from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.simulation.maps import (  # noqa: E402
    load_semantic_overlay,
    load_sumo_net_index,
    load_sumo_project,
)
from ai_quantum_hvtc.simulation.maps.source import sha256_file  # noqa: E402

DEFAULT_PROJECT = PROJECT_ROOT / "simulation_projects" / "map_intake" / "district7.project.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write geometry metadata from a retained SUMO project without creating demand."
    )
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = args.output.expanduser().resolve()
    try:
        project = load_sumo_project(args.project.expanduser())
        net_path = project.source.net_path.resolve(strict=True)
        overlay_path = project.overlay_path.resolve(strict=True)
        net_index = load_sumo_net_index(net_path)
        overlay = load_semantic_overlay(overlay_path, net_index)

        bounds = {
            "min_x": net_index.bounds_min[0],
            "min_y": net_index.bounds_min[1],
            "max_x": net_index.bounds_max[0],
            "max_y": net_index.bounds_max[1],
        }
        if not all(math.isfinite(value) for value in bounds.values()):
            raise ValueError("SUMO network bounds must be finite")
        if bounds["max_x"] <= bounds["min_x"] or bounds["max_y"] <= bounds["min_y"]:
            raise ValueError("SUMO network bounds must have positive width and height")
        if net_index.edge_count == 0 or net_index.lane_count == 0:
            raise ValueError("SUMO network must contain at least one edge and lane")

        geometry = {
            "schema_version": "geometry_manifest.v1",
            "geometry_source": "sumo_net_xml",
            "coordinate_system": "sumo_xy_meters",
            "net_xml": Path(os.path.relpath(net_path, output_path.parent)).as_posix(),
            "bounds": bounds,
            "local_origin": {"x": bounds["min_x"], "y": bounds["min_y"]},
            "project_id": project.project_id,
            "project_version": project.version,
            "source_id": project.source.source_id,
            "source_net_sha256": sha256_file(net_path),
            "semantic_overlay_sha256": sha256_file(overlay_path),
            "edge_count": net_index.edge_count,
            "lane_count": net_index.lane_count,
            "junction_count": net_index.junction_count,
            "traffic_light_count": net_index.traffic_light_count,
            "overlay_zone_count": len(overlay.zones),
            "overlay_candidate_count": len(overlay.candidates),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf-8") as handle:
            json.dump(geometry, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    except (OSError, ValueError, KeyError) as exc:
        print(f"[FAIL] Could not prepare city geometry: {exc}")
        return 1

    print(f"[OK] Geometry manifest written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
