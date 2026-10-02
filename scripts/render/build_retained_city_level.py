"""Create a read-only visual bootstrap level from retained SUMO road geometry.

Run with UnrealEditor-Cmd 5.8 and ``-ExecutePythonScript=<this-file>``.  The
script creates one new level package and refuses to replace an existing asset.
It renders retained static road geometry only; it does not create demand,
vehicles, replay traces, or claim simulation alignment beyond the manifest origin.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

import unreal


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEVEL = "/Game/City/District7_OSM/District7_OSM"
DEFAULT_REPORT = (
    ROOT / "artifacts" / "tmp" / "city_pipeline" / "district7_osm_visual_bootstrap.json"
)
ASPHALT_ASSET = "/Game/Demo092/Materials/Asphalt"
GROUND_ASSET = "/Game/Demo092/Materials/Concrete"
CENTIMETERS_PER_METER = 100.0


def _env_path(name: str, default: Path | None = None) -> Path:
    value = os.environ.get(name)
    if not value:
        if default is None:
            raise ValueError(
                f"{name} must be set explicitly; the builder does not fall back to a fixture manifest"
            )
        return default.resolve()
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _load_geometry(path: Path) -> tuple[dict[str, Any], Path, dict[str, float], dict[str, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "geometry_manifest.v1":
        raise ValueError("geometry manifest must use geometry_manifest.v1")
    if data.get("geometry_source") != "sumo_net_xml":
        raise ValueError("geometry manifest must identify SUMO net geometry")
    if data.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("geometry manifest coordinate_system must be sumo_xy_meters")

    raw_bounds = data.get("bounds")
    if not isinstance(raw_bounds, dict):
        raise ValueError("geometry manifest bounds must be an object")
    bounds = {
        key: _finite(raw_bounds.get(key), f"bounds.{key}")
        for key in ("min_x", "min_y", "max_x", "max_y")
    }
    if bounds["max_x"] <= bounds["min_x"] or bounds["max_y"] <= bounds["min_y"]:
        raise ValueError("geometry manifest bounds must have positive width and height")

    raw_origin = data.get("local_origin")
    if raw_origin is None:
        origin = {"x": bounds["min_x"], "y": bounds["min_y"]}
    elif isinstance(raw_origin, dict):
        origin = {
            "x": _finite(raw_origin.get("x"), "local_origin.x"),
            "y": _finite(raw_origin.get("y"), "local_origin.y"),
        }
    else:
        raise ValueError("geometry manifest local_origin must be an object")

    net_value = data.get("net_xml")
    if not isinstance(net_value, str) or not net_value:
        raise ValueError("geometry manifest net_xml must be a non-empty path")
    net_path = Path(net_value).expanduser()
    if not net_path.is_absolute():
        net_path = path.parent / net_path
    net_path = net_path.resolve()
    if not net_path.is_file():
        raise ValueError(f"geometry manifest net_xml does not exist: {net_path}")
    return data, net_path, bounds, origin


def _level_package_path(value: str) -> str:
    path = value.strip().rstrip("/")
    if not path.startswith("/Game/"):
        raise ValueError("AIQ_CITY_LEVEL_PATH must be an Unreal /Game package path")
    parts = path.split("/")[2:]
    if not parts or any(not re.fullmatch(r"[A-Za-z0-9_]+", part) for part in parts):
        raise ValueError("AIQ_CITY_LEVEL_PATH contains an invalid Unreal package name")
    if path.endswith(".umap"):
        raise ValueError("AIQ_CITY_LEVEL_PATH must omit the .umap extension")
    return path


def _preflight_level(level_path: str, content_dir: Path) -> tuple[Path, Path]:
    relative = Path(*level_path.removeprefix("/Game/").split("/"))
    level_file = content_dir / relative.with_suffix(".umap")
    lock_file = level_file.with_name(f".{level_file.stem}.city-bootstrap.lock")
    exists_in_registry = unreal.EditorAssetLibrary.does_asset_exist(level_path)
    if exists_in_registry or level_file.exists():
        raise FileExistsError(f"refusing to overwrite existing level asset: {level_path}")
    level_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_file.open("x", encoding="utf-8") as reservation:
            reservation.write("reserved by build_retained_city_level.py\n")
    except FileExistsError as exc:
        raise FileExistsError(f"level path is reserved by another bootstrap: {level_path}") from exc
    return level_file, lock_file


def _reserve_report(path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing QA report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.city-bootstrap.lock")
    try:
        with lock.open("x", encoding="utf-8") as reservation:
            reservation.write("reserved by build_retained_city_level.py\n")
    except FileExistsError as exc:
        raise FileExistsError(f"QA report path is reserved by another bootstrap: {path}") from exc
    return lock


def _spawn(
    subsystem: Any,
    actor_class: Any,
    name: str,
    location: tuple[float, float, float],
    rotation: Any = None,
) -> Any:
    vector = unreal.Vector(*location)
    rotator = rotation if rotation is not None else unreal.Rotator(0.0, 0.0, 0.0)
    actor = subsystem.spawn_actor_from_class(actor_class, vector, rotator)
    if not actor:
        raise RuntimeError(f"failed to spawn {name}")
    actor.set_actor_label(name)
    return actor


def _apply_road_material(geometry_actor: Any, material: Any, expected_tile_count: int) -> int:
    components = geometry_actor.get_components_by_class(unreal.ProceduralMeshComponent)
    # The native actor owns one empty root mesh plus one component per rendered tile.
    if len(components) != expected_tile_count + 1:
        raise RuntimeError(
            "SUMO road component count does not match the tile summary: "
            f"components={len(components)}, expected_tiles={expected_tile_count}"
        )

    for component in components:
        component.set_material(0, material)
        assigned = component.get_material(0)
        assigned_path = assigned.get_path_name().split(".", 1)[0] if assigned else ""
        if assigned_path != ASPHALT_ASSET:
            raise RuntimeError(
                "failed to assign Asphalt to a SUMO road mesh component: "
                f"expected {ASPHALT_ASSET}, got {assigned_path!r}"
            )
    return len(components) - 1


def _configure_ground_and_lighting(
    actors: Any,
    bounds: dict[str, float],
    origin: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    min_x = (bounds["min_x"] - origin["x"]) * CENTIMETERS_PER_METER
    max_x = (bounds["max_x"] - origin["x"]) * CENTIMETERS_PER_METER
    min_y = (bounds["min_y"] - origin["y"]) * CENTIMETERS_PER_METER
    max_y = (bounds["max_y"] - origin["y"]) * CENTIMETERS_PER_METER
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    width = max_x - min_x
    height = max_y - min_y
    margin = max(10_000.0, max(width, height) * 0.025)

    ground = _spawn(
        actors,
        unreal.StaticMeshActor,
        "Retained City Ground",
        (center_x, center_y, -270.0),
    )
    ground_component = ground.static_mesh_component
    ground_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    ground.set_actor_scale3d(
        unreal.Vector((width + margin * 2) / 100.0, (height + margin * 2) / 100.0, 5.0)
    )
    ground_material = unreal.load_asset(GROUND_ASSET)
    if ground_material:
        ground_component.set_material(0, ground_material)
        ground_material_status = {"asset": GROUND_ASSET, "assigned": True}
    else:
        unreal.log_warning(f"Ground material is missing; retaining engine default: {GROUND_ASSET}")
        ground_material_status = {"asset": GROUND_ASSET, "assigned": False}

    directional = _spawn(
        actors,
        unreal.DirectionalLight,
        "Retained City Daylight",
        (center_x, center_y, max(width, height) * 0.75),
        unreal.Rotator(-55.0, -35.0, 0.0),
    )
    directional.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    directional.light_component.set_intensity(5.0)

    sky = _spawn(
        actors,
        unreal.SkyLight,
        "Retained City Ambient Light",
        (center_x, center_y, 5000.0),
    )
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_intensity(1.0)

    target = unreal.Vector(center_x, center_y, 0.0)
    camera_location = unreal.Vector(
        center_x + width * 0.72,
        center_y - height * 0.72,
        max(width, height) * 1.05,
    )
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target)
    camera = _spawn(
        actors,
        unreal.CameraActor,
        "Retained City Overview Camera",
        (camera_location.x, camera_location.y, camera_location.z),
        camera_rotation,
    )
    camera.camera_component.set_field_of_view(55.0)

    return (
        {"x": center_x, "y": center_y, "width": width, "height": height, "margin": margin},
        {"x": camera_location.x, "y": camera_location.y, "z": camera_location.z},
        ground_material_status,
    )


def run() -> dict[str, Any]:
    geometry_path = _env_path("AIQ_CITY_GEOMETRY_MANIFEST")
    report_path = _env_path("AIQ_CITY_REPORT_PATH", DEFAULT_REPORT)
    level_path = _level_package_path(os.environ.get("AIQ_CITY_LEVEL_PATH", DEFAULT_LEVEL))
    raw_max_lanes = os.environ.get("AIQ_CITY_MAX_LANES", "0")
    try:
        max_lanes = int(raw_max_lanes)
    except ValueError as exc:
        raise ValueError("AIQ_CITY_MAX_LANES must be an integer >= 0") from exc
    if max_lanes < 0:
        raise ValueError("AIQ_CITY_MAX_LANES must be an integer >= 0")

    geometry, net_path, bounds, origin = _load_geometry(geometry_path)
    content_dir = Path(unreal.Paths.project_content_dir()).resolve()
    level_file, level_lock = _preflight_level(level_path, content_dir)
    report_lock = _reserve_report(report_path)
    level_created = False
    try:
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if not levels or not actors:
            raise RuntimeError("Unreal level/editor actor subsystems are unavailable")
        if not levels.new_level(level_path):
            raise RuntimeError(f"Unreal failed to create new level: {level_path}")
        level_created = True

        actor_class = unreal.load_class(
            None, "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
        )
        if not actor_class:
            raise RuntimeError("TrafficSumoGeometryActor class is not loaded")
        geometry_actor = _spawn(
            actors,
            actor_class,
            "Retained SUMO Road Geometry",
            (0.0, 0.0, 0.0),
        )
        asphalt = unreal.load_asset(ASPHALT_ASSET)
        if not asphalt:
            raise RuntimeError(f"Road material is missing: {ASPHALT_ASSET}")
        geometry_actor.set_editor_property("road_material", asphalt)

        build_result = geometry_actor.build_from_geometry_manifest(str(geometry_path), max_lanes)
        unreal.log(f"CITY_GEOMETRY_BUILD_RETURN {build_result!r}")
        if isinstance(build_result, tuple):
            return_values = [value for value in build_result if isinstance(value, bool)]
            built = any(return_values)
            errors = [value for value in build_result if isinstance(value, str) and value]
            build_error = "; ".join(errors)
        else:
            built = bool(build_result)
            build_error = str(build_result) if isinstance(build_result, str) else ""

        summary_text = geometry_actor.get_build_summary_json()
        unreal.log(f"CITY_GEOMETRY_BUILD_SUMMARY {summary_text!r}")
        try:
            summary = json.loads(summary_text) if isinstance(summary_text, str) else {}
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"geometry actor returned an invalid build summary: {exc}") from exc
        if not isinstance(summary, dict):
            raise RuntimeError("geometry actor returned a malformed build summary")
        total_lanes = int(summary.get("total_lane_count", 0))
        rendered_lanes = int(summary.get("rendered_lane_count", 0))
        rendered_segments = int(summary.get("rendered_segment_count", 0))
        rendered_tiles = int(summary.get("rendered_tile_count", 0))
        tile_size_meters = _finite(summary.get("tile_size_meters"), "tile_size_meters")
        skipped_degenerate_segments = int(summary.get("skipped_degenerate_segment_count", 0))
        junctions = int(summary.get("junction_count", 0))
        if rendered_lanes <= 0 or rendered_segments <= 0 or rendered_tiles <= 0:
            raise RuntimeError(
                "SUMO geometry actor produced no lane geometry; "
                f"return={build_result!r}, summary={summary!r}, error={build_error!r}"
            )
        if tile_size_meters <= 0 or skipped_degenerate_segments < 0:
            raise RuntimeError(f"SUMO geometry actor returned invalid tile QA: {summary!r}")
        if not built:
            unreal.log_warning(
                "Geometry build binding returned falsy, but actor counters confirm rendered "
                f"geometry: {summary!r}; OutError={build_error!r}"
            )

        road_material_tile_component_count = _apply_road_material(
            geometry_actor, asphalt, rendered_tiles
        )
        ground_summary, camera_location, ground_material = _configure_ground_and_lighting(
            actors, bounds, origin
        )

        if total_lanes <= 0 or rendered_lanes <= 0 or rendered_segments <= 0:
            raise RuntimeError("geometry actor produced no lane geometry")

        save_result = levels.save_current_level()
        if save_result is False or not level_file.is_file():
            raise RuntimeError(f"Unreal did not save the new level package: {level_file}")

        report = {
            "schema_version": "retained_city_visual_bootstrap.v1",
            "visual_map_bootstrap": True,
            "full_map_requested": max_lanes == 0,
            "full_map_geometry_confirmed": max_lanes == 0 and rendered_lanes == total_lanes,
            "render_scope": "full_retained_net_requested"
            if max_lanes == 0
            else "lane_limited_probe",
            "geometry_manifest_path": str(geometry_path),
            "net_xml_path": str(net_path),
            "saved_level_asset": level_path,
            "saved_level_file": str(level_file.resolve()),
            "max_lanes": max_lanes,
            "total_lane_count": total_lanes,
            "rendered_lane_count": rendered_lanes,
            "rendered_segment_count": rendered_segments,
            "rendered_tile_count": rendered_tiles,
            "tile_size_meters": tile_size_meters,
            "skipped_degenerate_segment_count": skipped_degenerate_segments,
            "junction_count": junctions,
            "local_origin_meters": origin,
            "bounds_meters": bounds,
            "ground_bounds_unreal_cm": ground_summary,
            "camera_location_unreal_cm": camera_location,
            "road_material": {
                "asset": ASPHALT_ASSET,
                "assigned": True,
                "assigned_tile_component_count": road_material_tile_component_count,
            },
            "ground_material": ground_material,
            "vertical_geometry_assumption": (
                "flat SUMO XY geometry at Z=0; lane shape elevation and terrain are not rendered"
            ),
            "demand_complete": False,
            "vehicle_replay_complete": False,
            "claim": (
                "Visual map bootstrap from retained SUMO network geometry only; "
                "no demand, replay, traffic performance, or action-safety claim."
            ),
        }
        with report_path.open("x", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2, sort_keys=True)
            report_file.write("\n")
        unreal.log("CITY_VISUAL_BOOTSTRAP_QA " + json.dumps(report, sort_keys=True))
        return report
    finally:
        for lock_file in (level_lock, report_lock):
            try:
                lock_file.unlink(missing_ok=True)
            except OSError as exc:
                unreal.log_warning(f"Could not remove bootstrap reservation {lock_file}: {exc}")
        if not level_created and level_file.exists():
            unreal.log_warning(
                "A new level package exists despite bootstrap failure; it was left untouched at "
                + str(level_file)
            )


try:
    RESULT = run()
    print("CITY_VISUAL_BOOTSTRAP_RESULT " + json.dumps(RESULT, indent=2, sort_keys=True))
except Exception as exc:
    unreal.log_error(f"CITY_VISUAL_BOOTSTRAP_FAILED: {type(exc).__name__}: {exc}")
    raise
