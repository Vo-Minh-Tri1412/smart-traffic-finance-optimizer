from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.maps.source import SumoProjectDescriptor, load_sumo_net_index


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"network {label} must be finite")
    return float(value)


def write_render_inputs(
    *,
    directory: Path,
    run: dict[str, Any],
    project: SumoProjectDescriptor,
) -> None:
    """Write renderer input manifests from the frozen run and retained SUMO project.

    This creates input metadata only. It does not launch Unreal or invent traffic-light or
    event traces that the debug executor does not produce.
    """
    experiment_id = run.get("experiment_id")
    run_id = run.get("run_id")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise ValueError("run experiment_id must be a non-empty string")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run run_id must be a non-empty string")

    directory = directory.resolve(strict=True)
    net_xml = project.source.net_path.resolve(strict=True)
    overlay = project.overlay_path.resolve(strict=True)
    trace = directory / "vehicle_trace.jsonl"
    if not trace.is_file():
        raise FileNotFoundError(f"vehicle trace not found: {trace}")

    net_index = load_sumo_net_index(net_xml)
    min_x = _finite(net_index.bounds_min[0], "min_x")
    min_y = _finite(net_index.bounds_min[1], "min_y")
    max_x = _finite(net_index.bounds_max[0], "max_x")
    max_y = _finite(net_index.bounds_max[1], "max_y")
    if max_x < min_x or max_y < min_y:
        raise ValueError("network bounds are inverted")

    geometry_path = directory / "geometry_manifest.json"
    render_path = directory / "render_run_manifest.json"
    if geometry_path.exists() or render_path.exists():
        raise FileExistsError("render input manifest already exists; refusing overwrite")

    geometry = {
        "schema_version": "geometry_manifest.v1",
        "experiment_id": experiment_id,
        "run_id": run_id,
        "geometry_source": "sumo_net_xml",
        "net_xml": str(net_xml),
        "coordinate_system": "sumo_xy_meters",
        "bounds": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        },
        "local_origin": {"x": min_x, "y": min_y},
        "edge_count": net_index.edge_count,
        "lane_count": net_index.lane_count,
        "junction_count": net_index.junction_count,
        "traffic_light_count": net_index.traffic_light_count,
    }
    render_manifest = {
        "schema_version": "render_run_manifest.v1",
        "experiment_id": experiment_id,
        "run_id": run_id,
        "geometry_manifest": geometry_path.name,
        "vehicle_trace": trace.name,
        "traffic_light_trace": "",
        "semantic_overlay": str(overlay),
        "event_trace": "",
        "renderer": "unreal",
        "quality_report": "",
        "render_executed": False,
        "render_status": "not_executed",
        "missing_layers": ["traffic_light_trace", "event_trace"],
        "evidence_scope": "render_input_metadata_only",
    }

    _write_json_exclusive(geometry_path, geometry)
    _write_json_exclusive(render_path, render_manifest)
