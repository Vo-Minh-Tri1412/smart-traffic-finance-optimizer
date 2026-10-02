"""Renderer-neutral Unreal contract smoke check.

This check deliberately runs without Unreal: it validates the artifacts that the UE
adapter consumes and repeats the canonical SUMO front-bumper geometry calculation.
It is useful on CI and on machines where the editor is unavailable.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMAS = {
    "geometry_manifest": "geometry_manifest.v1",
    "vehicle_trace": "vehicle_trace.v2",
    "visibility_trace": "visibility_trace.v1",
    "traffic_light_trace": "traffic_light_trace.v1",
    "semantic_overlay": "semantic_overlay.v2",
    "event_trace": "event_trace.v1",
    "render_run_manifest": "render_run_manifest.v1",
    "sensor_dataset_manifest": "sensor_dataset_manifest.v1",
    "camera_calibration": "camera_calibration.v1",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve(owner: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else owner.parent / candidate


def _check_vehicle(vehicle: dict[str, Any]) -> None:
    required = (
        "vehicle_id",
        "vehicle_type",
        "x",
        "y",
        "speed",
        "angle",
        "length_m",
        "width_m",
        "height_m",
        "ground_clearance_m",
        "elevation_m",
        "reference_point",
    )
    missing = [key for key in required if key not in vehicle]
    if missing:
        raise ValueError(f"vehicle missing canonical fields: {', '.join(missing)}")
    for key in ("vehicle_id", "vehicle_type"):
        if not isinstance(vehicle[key], str) or not vehicle[key]:
            raise ValueError(f"vehicle {key} must be a non-empty string")
    for key in ("x", "y", "speed", "angle", "length_m", "width_m", "height_m",
                "ground_clearance_m", "elevation_m"):
        _finite_number(vehicle[key], key)
    if vehicle["reference_point"] != "front_bumper_center":
        raise ValueError("vehicle reference_point must be front_bumper_center")
    if min(float(vehicle[key]) for key in ("length_m", "width_m", "height_m")) <= 0:
        raise ValueError("vehicle dimensions must be positive")
    if float(vehicle["ground_clearance_m"]) < 0:
        raise ValueError("vehicle ground_clearance_m cannot be negative")


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _check_trace(path: Path, max_frames: int | None) -> tuple[int, int, dict[str, float]]:
    frame_count = 0
    vehicle_ids: set[str] = set()
    previous_time = -math.inf
    first_center: dict[str, float] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if max_frames and frame_count >= max_frames:
            break
        if not line.strip():
            continue
        frame = json.loads(line)
        if frame.get("schema_version") != SCHEMAS["vehicle_trace"]:
            raise ValueError(f"{path}:{line_number} unsupported vehicle trace schema")
        time_seconds = _finite_number(frame["time_seconds"], "time_seconds")
        timestep = _finite_number(frame["timestep"], "timestep")
        if time_seconds < 0 or timestep < 0 or not timestep.is_integer():
            raise ValueError("time_seconds and integer timestep must be non-negative")
        if time_seconds < previous_time:
            raise ValueError(f"{path}:{line_number} trace time is not monotonic")
        previous_time = time_seconds
        vehicles = frame.get("vehicles")
        if not isinstance(vehicles, list):
            raise ValueError(f"{path}:{line_number} vehicles must be a list")
        frame_ids: set[str] = set()
        for vehicle in vehicles:
            if not isinstance(vehicle, dict):
                raise ValueError(f"{path}:{line_number} vehicle must be an object")
            _check_vehicle(vehicle)
            if vehicle["vehicle_id"] in frame_ids:
                raise ValueError(f"duplicate vehicle_id: {vehicle['vehicle_id']}")
            frame_ids.add(vehicle["vehicle_id"])
            vehicle_ids.add(str(vehicle["vehicle_id"]))
            if not first_center:
                angle = math.radians(float(vehicle["angle"]))
                first_center = {
                    "x": float(vehicle["x"]) - math.sin(angle) * float(vehicle["length_m"]) / 2,
                    "y": float(vehicle["y"]) - math.cos(angle) * float(vehicle["length_m"]) / 2,
                }
        frame_count += 1
    if frame_count == 0:
        raise ValueError(f"{path} contains no frames")
    return frame_count, len(vehicle_ids), first_center


def run(manifest_path: Path, output: Path | None, max_frames: int | None) -> dict[str, Any]:
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive when supplied")
    manifest = _load(manifest_path)
    if manifest.get("schema_version") != SCHEMAS["render_run_manifest"]:
        raise ValueError("manifest schema_version must be render_run_manifest.v1")
    for key in ("run_id", "geometry_manifest", "vehicle_trace", "renderer"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise ValueError(f"manifest {key} must be a non-empty string")
    geometry_path = _resolve(manifest_path, str(manifest["geometry_manifest"]))
    trace_path = _resolve(manifest_path, str(manifest["vehicle_trace"]))
    geometry = _load(geometry_path)
    if geometry.get("schema_version") != SCHEMAS["geometry_manifest"]:
        raise ValueError("geometry schema_version must be geometry_manifest.v1")
    if geometry.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("geometry coordinate_system must be sumo_xy_meters")
    if geometry.get("geometry_source") != "sumo_net_xml":
        raise ValueError("geometry_source must be sumo_net_xml")
    if not isinstance(geometry.get("net_xml"), str) or not geometry["net_xml"]:
        raise ValueError("geometry net_xml must be a non-empty string")
    if not _resolve(geometry_path, geometry["net_xml"]).is_file():
        raise ValueError("geometry net_xml file does not exist")
    bounds = geometry["bounds"]
    for key in ("min_x", "min_y", "max_x", "max_y"):
        _finite_number(bounds[key], key)
    if bounds["max_x"] < bounds["min_x"] or bounds["max_y"] < bounds["min_y"]:
        raise ValueError("geometry bounds are inverted")
    origin = geometry.get(
        "local_origin", {"x": bounds.get("min_x", 0.0), "y": bounds.get("min_y", 0.0)}
    )
    for key in ("x", "y"):
        _finite_number(origin[key], f"origin.{key}")
    frame_count, vehicle_count, center = _check_trace(trace_path, max_frames)
    report = {
        "success": True,
        "renderer": "unreal",
        "run_id": manifest.get("run_id", ""),
        "schemas": SCHEMAS,
        "loaded_frame_count": frame_count,
        "unique_vehicle_count": vehicle_count,
        "local_origin_meters": {"x": float(origin["x"]), "y": float(origin["y"])},
        "front_bumper_center_sample_m": center,
        "unit_policy": "SUMO metres -> Unreal centimetres (100.0), explicit local origin",
        "authority": "SUMO authoritative; Unreal render/sensor adapter only",
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="render_run_manifest.v1 JSON")
    parser.add_argument("--output", type=Path, help="optional smoke report path")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()
    try:
        print(
            json.dumps(run(args.manifest, args.output, args.max_frames), indent=2, sort_keys=True)
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
