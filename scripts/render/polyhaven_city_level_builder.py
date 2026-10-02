"""Build a PBR city-corner level from a profile in two Unreal Editor processes.

Run the ``prepare`` phase first, exit Unreal completely, then run ``populate``
in a fresh Unreal process. This deliberately duplicates the saved styled level
before loading the duplicate as a UWorld; combining those operations in one
process previously exposed an Unreal world/GC failure.

Example (PowerShell, UE 5.8):

    $env:AIQ_PBR_PHASE = "prepare"
    & $UnrealEditorCmd $Project -ExecutePythonScript=$Script -NullRHI
    # Close that process before starting the second command.
    $env:AIQ_PBR_PHASE = "populate"
    & $UnrealEditorCmd $Project -ExecutePythonScript=$Script -NullRHI

The pbr_v1 profile retains the original level and output paths. The hero_v2
profile creates a separate P11 art checkpoint. Both preserve their source
level, the other city levels, and existing catalogs. Building geometry is
illustrative and is not surveyed building geometry.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from contextlib import suppress
from pathlib import Path
from typing import Any

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
MAP_PROJECT_PATH = ROOT / "simulation_projects" / "map_intake" / "district7.project.json"
SOURCE_LEVEL_ASSET = "/Game/City/District7_Styled/District7_Styled"
SCENE_PROFILE = os.environ.get("AIQ_PBR_PROFILE", "pbr_v1").strip().lower()
if SCENE_PROFILE not in {"pbr_v1", "hero_v2"}:
    raise ValueError("AIQ_PBR_PROFILE must be 'pbr_v1' or 'hero_v2'")
DEFAULT_LEVEL_ASSET = (
    "/Game/City/District7_PBR/District7_PBR_V2"
    if SCENE_PROFILE == "hero_v2"
    else "/Game/City/District7_PBR/District7_PBR"
)
LEVEL_ASSET = os.environ.get("AIQ_PBR_LEVEL_ASSET", DEFAULT_LEVEL_ASSET).strip().rstrip("/")
LEVEL_DIRECTORY, LEVEL_NAME = LEVEL_ASSET.rsplit("/", 1)
GEOMETRY_MANIFEST = ROOT / "render_unreal" / "CitySources" / "district7_geometry_manifest.v1.json"
PLACEMENT_MANIFEST = ROOT / "render_unreal" / "CitySources" / "district7_visual_placements.v1.json"
REL_GEOMETRY_MANIFEST = "CitySources/district7_geometry_manifest.v1.json"
STATE_PATH = (
    ROOT
    / "artifacts"
    / "tmp"
    / "city_pipeline"
    / (
        "district7_pbr_v2_prepare.json"
        if SCENE_PROFILE == "hero_v2"
        else "district7_pbr_prepare.json"
    )
)
REPORT_PATH = (
    ROOT
    / "artifacts"
    / "tmp"
    / "city_pipeline"
    / (
        "district7_pbr_v2_scene_qa.json"
        if SCENE_PROFILE == "hero_v2"
        else "district7_pbr_scene_qa.json"
    )
)
CAPTURE_PATH = (
    ROOT
    / "artifacts"
    / "unreal_demo"
    / ("district7_pbr_v2_hero.png" if SCENE_PROFILE == "hero_v2" else "district7_pbr_hero.png")
)
CAPTURE_REPORT_PATH = (
    ROOT
    / "artifacts"
    / "tmp"
    / "city_pipeline"
    / (
        "district7_pbr_v2_capture.json"
        if SCENE_PROFILE == "hero_v2"
        else "district7_pbr_capture.json"
    )
)

ASPHALT_MATERIAL = "/Game/City/Assets/PolyHaven/Materials/M_CityAsphalt2K"
PAVEMENT_MATERIAL = "/Game/City/Assets/PolyHaven/Materials/M_CityPavement2K"
FACADE_DIRECTORY = (
    "/Game/City/Assets/PolyHaven/UrbanFacade/modular_urban_apartments_facade_2k/StaticMeshes"
)
FACADE_MESH_NAMES = (
    "wall_standard_standard_01",
    "wall_window_centered_double_01",
    "window_centered_double_01",
    "door_window_small_04",
)
CLASS_GEOMETRY = "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
CLASS_CITY_VISUALS = "/Script/TrafficRenderRuntime.TrafficCityVisualActor"
HERO_CAMERA_LABEL = "Retained City Hero Corner"
ROAD_ACTOR_LABEL = "Retained SUMO Road Geometry"
VISUAL_ACTOR_LABEL = "Retained City Illustrative Visuals"
HERO_SITE_ID = "way_420032378_P11_visual_1"
PAD_ACTOR_LABEL = "PBR Hero P11 Poly Haven Pavement Pad"
ROOF_ACTOR_LABEL = "PBR Hero P11 Poly Haven Flat Roof"

EXPECTED_RENDERED_LANES = 88_163
EXPECTED_RENDERED_TILES = 305
EXPECTED_TEXTURE_REPEAT_METERS = 2.0
CENTIMETERS_PER_METER = 100.0
HERO_CAMERA_SUMO_XY = (1135.98, 7478.64)
HERO_TARGET_SUMO_XY = (
    (1119.4782318556297, 7466.672089859561) if SCENE_PROFILE == "hero_v2" else (1080.0, 7490.0)
)
HERO_CAMERA_HEIGHT_METERS = 8.0
HERO_TARGET_HEIGHT_METERS = 4.5 if SCENE_PROFILE == "hero_v2" else 5.0
HERO_CAMERA_FOV_DEGREES = 60.0 if SCENE_PROFILE == "hero_v2" else 64.0
FACADE_COLUMNS = 4 if SCENE_PROFILE == "hero_v2" else 2
FACADE_FLOORS = 3 if SCENE_PROFILE == "hero_v2" else 2
SITE_PAD_SIDE_METERS = 15.0


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default.resolve()
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _asset_path(asset: Any) -> str:
    if not asset:
        return ""
    return asset.get_path_name().split(".", 1)[0]


def _project_preflight() -> None:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise RuntimeError(
            f"wrong Unreal project loaded: {project_dir}; expected canonical project {PROJECT_ROOT}"
        )


def _resolve_inside(base: Path, value: str, label: str) -> Path:
    candidate = (base / value).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError(f"{label} resolves outside its project directory: {value}")
    return candidate


def _lane_shape_dimension_counts(net_path: Path) -> dict[str, int]:
    """Count source SUMO lane shapes by coordinate dimension without loading the net at once."""
    counts: dict[str, int] = {}
    missing_shape_count = 0
    for _event, element in ET.iterparse(net_path, events=("end",)):
        if element.tag != "lane":
            continue
        shape = element.get("shape", "").strip()
        if not shape:
            missing_shape_count += 1
        else:
            first_point = shape.split()[0]
            dimensions = str(len(first_point.split(",")))
            counts[dimensions] = counts.get(dimensions, 0) + 1
        element.clear()
    if missing_shape_count:
        counts["missing"] = missing_shape_count
    return dict(sorted(counts.items()))


def _validate_manifests() -> dict[str, Any]:
    for path in (MAP_PROJECT_PATH, GEOMETRY_MANIFEST, PLACEMENT_MANIFEST):
        if not path.is_file():
            raise FileNotFoundError(f"required source manifest is missing: {path}")

    map_project = _load_json(MAP_PROJECT_PATH, "map project")
    geometry = _load_json(GEOMETRY_MANIFEST, "geometry manifest")
    placements = _load_json(PLACEMENT_MANIFEST, "visual placement manifest")
    if geometry.get("schema_version") != "geometry_manifest.v1":
        raise ValueError("geometry manifest must use geometry_manifest.v1")
    if geometry.get("geometry_source") != "sumo_net_xml":
        raise ValueError("geometry manifest must describe SUMO net geometry")
    if geometry.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("geometry manifest must use SUMO XY meters")
    if placements.get("schema_version") != "city_visual_placements.v1":
        raise ValueError("placement manifest must use city_visual_placements.v1")
    if placements.get("purpose") != "illustrative_visual_only":
        raise ValueError("placement manifest must declare illustrative_visual_only scope")
    if placements.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("placement manifest must use SUMO XY meters")

    project_id = map_project.get("id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("map project has no id")
    if geometry.get("project_id") != project_id or placements.get("project_id") != project_id:
        raise ValueError("geometry, placement, and map project IDs do not match")
    if geometry.get("project_version") != map_project.get("version"):
        raise ValueError("geometry manifest and map project versions do not match")

    net_value = geometry.get("net_xml")
    if not isinstance(net_value, str) or not net_value:
        raise ValueError("geometry manifest net_xml must be a non-empty path")
    net_path = (GEOMETRY_MANIFEST.parent / net_value).resolve()
    project_source = map_project.get("source")
    if not isinstance(project_source, dict):
        raise ValueError("map project source must be an object")
    project_net_value = project_source.get("net_path")
    overlay_value = map_project.get("semantic_overlay_path")
    if not isinstance(project_net_value, str) or not isinstance(overlay_value, str):
        raise ValueError("map project must identify its net and semantic overlay")
    map_project_root = MAP_PROJECT_PATH.parent.resolve()
    project_net_path = _resolve_inside(map_project_root, project_net_value, "project net path")
    overlay_path = _resolve_inside(map_project_root, overlay_value, "semantic overlay path")
    if not net_path.is_file() or not project_net_path.is_file() or not overlay_path.is_file():
        raise FileNotFoundError("the retained net or semantic overlay source file is missing")
    if net_path != project_net_path:
        raise ValueError("geometry and map project manifests point to different SUMO net files")

    net_hash = _sha256(net_path)
    overlay_hash = _sha256(overlay_path)
    lane_shape_dimensions = _lane_shape_dimension_counts(net_path)
    expected_net_hash = geometry.get("source_net_sha256")
    expected_overlay_hash = geometry.get("semantic_overlay_sha256")
    if net_hash != expected_net_hash:
        raise ValueError("geometry manifest net hash differs from its source SUMO net")
    if overlay_hash != expected_overlay_hash:
        raise ValueError("geometry manifest overlay hash differs from its source semantic overlay")
    if placements.get("source_net_sha256") != expected_net_hash:
        raise ValueError("geometry and placement manifests refer to different SUMO net hashes")
    if placements.get("source_overlay_sha256") != expected_overlay_hash:
        raise ValueError("geometry and placement manifests refer to different overlay hashes")

    geometry_origin = geometry.get("local_origin")
    placement_origin = placements.get("local_origin")
    if not isinstance(geometry_origin, dict) or not isinstance(placement_origin, dict):
        raise ValueError("both source manifests must have local_origin objects")
    origin: dict[str, float] = {}
    for axis in ("x", "y"):
        g_value = _finite(geometry_origin.get(axis), f"geometry local_origin.{axis}")
        p_value = _finite(placement_origin.get(axis), f"placement local_origin.{axis}")
        if not math.isclose(g_value, p_value, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"geometry and placement local origins differ on {axis}")
        origin[axis] = g_value

    rows = placements.get("placements")
    if not isinstance(rows, list) or placements.get("placement_count") != len(rows):
        raise ValueError("placement_count does not match placement array length")
    if not rows:
        raise ValueError("placement manifest contains no sites")

    return {
        "map_project": map_project,
        "geometry": geometry,
        "placements": placements,
        "net_path": net_path,
        "overlay_path": overlay_path,
        "net_sha256": net_hash,
        "overlay_sha256": overlay_hash,
        "lane_shape_dimension_counts": lane_shape_dimensions,
        "origin": origin,
        "placement_rows": rows,
    }


def _level_file(asset_path: str) -> Path:
    if not asset_path.startswith("/Game/") or asset_path.endswith(".umap"):
        raise ValueError(f"invalid /Game level asset path: {asset_path}")
    parts = asset_path.removeprefix("/Game/").split("/")
    if not parts or any(not re.fullmatch(r"[A-Za-z0-9_]+", part) for part in parts):
        raise ValueError(f"invalid package name in level asset path: {asset_path}")
    return Path(unreal.Paths.project_content_dir()).resolve() / Path(*parts).with_suffix(".umap")


def _reserve(path: Path, purpose: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.pbr-city.lock")
    try:
        with lock.open("x", encoding="utf-8") as reservation:
            reservation.write(f"reserved by build_polyhaven_city_level.py: {purpose}\n")
    except FileExistsError as exc:
        raise FileExistsError(f"path is reserved by another PBR city build: {path}") from exc
    return lock


def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def _prepare_phase(inputs: dict[str, Any], content_dir: Path) -> dict[str, Any]:
    source_file = _level_file(SOURCE_LEVEL_ASSET)
    target_file = _level_file(LEVEL_ASSET)
    state_path = _env_path("AIQ_PBR_STATE_PATH", STATE_PATH)
    report_path = _env_path("AIQ_PBR_REPORT_PATH", REPORT_PATH)
    if not source_file.is_file() or not unreal.EditorAssetLibrary.does_asset_exist(
        SOURCE_LEVEL_ASSET
    ):
        raise FileNotFoundError(f"source styled level is missing: {SOURCE_LEVEL_ASSET}")
    if target_file.exists() or unreal.EditorAssetLibrary.does_asset_exist(LEVEL_ASSET):
        raise FileExistsError(f"refusing to overwrite existing PBR level: {LEVEL_ASSET}")
    if state_path.exists() or report_path.exists():
        raise FileExistsError(f"refusing to overwrite existing PBR state/report: {state_path}")

    locks: list[Path] = []
    try:
        locks.append(_reserve(target_file, "new PBR level package"))
        locks.append(_reserve(state_path, "two-phase prepare state"))
        source_hash_before = _sha256(source_file)
        source_level = unreal.load_asset(SOURCE_LEVEL_ASSET)
        if not source_level:
            raise RuntimeError(f"could not load source styled level: {SOURCE_LEVEL_ASSET}")

        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        if not asset_tools:
            raise RuntimeError("Unreal AssetTools are unavailable")
        try:
            unreal.EditorAssetLibrary.make_directory(LEVEL_DIRECTORY)
        except Exception as exc:
            unreal.log_warning(f"Could not explicitly create target package directory: {exc}")
        target_asset = asset_tools.duplicate_asset(LEVEL_NAME, LEVEL_DIRECTORY, source_level)
        if not target_asset or _asset_path(target_asset) != LEVEL_ASSET:
            raise RuntimeError(f"Unreal failed to duplicate source level to {LEVEL_ASSET}")
        if not unreal.EditorAssetLibrary.save_loaded_asset(target_asset):
            raise RuntimeError(f"Unreal failed to save prepared PBR duplicate: {target_file}")
        if not target_file.is_file() or target_file.stat().st_size <= 0:
            raise RuntimeError(f"prepared PBR level package is missing or empty: {target_file}")

        del target_asset
        del source_level
        del asset_tools
        gc.collect()

        source_hash_after = _sha256(source_file)
        if source_hash_after != source_hash_before:
            raise RuntimeError("source styled level changed while duplicating the PBR level")
        state = {
            "schema_version": "polyhaven_city_prepare.v1",
            "status": "prepared",
            "prepare_process_id": os.getpid(),
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "source_level_asset": SOURCE_LEVEL_ASSET,
            "source_level_file": str(source_file),
            "source_level_sha256": source_hash_after,
            "pbr_level_asset": LEVEL_ASSET,
            "pbr_level_file": str(target_file),
            "pbr_level_sha256": _sha256(target_file),
            "pbr_level_size_bytes": target_file.stat().st_size,
            "geometry_manifest_file": str(GEOMETRY_MANIFEST),
            "placement_manifest_file": str(PLACEMENT_MANIFEST),
            "source_net_sha256": inputs["net_sha256"],
            "source_overlay_sha256": inputs["overlay_sha256"],
            "local_origin_meters": inputs["origin"],
            "claim": "Duplicate prepared only; population runs in a separate fresh Unreal process.",
        }
        _write_json_new(state_path, state)
        unreal.log("POLYHAVEN_CITY_PREPARED " + json.dumps(state, sort_keys=True))
        return state
    finally:
        for lock in locks:
            try:
                lock.unlink(missing_ok=True)
            except OSError as exc:
                unreal.log_warning(f"Could not remove PBR build reservation {lock}: {exc}")


def _validate_prepare_state(
    inputs: dict[str, Any],
    source_file: Path,
    level_file: Path,
    state_path: Path,
) -> dict[str, Any]:
    if not state_path.is_file():
        raise FileNotFoundError(f"prepare phase state is missing: {state_path}")
    state = _load_json(state_path, "PBR prepare state")
    if (
        state.get("schema_version") != "polyhaven_city_prepare.v1"
        or state.get("status") != "prepared"
    ):
        raise ValueError("PBR prepare phase state is invalid")
    if state.get("prepare_process_id") == os.getpid():
        raise RuntimeError(
            "populate must run in a fresh Unreal process after the prepare process has exited"
        )
    expected = {
        "source_level_asset": SOURCE_LEVEL_ASSET,
        "pbr_level_asset": LEVEL_ASSET,
        "source_level_sha256": _sha256(source_file),
        "pbr_level_sha256": _sha256(level_file),
        "source_net_sha256": inputs["net_sha256"],
        "source_overlay_sha256": inputs["overlay_sha256"],
        "local_origin_meters": inputs["origin"],
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError(f"PBR prepared input/output changed before populate: {key}")
    return state


def _mesh_bounds(mesh: Any) -> dict[str, tuple[float, float, float]]:
    """Read mesh bounds through the editor property API, with method fallbacks."""

    candidates: list[Any] = []
    for method_name in ("get_bounding_box", "get_bounds"):
        method = getattr(mesh, method_name, None)
        if callable(method):
            try:
                candidates.append(method())
            except Exception as exc:
                unreal.log_warning(f"{method_name} failed for {_asset_path(mesh)}: {exc}")
    for property_name in ("extended_bounds", "bounds"):
        with suppress(Exception):
            candidates.append(mesh.get_editor_property(property_name))

    def member(value: Any, name: str) -> Any:
        try:
            return value.get_editor_property(name)
        except Exception:
            return getattr(value, name, None)

    def vector3(value: Any, label: str) -> tuple[float, float, float] | None:
        if value is None:
            return None
        try:
            return tuple(
                _finite(member(value, axis), f"{label}.{axis}") for axis in ("x", "y", "z")
            )  # type: ignore[return-value]
        except (ValueError, TypeError):
            return None

    for bounds in candidates:
        lower = vector3(member(bounds, "min"), "mesh bounds min")
        upper = vector3(member(bounds, "max"), "mesh bounds max")
        if lower and upper:
            sizes = tuple(upper[index] - lower[index] for index in range(3))
            if all(value >= 0.0 for value in sizes) and any(value > 0.0 for value in sizes):
                center = tuple((lower[index] + upper[index]) * 0.5 for index in range(3))
                return {"min": lower, "max": upper, "center": center, "size": sizes}

        center = vector3(member(bounds, "origin"), "mesh bounds origin")
        extent = vector3(member(bounds, "box_extent"), "mesh bounds box_extent")
        if (
            center
            and extent
            and all(value >= 0.0 for value in extent)
            and any(value > 0.0 for value in extent)
        ):
            lower = tuple(center[index] - extent[index] for index in range(3))
            upper = tuple(center[index] + extent[index] for index in range(3))
            size = tuple(upper[index] - lower[index] for index in range(3))
            return {"min": lower, "max": upper, "center": center, "size": size}

    raise RuntimeError(f"Unreal Python could not read static mesh bounds: {_asset_path(mesh)}")


def _mesh_qa(mesh_name: str, require_three_lods: bool) -> dict[str, Any]:
    asset_path = f"{FACADE_DIRECTORY}/{mesh_name}"
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise FileNotFoundError(f"required Poly Haven facade mesh is missing: {asset_path}")
    class_path = mesh.get_class().get_path_name()
    if class_path != "/Script/Engine.StaticMesh":
        raise TypeError(f"facade asset is not a StaticMesh: {asset_path} ({class_path})")
    lod_count = int(unreal.EditorStaticMeshLibrary.get_lod_count(mesh))
    vertices = [
        int(unreal.EditorStaticMeshLibrary.get_number_verts(mesh, lod_index))
        for lod_index in range(max(1, lod_count))
    ]
    if lod_count < 1 or not vertices or vertices[0] <= 0:
        raise RuntimeError(f"facade mesh has no renderable LOD0: {asset_path}")
    if require_three_lods and (lod_count < 3 or not (vertices[0] > vertices[1] > vertices[2] > 0)):
        raise RuntimeError(
            f"high-detail facade mesh needs three genuinely reduced LODs: {asset_path}, "
            f"lod_count={lod_count}, vertices={vertices}"
        )

    slots = []
    for slot in mesh.get_editor_property("static_materials"):
        material = slot.get_editor_property("material_interface")
        slots.append(
            {
                "slot_name": str(slot.get_editor_property("material_slot_name")),
                "material_asset": material.get_path_name() if material else "",
                "assigned": bool(material),
            }
        )
    if not slots or not any(slot["assigned"] for slot in slots):
        raise RuntimeError(f"facade mesh has no imported material assignments: {asset_path}")

    bounds = _mesh_bounds(mesh)
    return {
        "asset_path": _asset_path(mesh),
        "class": class_path,
        "lod_count": lod_count,
        "vertices_by_lod": vertices,
        "lod_reduction_verified": bool(
            lod_count >= 3 and vertices[0] > vertices[1] > vertices[2] > 0
        ),
        "bounds_cm": {key: list(value) for key, value in bounds.items()},
        "material_slots": slots,
    }


def _material_qa(asset_path: str) -> dict[str, Any]:
    material = unreal.load_asset(asset_path)
    if not material:
        raise FileNotFoundError(f"required Poly Haven PBR material is missing: {asset_path}")
    resolved_path = _asset_path(material)
    if resolved_path != asset_path:
        raise RuntimeError(
            f"loaded a different material: expected {asset_path}, got {resolved_path}"
        )
    class_path = material.get_class().get_path_name()
    if class_path not in ("/Script/Engine.Material", "/Script/Engine.MaterialInstanceConstant"):
        raise TypeError(
            f"PBR asset is not a Material/MaterialInstanceConstant: {asset_path} ({class_path})"
        )
    return {"asset_path": resolved_path, "class": class_path, "loaded": True}


def _check_build_result(value: Any, label: str) -> None:
    if isinstance(value, tuple):
        bools = [part for part in value if isinstance(part, bool)]
        errors = [part for part in value if isinstance(part, str) and part]
        if errors:
            raise RuntimeError(f"{label} failed: return={value!r}, error={'; '.join(errors)!r}")
        if bools and not any(bools):
            raise RuntimeError(f"{label} reported failure: return={value!r}")
        if not bools:
            unreal.log_warning(
                f"{label} binding returned no boolean status; native geometry counters are the gate"
            )
        return
    if isinstance(value, bool):
        if not value:
            raise RuntimeError(f"{label} reported failure: return={value!r}")
        return
    if isinstance(value, str):
        if value.strip():
            raise RuntimeError(f"{label} returned an error string: {value!r}")
        unreal.log_warning(
            f"{label} binding returned an empty out-error string; "
            "native geometry counters are the gate"
        )
        return
    if value is None:
        unreal.log_warning(
            f"{label} binding returned no status; native geometry counters are the gate"
        )
        return
    if not value:
        raise RuntimeError(f"{label} reported failure: return={value!r}")


def _summary_json(actor: Any, method_name: str, label: str) -> dict[str, Any]:
    value = getattr(actor, method_name)()
    if not isinstance(value, str):
        raise RuntimeError(f"{label} did not return JSON text")
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{label} returned malformed JSON")
    return decoded


def _component_material_path(component: Any, index: int = 0) -> str:
    material = component.get_material(index)
    return _asset_path(material)


def _rebuild_road(actors: Any, asphalt: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    matches = [
        actor
        for actor in actors.get_all_level_actors()
        if actor.get_class().get_path_name() == CLASS_GEOMETRY
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one SUMO geometry actor, found {len(matches)}")
    road = matches[0]
    road.set_actor_label(ROAD_ACTOR_LABEL)
    road.set_editor_property("geometry_manifest_path", REL_GEOMETRY_MANIFEST)
    road.set_editor_property("preview_max_lanes", 0)
    road.set_editor_property("road_material", asphalt)
    road.set_editor_property("texture_repeat_meters", EXPECTED_TEXTURE_REPEAT_METERS)
    if not math.isclose(
        float(road.get_editor_property("texture_repeat_meters")),
        EXPECTED_TEXTURE_REPEAT_METERS,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise RuntimeError("SUMO geometry actor did not retain TextureRepeatMeters=2")
    if _asset_path(road.get_editor_property("road_material")) != ASPHALT_MATERIAL:
        raise RuntimeError("SUMO geometry actor did not retain the Poly Haven asphalt material")

    result = road.rebuild_configured_geometry()
    _check_build_result(result, "RebuildConfiguredGeometry")
    summary = _summary_json(road, "get_build_summary_json", "SUMO geometry summary")
    total_lanes = int(summary.get("total_lane_count", 0))
    rendered_lanes = int(summary.get("rendered_lane_count", 0))
    rendered_tiles = int(summary.get("rendered_tile_count", 0))
    if total_lanes != EXPECTED_RENDERED_LANES or rendered_lanes != EXPECTED_RENDERED_LANES:
        raise RuntimeError(
            "SUMO road lane count differs from the verified XML lane-element count: "
            f"total={total_lanes}, rendered={rendered_lanes}, expected={EXPECTED_RENDERED_LANES}"
        )
    if rendered_tiles != EXPECTED_RENDERED_TILES:
        raise RuntimeError(
            f"SUMO road tile count differs from the requested scene contract: "
            f"actual={rendered_tiles}, expected={EXPECTED_RENDERED_TILES}"
        )

    components = road.get_components_by_class(unreal.ProceduralMeshComponent)
    if len(components) != rendered_tiles + 1:
        raise RuntimeError(
            f"road component count does not match tile count: components={len(components)}, "
            f"tiles={rendered_tiles}"
        )
    assigned_paths = []
    for component in components:
        component.set_material(0, asphalt)
        assigned_path = _component_material_path(component)
        if assigned_path != ASPHALT_MATERIAL:
            raise RuntimeError(
                f"SUMO road component has wrong material: expected {ASPHALT_MATERIAL}, "
                f"got {assigned_path!r}"
            )
        assigned_paths.append(assigned_path)
    if len(set(assigned_paths)) != 1:
        raise RuntimeError("not all SUMO road tile components use the same PBR asphalt material")

    return {
        "actor_label": road.get_actor_label(),
        "class": CLASS_GEOMETRY,
        "geometry_manifest_path": REL_GEOMETRY_MANIFEST,
        "source_net_sha256": inputs["net_sha256"],
        "source_overlay_sha256": inputs["overlay_sha256"],
        "geometry_summary": summary,
        "rebuild_configured_geometry_binding_return": repr(result),
        "native_summary_and_component_readback_used_as_gate": True,
        "total_lane_count": total_lanes,
        "rendered_lane_count": rendered_lanes,
        "rendered_tile_count": rendered_tiles,
        "road_material_asset": ASPHALT_MATERIAL,
        "texture_repeat_meters": EXPECTED_TEXTURE_REPEAT_METERS,
        "road_mesh_component_count_including_root": len(components),
        "all_road_components_use_material": len(assigned_paths) == rendered_tiles + 1,
    }


def _rebuild_city_visuals(actors: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    matches = [
        actor
        for actor in actors.get_all_level_actors()
        if actor.get_class().get_path_name() == CLASS_CITY_VISUALS
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one retained city visual actor, found {len(matches)}")
    visual_actor = matches[0]
    visual_actor.set_actor_label(VISUAL_ACTOR_LABEL)
    catalog = visual_actor.get_editor_property("asset_catalog")
    catalog_path = _asset_path(catalog)
    if not catalog or catalog_path != "/Game/City/Profiles/RetainedCityAssetCatalog":
        raise RuntimeError(
            f"retained city visual actor has an unexpected asset catalog: {catalog_path!r}"
        )
    visual_actor.set_editor_property(
        "placement_manifest_path", "CitySources/district7_visual_placements.v1.json"
    )
    visual_actor.set_editor_property("expected_net_sha256", inputs["net_sha256"])
    visual_actor.set_editor_property("expected_overlay_sha256", inputs["overlay_sha256"])
    result = visual_actor.rebuild_configured_placements()
    _check_build_result(result, "RebuildConfiguredPlacements")
    summary = _summary_json(visual_actor, "get_build_summary_json", "city visual summary")
    rows = inputs["placement_rows"]
    expected_counts = {
        "building": sum(1 for row in rows if row.get("kind") == "building"),
        "landscape": sum(1 for row in rows if row.get("kind") == "landscape"),
        "active_style": len({row.get("zone_type") for row in rows}),
    }
    actual_counts = {
        "building": int(summary.get("rendered_building_count", 0)),
        "landscape": int(summary.get("rendered_landscape_count", 0)),
        "active_style": int(summary.get("rendered_style_count", 0)),
    }
    if actual_counts != expected_counts:
        raise RuntimeError(
            "RebuildConfiguredPlacements did not reproduce the sourced placement manifest: "
            f"actual={actual_counts}, expected={expected_counts}, return={result!r}"
        )
    return {
        "actor_label": visual_actor.get_actor_label(),
        "class": CLASS_CITY_VISUALS,
        "asset_catalog": catalog_path,
        "placement_manifest_path": "CitySources/district7_visual_placements.v1.json",
        "source_net_sha256": inputs["net_sha256"],
        "source_overlay_sha256": inputs["overlay_sha256"],
        "rebuild_configured_placements_binding_return": repr(result),
        "summary": summary,
        "rendered_counts": actual_counts,
        "expected_counts": expected_counts,
        "native_summary_used_as_gate": True,
    }


def _city_placeholder_qa(actors: Any) -> dict[str, Any]:
    matches = [
        actor
        for actor in actors.get_all_level_actors()
        if actor.get_actor_label() == VISUAL_ACTOR_LABEL
        and actor.get_class().get_path_name() == CLASS_CITY_VISUALS
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one retained city visual actor, found {len(matches)}")
    visual_actor = matches[0]
    cube_components = []
    for component in visual_actor.get_components_by_class(
        unreal.HierarchicalInstancedStaticMeshComponent
    ):
        if _asset_path(component.get_editor_property("static_mesh")) == "/Engine/BasicShapes/Cube":
            cube_components.append(component)
    instance_count = sum(int(component.get_instance_count()) for component in cube_components)
    if instance_count != 1087:
        raise RuntimeError(
            f"retained Cube placeholder count changed: {instance_count}; expected 1087"
        )
    return {
        "actor_label": VISUAL_ACTOR_LABEL,
        "cube_mesh_asset": "/Engine/BasicShapes/Cube",
        "cube_hism_component_count": len(cube_components),
        "cube_instance_count_preserved": instance_count,
        "removed_by_builder": 0,
        "capture_visibility": (
            "V2 hero diagnostic excludes this actor's primitive components through the temporary "
            "SceneCapture2D HideActorComponents call; the saved level and overview keep placements."
        ),
    }


def _find_hero_site(inputs: dict[str, Any]) -> dict[str, Any]:
    target_x, target_y = HERO_TARGET_SUMO_XY
    residential = [
        row
        for row in inputs["placement_rows"]
        if row.get("kind") == "building" and row.get("zone_type") == "residential"
    ]
    if not residential:
        raise ValueError("placement manifest has no residential building sites")
    for row in residential:
        _finite(row.get("x_m"), "residential placement x_m")
        _finite(row.get("y_m"), "residential placement y_m")
    selected = min(
        residential,
        key=lambda row: math.hypot(row["x_m"] - target_x, row["y_m"] - target_y),
    )
    selected_distance = math.hypot(selected["x_m"] - target_x, selected["y_m"] - target_y)
    if SCENE_PROFILE == "hero_v2" and (
        selected.get("id") != HERO_SITE_ID or selected_distance > 0.01
    ):
        raise ValueError(
            f"hero_v2 must target the reviewed P11 illustrative site {HERO_SITE_ID}; "
            f"selected={selected.get('id')!r}, target_distance_m={selected_distance:.4f}"
        )
    clearance = _finite(selected.get("source_clearance_m"), "site source_clearance_m")
    radius = _finite(selected.get("max_footprint_radius_m"), "site max_footprint_radius_m")
    if clearance <= 0 or radius <= 0 or radius > clearance:
        raise ValueError(
            f"selected residential site has invalid safe envelope: {selected.get('id')}"
        )
    if SCENE_PROFILE == "hero_v2":
        heading = _finite(selected.get("heading_degrees"), "P11 heading_degrees")
        if selected.get("source_has_building_tag") is not False:
            raise ValueError(
                "P11 must remain labeled as illustrative without a source building tag"
            )
        if not math.isclose(radius, 10.8302253882, rel_tol=0.0, abs_tol=0.01):
            raise ValueError(f"P11 conservative radius changed: {radius:.4f}m")
        if not math.isclose(heading, 125.8410778, rel_tol=0.0, abs_tol=0.02):
            raise ValueError(f"P11 source heading changed: {heading:.4f} degrees")
    return selected


def _vector_component(value: Any, field: str) -> float:
    try:
        result = value.get_editor_property(field)
    except Exception:
        result = getattr(value, field, None)
    return _finite(result, f"vector.{field}")


def _site_unreal_xy(site: dict[str, Any], origin: dict[str, float]) -> tuple[float, float]:
    return (
        (float(site["x_m"]) - origin["x"]) * CENTIMETERS_PER_METER,
        (float(site["y_m"]) - origin["y"]) * CENTIMETERS_PER_METER,
    )


def _component_tags(component: Any) -> set[str]:
    try:
        values = component.get_editor_property("component_tags")
    except Exception:
        values = []
    return {str(value) for value in values}


def _instance_location(component: Any, index: int) -> tuple[float, float, float]:
    transform = component.get_instance_transform(index, True)
    translation = None
    for field in ("translation", "location"):
        try:
            translation = transform.get_editor_property(field)
        except Exception:
            translation = getattr(transform, field, None)
        if translation is not None:
            break
    if translation is None:
        raise RuntimeError("Unreal Python could not read a city HISM instance transform")
    return tuple(_vector_component(translation, axis) for axis in ("x", "y", "z"))


def _remove_site_placeholder(
    actors: Any, site: dict[str, Any], origin: dict[str, float]
) -> dict[str, Any]:
    visual_actors = [
        actor
        for actor in actors.get_all_level_actors()
        if actor.get_class().get_path_name() == CLASS_CITY_VISUALS
    ]
    if len(visual_actors) != 1:
        raise RuntimeError(f"expected one retained city visual actor, found {len(visual_actors)}")
    visual_actor = visual_actors[0]
    visual_actor.set_actor_label(VISUAL_ACTOR_LABEL)
    residential_cube_components = []
    for component in visual_actor.get_components_by_class(
        unreal.HierarchicalInstancedStaticMeshComponent
    ):
        mesh_path = _asset_path(component.get_editor_property("static_mesh"))
        if "residential" in _component_tags(component) and mesh_path == "/Engine/BasicShapes/Cube":
            residential_cube_components.append(component)
    if len(residential_cube_components) != 1:
        raise RuntimeError(
            "expected one residential Cube HISM component in the styled duplicate, "
            f"found {len(residential_cube_components)}"
        )

    expected_x, expected_y = _site_unreal_xy(site, origin)
    component = residential_cube_components[0]
    count_before = int(component.get_instance_count())
    matches = []
    for index in range(count_before):
        x, y, _z = _instance_location(component, index)
        if math.hypot(x - expected_x, y - expected_y) <= 30.0:
            matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one placeholder at selected site {site.get('id')}, "
            f"found {len(matches)} within 30 cm"
        )
    index = matches[0]
    if not component.remove_instance(index):
        raise RuntimeError(
            f"failed to remove the selected placeholder instance at {site.get('id')}"
        )
    count_after = int(component.get_instance_count())
    if count_after != count_before - 1:
        raise RuntimeError(
            f"placeholder HISM count did not decrease by one: before={count_before}, "
            f"after={count_after}"
        )
    for index in range(count_after):
        x, y, _z = _instance_location(component, index)
        if math.hypot(x - expected_x, y - expected_y) <= 30.0:
            raise RuntimeError("selected site still contains a placeholder instance after removal")
    return {
        "component_tags": sorted(_component_tags(component)),
        "mesh_asset": "/Engine/BasicShapes/Cube",
        "site_id": site.get("id"),
        "instance_count_before": count_before,
        "instance_count_after": count_after,
        "removed_instances": 1,
        "site_match_tolerance_cm": 30.0,
    }


def _component_vector(
    bounds: dict[str, tuple[float, float, float]], key: str
) -> tuple[float, float, float]:
    return bounds[key]


def _spawn_facade_actor(
    actors: Any,
    mesh: Any,
    label: str,
    center: tuple[float, float, float],
    yaw_degrees: float,
    scale: float,
    bounds: dict[str, tuple[float, float, float]],
) -> dict[str, Any]:
    center_bounds = _component_vector(bounds, "center")
    radians = math.radians(yaw_degrees)
    offset_x = center_bounds[0] * scale
    offset_y = center_bounds[1] * scale
    rotated_x = offset_x * math.cos(radians) - offset_y * math.sin(radians)
    rotated_y = offset_x * math.sin(radians) + offset_y * math.cos(radians)
    actor_origin = unreal.Vector(
        center[0] - rotated_x, center[1] - rotated_y, center[2] - center_bounds[2] * scale
    )
    rotation = unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw_degrees)
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, actor_origin, rotation)
    if not actor:
        raise RuntimeError(f"failed to spawn Poly Haven facade module: {label}")
    actor.set_actor_label(label)
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if component.get_num_materials() <= 0:
        raise RuntimeError(f"spawned facade actor has no material slots: {label}")
    assigned_materials = []
    for index in range(component.get_num_materials()):
        material = component.get_material(index)
        assigned_materials.append(material.get_path_name() if material else "")
    if not any(assigned_materials):
        raise RuntimeError(f"spawned facade actor lost its imported material: {label}")
    readback_location = actor.get_actor_location()
    readback_rotation = actor.get_actor_rotation()
    readback_scale = actor.get_actor_scale3d()
    actor_scale_values = (readback_scale.x, readback_scale.y, readback_scale.z)
    if not all(
        math.isclose(value, scale, rel_tol=0.0, abs_tol=1e-4) for value in actor_scale_values
    ):
        raise RuntimeError(f"facade actor scale readback mismatch: {label}")
    reregister = getattr(component, "reregister_component", None)
    if callable(reregister):
        try:
            reregister()
        except Exception as exc:
            unreal.log_warning(f"reregister_component failed for {label}: {exc}")

    def read_actor_bounds() -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        result = actor.get_actor_bounds(False, False)
        if not isinstance(result, tuple) or len(result) != 2:
            raise RuntimeError(f"Unreal did not return world bounds for {label}")
        measured_center = tuple(_vector_component(result[0], axis) for axis in ("x", "y", "z"))
        measured_extent = tuple(_vector_component(result[1], axis) for axis in ("x", "y", "z"))
        if any(value < 0.0 for value in measured_extent) or not any(
            value > 0.0 for value in measured_extent
        ):
            raise RuntimeError(
                f"Unreal returned invalid world bounds for {label}: {measured_extent}"
            )
        return measured_center, measured_extent

    bounds_center_before, bounds_extent_before = read_actor_bounds()
    correction_delta = tuple(center[index] - bounds_center_before[index] for index in range(3))
    if math.sqrt(sum(value * value for value in correction_delta)) > 0.05:
        actor.set_actor_location(
            unreal.Vector(
                readback_location.x + correction_delta[0],
                readback_location.y + correction_delta[1],
                readback_location.z + correction_delta[2],
            ),
            False,
            False,
        )
    bounds_center_after, bounds_extent_after = read_actor_bounds()
    readback_location = actor.get_actor_location()
    readback_rotation = actor.get_actor_rotation()
    readback_scale = actor.get_actor_scale3d()
    bounds_center_error = math.sqrt(
        sum((bounds_center_after[index] - center[index]) ** 2 for index in range(3))
    )
    if bounds_center_error > 2.0:
        raise RuntimeError(
            f"facade actor world bounds do not align with requested parcel: {label}, "
            f"before_cm={list(bounds_center_before)}, correction_cm={list(correction_delta)}, "
            f"after_cm={list(bounds_center_after)}, requested_cm={list(center)}, "
            f"error_cm={bounds_center_error:.2f}"
        )
    if abs(readback_rotation.pitch) > 1e-3 or abs(readback_rotation.roll) > 1e-3:
        raise RuntimeError(f"facade actor unexpectedly has pitch/roll: {label}")
    yaw_error = abs((readback_rotation.yaw - yaw_degrees + 180.0) % 360.0 - 180.0)
    if yaw_error > 0.1:
        raise RuntimeError(f"facade actor yaw readback mismatch: {label}, error={yaw_error:.3f}")

    world_min = [bounds_center_after[index] - bounds_extent_after[index] for index in range(3)]
    world_max = [bounds_center_after[index] + bounds_extent_after[index] for index in range(3)]
    return {
        "actor_label": actor.get_actor_label(),
        "mesh_asset": _asset_path(mesh),
        "requested_bounds_center_unreal_cm": list(center),
        "actor_origin_unreal_cm": [readback_location.x, readback_location.y, readback_location.z],
        "asset_local_bounds_cm": {
            "min": list(_component_vector(bounds, "min")),
            "max": list(_component_vector(bounds, "max")),
        },
        "world_bounds_space": "StaticMeshActor.get_actor_bounds after center correction",
        "world_bounds_center_before_correction_cm": list(bounds_center_before),
        "world_bounds_extent_before_correction_cm": list(bounds_extent_before),
        "world_bounds_correction_delta_cm": list(correction_delta),
        "world_bounds_center_unreal_cm": list(bounds_center_after),
        "world_bounds_extent_unreal_cm": list(bounds_extent_after),
        "world_bounds_min_unreal_cm": world_min,
        "world_bounds_max_unreal_cm": world_max,
        "world_bounds_center_error_cm": bounds_center_error,
        "rotation_degrees": [
            readback_rotation.roll,
            readback_rotation.pitch,
            readback_rotation.yaw,
        ],
        "uniform_scale": readback_scale.x,
        "material_assets": assigned_materials,
    }


def _spawn_horizontal_surface(
    actors: Any,
    mesh: Any,
    material: Any,
    label: str,
    center: tuple[float, float, float],
    size_cm: tuple[float, float],
    site_xy_cm: tuple[float, float],
    site_radius_cm: float,
) -> dict[str, Any]:
    mesh_bounds = _mesh_bounds(mesh)
    mesh_size = mesh_bounds["size"]
    if mesh_size[0] <= 0.0 or mesh_size[1] <= 0.0:
        raise RuntimeError(f"horizontal StaticMesh needs non-zero XY bounds: {_asset_path(mesh)}")
    scale = unreal.Vector(size_cm[0] / mesh_size[0], size_cm[1] / mesh_size[1], 1.0)
    local_center = mesh_bounds["center"]
    origin = unreal.Vector(
        center[0] - local_center[0] * scale.x,
        center[1] - local_center[1] * scale.y,
        center[2] - local_center[2] * scale.z,
    )
    actor = actors.spawn_actor_from_class(
        unreal.StaticMeshActor, origin, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    )
    if not actor:
        raise RuntimeError(f"failed to spawn Poly Haven horizontal surface: {label}")
    actor.set_actor_label(label)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    actor.set_actor_location(origin, False, False)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if component.get_num_materials() < 1:
        raise RuntimeError(f"horizontal surface has no material slots: {label}")
    component.set_material(0, material)
    assigned_material = _component_material_path(component)
    if assigned_material != _asset_path(material):
        raise RuntimeError(
            f"horizontal surface material readback mismatch: {label}, got={assigned_material!r}"
        )
    bounds_result = actor.get_actor_bounds(False, False)
    if not isinstance(bounds_result, tuple) or len(bounds_result) != 2:
        raise RuntimeError(f"Unreal did not return world bounds for {label}")
    bounds_center = tuple(_vector_component(bounds_result[0], axis) for axis in ("x", "y", "z"))
    bounds_extent = tuple(_vector_component(bounds_result[1], axis) for axis in ("x", "y", "z"))
    center_error = math.sqrt(sum((bounds_center[index] - center[index]) ** 2 for index in range(3)))
    if center_error > 2.0:
        raise RuntimeError(f"horizontal surface is not centered on its requested site: {label}")
    bounds_min = [bounds_center[index] - bounds_extent[index] for index in range(3)]
    bounds_max = [bounds_center[index] + bounds_extent[index] for index in range(3)]
    max_radius = max(
        math.hypot(x - site_xy_cm[0], y - site_xy_cm[1])
        for x in (bounds_min[0], bounds_max[0])
        for y in (bounds_min[1], bounds_max[1])
    )
    if max_radius > site_radius_cm + 1.0:
        raise RuntimeError(
            f"horizontal surface exceeds the site's conservative visual radius: {label}, "
            f"corner_radius_cm={max_radius:.1f}, allowed_radius_cm={site_radius_cm:.1f}"
        )
    return {
        "actor_label": actor.get_actor_label(),
        "mesh_asset": _asset_path(mesh),
        "material_asset": assigned_material,
        "center_unreal_cm": list(bounds_center),
        "requested_size_cm": list(size_cm),
        "world_bounds_extent_cm": list(bounds_extent),
        "max_world_bounds_radius_from_site_center_cm": max_radius,
        "allowed_site_radius_cm": site_radius_cm,
        "within_site_visual_envelope": True,
    }


def _build_one_facade(
    actors: Any,
    inputs: dict[str, Any],
    mesh_qa: dict[str, dict[str, Any]],
    meshes: dict[str, Any],
    pavement: Any | None = None,
) -> dict[str, Any]:
    site = _find_hero_site(inputs)
    site_x, site_y = _site_unreal_xy(site, inputs["origin"])
    camera_x, camera_y = _site_unreal_xy(
        {"x_m": HERO_CAMERA_SUMO_XY[0], "y_m": HERO_CAMERA_SUMO_XY[1]}, inputs["origin"]
    )

    yaw = _finite(site.get("heading_degrees"), "site heading_degrees")
    theta = math.radians(yaw)
    normal_x, normal_y = -math.sin(theta), math.cos(theta)
    toward_camera_x, toward_camera_y = camera_x - site_x, camera_y - site_y
    if normal_x * toward_camera_x + normal_y * toward_camera_y < 0:
        yaw += 180.0

    wall_name = "wall_standard_standard_01"
    window_name = "window_centered_double_01"
    door_name = "door_window_small_04"
    wall = meshes[wall_name]
    window = meshes[window_name]
    door = meshes[door_name]
    wall_bounds = {key: tuple(value) for key, value in mesh_qa[wall_name]["bounds_cm"].items()}
    window_bounds = {key: tuple(value) for key, value in mesh_qa[window_name]["bounds_cm"].items()}
    door_bounds = {key: tuple(value) for key, value in mesh_qa[door_name]["bounds_cm"].items()}
    wall_size = wall_bounds["size"]
    if wall_size[0] <= 0.0 or wall_size[2] <= 0.0 or wall_size[1] < 0.0:
        raise RuntimeError(f"wall module has invalid bounds: {wall_name}")

    columns = FACADE_COLUMNS
    floors = FACADE_FLOORS
    is_hero_v2 = SCENE_PROFILE == "hero_v2"
    site_radius_cm = min(
        _finite(site.get("source_clearance_m"), "site source clearance") * 100.0,
        _finite(site.get("max_footprint_radius_m"), "site max footprint radius") * 100.0,
    )
    safe_radius_cm = site_radius_cm * 0.90
    depth_cm = wall_size[0] if is_hero_v2 else 0.0
    unscaled_half_diagonal = 0.5 * math.sqrt((columns * wall_size[0]) ** 2 + depth_cm**2)
    facade_scale = min(1.0, safe_radius_cm / max(unscaled_half_diagonal, 1e-6))
    if facade_scale < 0.25:
        raise RuntimeError(
            "Poly Haven facade grid would be too small for this site envelope: "
            f"scale={facade_scale:.3f}"
        )
    half_diagonal = unscaled_half_diagonal * facade_scale
    if half_diagonal > site_radius_cm + 1e-3:
        raise RuntimeError(
            "facade transform extends beyond the site's conservative visual envelope"
        )

    rotation = math.radians(yaw)
    cos_yaw, sin_yaw = math.cos(rotation), math.sin(rotation)

    def world_center(
        local_x_cm: float, local_y_cm: float, z_cm: float
    ) -> tuple[float, float, float]:
        return (
            site_x + local_x_cm * cos_yaw - local_y_cm * sin_yaw,
            site_y + local_x_cm * sin_yaw + local_y_cm * cos_yaw,
            z_cm,
        )

    actors_qa: list[dict[str, Any]] = []
    scaled_wall_x = wall_size[0] * facade_scale
    scaled_wall_z = wall_size[2] * facade_scale
    scaled_wall_y = wall_size[1] * facade_scale
    front_y = depth_cm * facade_scale * 0.5
    for floor in range(floors):
        for column in range(columns):
            local_x = (column - (columns - 1) * 0.5) * scaled_wall_x
            cell_center_z = floor * scaled_wall_z + scaled_wall_z * 0.5
            center = world_center(local_x, front_y, cell_center_z)
            actors_qa.append(
                _spawn_facade_actor(
                    actors,
                    wall,
                    f"PBR Hero Residential Wall F{floor + 1} C{column + 1}",
                    center,
                    yaw,
                    facade_scale,
                    wall_bounds,
                )
            )

            # Keep high-detail window/door modules on the wall plane and within
            # each wall bay; the original Poly Haven materials remain assigned.
            door_column = 1 if is_hero_v2 else 0
            detail_name = door_name if floor == 0 and column == door_column else window_name
            detail_mesh = door if detail_name == door_name else window
            detail_bounds = door_bounds if detail_name == door_name else window_bounds
            detail_size = detail_bounds["size"]
            fit_scale = min(
                facade_scale,
                facade_scale * wall_size[0] * 0.78 / max(detail_size[0], 1e-6),
                facade_scale * wall_size[2] * 0.72 / max(detail_size[2], 1e-6),
            )
            if fit_scale < 0.15:
                raise RuntimeError(
                    f"detail module is too large/small for its facade bay: {detail_name}, "
                    f"scale={fit_scale:.3f}"
                )
            detail_center = world_center(
                local_x,
                front_y + scaled_wall_y * 0.5 + detail_size[1] * fit_scale * 0.5 + 1.0,
                cell_center_z,
            )
            actors_qa.append(
                _spawn_facade_actor(
                    actors,
                    detail_mesh,
                    f"PBR Hero Residential {detail_name} F{floor + 1} C{column + 1}",
                    detail_center,
                    yaw,
                    fit_scale,
                    detail_bounds,
                )
            )

    pad_qa = None
    roof_qa = None
    if is_hero_v2:
        if not pavement:
            raise RuntimeError("hero_v2 requires the imported Poly Haven pavement material")
        for side_sign, side_name in ((-1, "Left"), (1, "Right")):
            side_yaw = yaw - side_sign * 90.0
            side_x = side_sign * columns * scaled_wall_x * 0.5
            for floor in range(floors):
                cell_center_z = floor * scaled_wall_z + scaled_wall_z * 0.5
                side_center = world_center(side_x, 0.0, cell_center_z)
                actors_qa.append(
                    _spawn_facade_actor(
                        actors,
                        wall,
                        f"PBR Hero Residential {side_name} Wall F{floor + 1}",
                        side_center,
                        side_yaw,
                        facade_scale,
                        wall_bounds,
                    )
                )
                detail_size = window_bounds["size"]
                fit_scale = min(
                    facade_scale,
                    facade_scale * wall_size[0] * 0.78 / max(detail_size[0], 1e-6),
                    facade_scale * wall_size[2] * 0.72 / max(detail_size[2], 1e-6),
                )
                outward_offset = scaled_wall_y * 0.5 + detail_size[1] * fit_scale * 0.5 + 1.0
                side_detail_center = world_center(
                    side_x + side_sign * outward_offset, 0.0, cell_center_z
                )
                actors_qa.append(
                    _spawn_facade_actor(
                        actors,
                        window,
                        f"PBR Hero Residential {side_name} Window F{floor + 1}",
                        side_detail_center,
                        side_yaw,
                        fit_scale,
                        window_bounds,
                    )
                )

        plane = unreal.load_asset("/Engine/BasicShapes/Plane")
        if not plane:
            raise FileNotFoundError("Unreal basic Plane mesh is unavailable for the pad and roof")
        pad_side_cm = SITE_PAD_SIDE_METERS * CENTIMETERS_PER_METER
        pad_qa = _spawn_horizontal_surface(
            actors,
            plane,
            pavement,
            PAD_ACTOR_LABEL,
            (site_x, site_y, 1.0),
            (pad_side_cm, pad_side_cm),
            (site_x, site_y),
            site_radius_cm,
        )
        roof_qa = _spawn_horizontal_surface(
            actors,
            plane,
            pavement,
            ROOF_ACTOR_LABEL,
            (site_x, site_y, floors * scaled_wall_z + 1.0),
            (columns * scaled_wall_x, depth_cm * facade_scale),
            (site_x, site_y),
            site_radius_cm,
        )

    for record in actors_qa:
        bounds_min = record["world_bounds_min_unreal_cm"]
        bounds_max = record["world_bounds_max_unreal_cm"]
        corner_radius = max(
            math.hypot(x - site_x, y - site_y)
            for x in (bounds_min[0], bounds_max[0])
            for y in (bounds_min[1], bounds_max[1])
        )
        if corner_radius > site_radius_cm + 1.0:
            raise RuntimeError(
                f"facade module world bounds exceed the selected site's conservative visual "
                f"envelope: actor={record['actor_label']}, corner_radius_cm={corner_radius:.1f}, "
                f"allowed_radius_cm={site_radius_cm:.1f}"
            )
        record["max_world_bounds_radius_from_site_center_cm"] = corner_radius
        record["within_site_visual_envelope"] = True

    return {
        "site": {
            "id": site.get("id"),
            "zone_type": site.get("zone_type"),
            "kind": site.get("kind"),
            "sumo_xy_meters": [site["x_m"], site["y_m"]],
            "distance_to_hero_look_target_meters": math.hypot(
                site["x_m"] - HERO_TARGET_SUMO_XY[0],
                site["y_m"] - HERO_TARGET_SUMO_XY[1],
            ),
            "heading_degrees_from_source_manifest": site.get("heading_degrees"),
            "source_polygon_area_m2": site.get("source_polygon_area_m2"),
            "source_clearance_m": site.get("source_clearance_m"),
            "max_footprint_radius_m": site.get("max_footprint_radius_m"),
            "source_has_building_tag": site.get("source_has_building_tag"),
            "distance_from_road_sample_camera_meters": math.hypot(
                HERO_CAMERA_SUMO_XY[0] - float(site["x_m"]),
                HERO_CAMERA_SUMO_XY[1] - float(site["y_m"]),
            ),
            "placement_interpretation": (
                "Illustrative facade modules within the placement manifest's conservative "
                "radius; the source site is not a surveyed building footprint."
            ),
        },
        "grid": {
            "wall_mesh_asset": _asset_path(wall),
            "columns": columns,
            "floors": floors,
            "wall_panels": floors * columns,
            "front_wall_panels": floors * columns,
            "side_wall_panels": 2 * floors if is_hero_v2 else 0,
            "detail_panels": floors * columns + (2 * floors if is_hero_v2 else 0),
            "facade_heading_degrees": yaw,
            "uniform_wall_scale": facade_scale,
            "conservative_half_diagonal_cm": half_diagonal,
            "allowed_site_radius_cm": site_radius_cm,
            "pavement_pad": pad_qa,
            "flat_roof": roof_qa,
            "actors": actors_qa,
        },
    }


def _configure_camera(actors: Any, origin: dict[str, float]) -> dict[str, Any]:
    matches = [
        actor
        for actor in actors.get_all_level_actors()
        if actor.get_actor_label() == HERO_CAMERA_LABEL and isinstance(actor, unreal.CameraActor)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one existing hero camera to update, found {len(matches)}")
    camera = matches[0]
    location = unreal.Vector(
        (HERO_CAMERA_SUMO_XY[0] - origin["x"]) * CENTIMETERS_PER_METER,
        (HERO_CAMERA_SUMO_XY[1] - origin["y"]) * CENTIMETERS_PER_METER,
        HERO_CAMERA_HEIGHT_METERS * CENTIMETERS_PER_METER,
    )
    target = unreal.Vector(
        (HERO_TARGET_SUMO_XY[0] - origin["x"]) * CENTIMETERS_PER_METER,
        (HERO_TARGET_SUMO_XY[1] - origin["y"]) * CENTIMETERS_PER_METER,
        HERO_TARGET_HEIGHT_METERS * CENTIMETERS_PER_METER,
    )
    rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
    camera.set_actor_location(location, False, False)
    camera.set_actor_rotation(rotation, False)
    camera.camera_component.set_field_of_view(HERO_CAMERA_FOV_DEGREES)
    readback_location = camera.get_actor_location()
    readback_rotation = camera.get_actor_rotation()
    readback_fov = float(camera.camera_component.get_editor_property("field_of_view"))
    if not math.isclose(readback_location.z, HERO_CAMERA_HEIGHT_METERS * 100.0, abs_tol=0.1):
        raise RuntimeError("hero camera height readback does not match the requested 8 meters")
    if not math.isclose(readback_fov, HERO_CAMERA_FOV_DEGREES, abs_tol=0.1):
        raise RuntimeError("hero camera FOV readback differs from the selected scene profile")
    return {
        "actor_label": camera.get_actor_label(),
        "sumo_xy_meters": list(HERO_CAMERA_SUMO_XY),
        "target_sumo_xy_meters": list(HERO_TARGET_SUMO_XY),
        "local_origin_meters_subtracted": origin,
        "location_unreal_cm": [readback_location.x, readback_location.y, readback_location.z],
        "target_unreal_cm": [target.x, target.y, target.z],
        "rotation_degrees": [
            readback_rotation.roll,
            readback_rotation.pitch,
            readback_rotation.yaw,
        ],
        "field_of_view_degrees": readback_fov,
        "existing_overview_camera_preserved": True,
    }


def _set_component_color(component: Any, color: Any) -> bool:
    method = getattr(component, "set_light_color", None)
    if callable(method):
        method(color)
        return True
    try:
        component.set_editor_property("light_color", color)
        return True
    except Exception:
        return False


def _configure_dusk_lighting(actors: Any) -> dict[str, Any]:
    level_actors = actors.get_all_level_actors()
    directionals = [actor for actor in level_actors if isinstance(actor, unreal.DirectionalLight)]
    skylights = [actor for actor in level_actors if isinstance(actor, unreal.SkyLight)]
    if not directionals or not skylights:
        raise RuntimeError(
            f"styled source needs existing DirectionalLight and SkyLight; "
            f"found directionals={len(directionals)}, skylights={len(skylights)}"
        )

    sun = directionals[0]
    sky = skylights[0]
    sun_component = sun.light_component
    sky_component = sky.light_component
    old_sun_intensity = float(sun_component.get_editor_property("intensity"))
    old_sky_intensity = float(sky_component.get_editor_property("intensity"))
    yaw = float(sun.get_actor_rotation().yaw)
    sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-12.0, yaw=yaw), False)
    sun_component.set_intensity(12.0)
    sky_component.set_intensity(0.55)
    warm = unreal.LinearColor(1.0, 0.68, 0.46, 1.0)
    cool = unreal.LinearColor(0.52, 0.62, 0.88, 1.0)
    if not _set_component_color(sun_component, warm):
        raise RuntimeError("could not set the existing DirectionalLight to a warm dusk tint")
    if not _set_component_color(sky_component, cool):
        raise RuntimeError("could not set the existing SkyLight to a cool dusk fill")
    return {
        "directional_light_actor": sun.get_actor_label(),
        "directional_light_count_in_level": len(directionals),
        "directional_old_intensity": old_sun_intensity,
        "directional_intensity": float(sun_component.get_editor_property("intensity")),
        "directional_rotation_degrees": [
            sun.get_actor_rotation().roll,
            sun.get_actor_rotation().pitch,
            sun.get_actor_rotation().yaw,
        ],
        "directional_color_linear": [1.0, 0.68, 0.46, 1.0],
        "skylight_actor": sky.get_actor_label(),
        "skylight_count_in_level": len(skylights),
        "skylight_old_intensity": old_sky_intensity,
        "skylight_intensity": float(sky_component.get_editor_property("intensity")),
        "skylight_color_linear": [0.52, 0.62, 0.88, 1.0],
        "art_direction": (
            "Illustrative low warm sun and cool ambient fill; no added traffic or signal colors."
        ),
    }


def _configure_daylight_lighting(actors: Any) -> dict[str, Any]:
    level_actors = actors.get_all_level_actors()
    directionals = [actor for actor in level_actors if isinstance(actor, unreal.DirectionalLight)]
    skylights = [actor for actor in level_actors if isinstance(actor, unreal.SkyLight)]
    atmospheres = [actor for actor in level_actors if isinstance(actor, unreal.SkyAtmosphere)]
    if len(directionals) != 1 or len(skylights) != 1:
        raise RuntimeError(
            "hero_v2 requires exactly one existing DirectionalLight and SkyLight; "
            f"found directionals={len(directionals)}, skylights={len(skylights)}"
        )
    if len(atmospheres) > 1:
        raise RuntimeError(f"hero_v2 expected at most one SkyAtmosphere, found {len(atmospheres)}")
    if not atmospheres:
        atmosphere = actors.spawn_actor_from_class(
            unreal.SkyAtmosphere,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
        )
        if not atmosphere:
            raise RuntimeError("Unreal failed to spawn a SkyAtmosphere for hero_v2")
        atmosphere.set_actor_label("Retained City Daylight Sky Atmosphere")
    else:
        atmosphere = atmospheres[0]
        atmosphere.set_actor_label("Retained City Daylight Sky Atmosphere")

    sun = directionals[0]
    sky = skylights[0]
    sun_component = sun.light_component
    sky_component = sky.light_component
    old_sun_intensity = float(sun_component.get_editor_property("intensity"))
    old_sky_intensity = float(sky_component.get_editor_property("intensity"))
    camera_to_site_yaw = math.degrees(
        math.atan2(
            HERO_TARGET_SUMO_XY[1] - HERO_CAMERA_SUMO_XY[1],
            HERO_TARGET_SUMO_XY[0] - HERO_CAMERA_SUMO_XY[0],
        )
    )
    sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-45.0, yaw=camera_to_site_yaw), False)
    with suppress(Exception):
        sun_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun_component.set_intensity(10.0)
    if not _set_component_color(sun_component, unreal.LinearColor(1.0, 0.97, 0.88, 1.0)):
        raise RuntimeError("could not set the existing DirectionalLight to a daylight color")
    set_sunlight = getattr(sun_component, "set_atmosphere_sun_light", None)
    if callable(set_sunlight):
        set_sunlight(True)
    else:
        sun_component.set_editor_property("atmosphere_sun_light", True)
    set_sunlight_index = getattr(sun_component, "set_atmosphere_sun_light_index", None)
    if callable(set_sunlight_index):
        set_sunlight_index(0)
    else:
        sun_component.set_editor_property("atmosphere_sun_light_index", 0)

    with suppress(Exception):
        sky_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_component.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
    sky_component.set_editor_property("real_time_capture", True)
    sky_component.set_intensity(2.0)
    if not _set_component_color(sky_component, unreal.LinearColor(0.78, 0.86, 1.0, 1.0)):
        raise RuntimeError("could not set the existing SkyLight to a daylight fill")
    recapture = getattr(sky_component, "recapture_sky", None)
    if callable(recapture):
        recapture()
    else:
        raise RuntimeError("Unreal SkyLight component does not expose recapture_sky")

    return {
        "directional_light_actor": sun.get_actor_label(),
        "directional_light_count_in_level": len(directionals),
        "directional_old_intensity": old_sun_intensity,
        "directional_intensity": float(sun_component.get_editor_property("intensity")),
        "directional_rotation_degrees": [
            sun.get_actor_rotation().roll,
            sun.get_actor_rotation().pitch,
            sun.get_actor_rotation().yaw,
        ],
        "directional_color_linear": [1.0, 0.97, 0.88, 1.0],
        "atmosphere_sun_light_enabled": bool(
            sun_component.get_editor_property("atmosphere_sun_light")
        ),
        "atmosphere_sun_light_index": int(
            sun_component.get_editor_property("atmosphere_sun_light_index")
        ),
        "sky_atmosphere_actor": atmosphere.get_actor_label(),
        "sky_atmosphere_count_in_level": len(
            [
                actor
                for actor in actors.get_all_level_actors()
                if isinstance(actor, unreal.SkyAtmosphere)
            ]
        ),
        "skylight_actor": sky.get_actor_label(),
        "skylight_count_in_level": len(skylights),
        "skylight_old_intensity": old_sky_intensity,
        "skylight_intensity": float(sky_component.get_editor_property("intensity")),
        "skylight_source_type": str(sky_component.get_editor_property("source_type")),
        "skylight_real_time_capture": bool(sky_component.get_editor_property("real_time_capture")),
        "skylight_recapture_called": True,
        "art_direction": "Clear daylight with an atmosphere sun and cool real-time sky fill.",
    }


def _populate_phase(inputs: dict[str, Any], content_dir: Path) -> dict[str, Any]:
    state_path = _env_path("AIQ_PBR_STATE_PATH", STATE_PATH)
    report_path = _env_path("AIQ_PBR_REPORT_PATH", REPORT_PATH)
    source_file = _level_file(SOURCE_LEVEL_ASSET)
    level_file = _level_file(LEVEL_ASSET)
    capture_path = _env_path("AIQ_PBR_CAPTURE_PATH", CAPTURE_PATH)
    capture_report_path = _env_path("AIQ_PBR_CAPTURE_REPORT_PATH", CAPTURE_REPORT_PATH)
    if report_path.exists():
        raise FileExistsError(f"refusing to overwrite PBR scene QA report: {report_path}")
    if capture_path.exists() or capture_report_path.exists():
        raise FileExistsError(
            "refusing to overwrite a previous PBR capture; set fresh AIQ_PBR_CAPTURE_PATH "
            "and AIQ_PBR_CAPTURE_REPORT_PATH values"
        )
    if not source_file.is_file() or not level_file.is_file():
        raise FileNotFoundError("the source styled level or prepared PBR duplicate is missing")
    if not unreal.EditorAssetLibrary.does_asset_exist(LEVEL_ASSET):
        raise FileNotFoundError(f"prepared PBR level is not registered: {LEVEL_ASSET}")
    prepare_state = _validate_prepare_state(inputs, source_file, level_file, state_path)

    lock = _reserve(report_path, "populated PBR level QA")
    try:
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if not levels or not editor or not actors:
            raise RuntimeError("Unreal level, editor, or actor subsystem is unavailable")
        # Load the duplicated UWorld through the level subsystem in this fresh
        # process; do not call unreal.load_asset(LEVEL_ASSET) for a UWorld here.
        if not levels.load_level(LEVEL_ASSET):
            raise RuntimeError(f"Unreal failed to load prepared PBR level: {LEVEL_ASSET}")
        world = editor.get_editor_world()
        if not world:
            raise RuntimeError("Unreal editor world is unavailable after loading PBR level")

        asphalt_qa = _material_qa(ASPHALT_MATERIAL)
        pavement_qa = _material_qa(PAVEMENT_MATERIAL)
        pavement = unreal.load_asset(PAVEMENT_MATERIAL) if SCENE_PROFILE == "hero_v2" else None
        if SCENE_PROFILE == "hero_v2" and not pavement:
            raise FileNotFoundError(
                f"verified Poly Haven pavement disappeared: {PAVEMENT_MATERIAL}"
            )
        required_lod = {"window_centered_double_01", "door_window_small_04"}
        mesh_qa = {
            name: _mesh_qa(name, require_three_lods=name in required_lod)
            for name in FACADE_MESH_NAMES
        }
        meshes = {
            name: unreal.load_asset(f"{FACADE_DIRECTORY}/{name}") for name in FACADE_MESH_NAMES
        }
        if not all(meshes.values()):
            raise RuntimeError("a verified facade mesh could not be retained for level population")
        asphalt = unreal.load_asset(ASPHALT_MATERIAL)
        if not asphalt:
            raise FileNotFoundError(f"verified road material disappeared: {ASPHALT_MATERIAL}")

        road_qa = _rebuild_road(actors, asphalt, inputs)
        city_visuals_qa = _rebuild_city_visuals(actors, inputs)
        if SCENE_PROFILE == "hero_v2":
            placeholder_qa = _city_placeholder_qa(actors)
        else:
            placeholder_qa = _remove_site_placeholder(
                actors, _find_hero_site(inputs), inputs["origin"]
            )
        facade_qa = _build_one_facade(actors, inputs, mesh_qa, meshes, pavement)
        camera_qa = _configure_camera(actors, inputs["origin"])
        lighting_qa = (
            _configure_daylight_lighting(actors)
            if SCENE_PROFILE == "hero_v2"
            else _configure_dusk_lighting(actors)
        )

        save_result = levels.save_current_level()
        if save_result is False or not level_file.is_file() or level_file.stat().st_size <= 0:
            raise RuntimeError(f"Unreal failed to save populated PBR level: {level_file}")
        if _sha256(source_file) != prepare_state["source_level_sha256"]:
            raise RuntimeError("source styled level changed while creating the PBR duplicate")
        if _sha256(GEOMETRY_MANIFEST) != _sha256(Path(prepare_state["geometry_manifest_file"])):
            raise RuntimeError("geometry source manifest changed during PBR population")

        all_actors = actors.get_all_level_actors()
        report = {
            "schema_version": "polyhaven_city_scene_qa.v1",
            "status": "created",
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "source_level_asset": SOURCE_LEVEL_ASSET,
            "source_level_sha256": _sha256(source_file),
            "source_level_preserved": True,
            "pbr_level_asset": LEVEL_ASSET,
            "pbr_level_file": str(level_file),
            "pbr_level_size_bytes": level_file.stat().st_size,
            "pbr_level_sha256_after_population": _sha256(level_file),
            "prepared_level_sha256_before_population": prepare_state["pbr_level_sha256"],
            "prepare_process_id": prepare_state["prepare_process_id"],
            "populate_process_id": os.getpid(),
            "separate_process_verified": prepare_state["prepare_process_id"] != os.getpid(),
            "source_manifests": {
                "geometry_manifest_file": str(GEOMETRY_MANIFEST),
                "geometry_manifest_sha256": _sha256(GEOMETRY_MANIFEST),
                "placement_manifest_file": str(PLACEMENT_MANIFEST),
                "placement_manifest_sha256": _sha256(PLACEMENT_MANIFEST),
                "map_project_file": str(MAP_PROJECT_PATH),
                "semantic_overlay_file": str(inputs["overlay_path"]),
                "semantic_overlay_sha256": inputs["overlay_sha256"],
                "source_net_file": str(inputs["net_path"]),
                "source_net_sha256": inputs["net_sha256"],
                "geometry_manifest_declared_lane_count": inputs["geometry"].get("lane_count"),
                "source_lane_shape_dimension_counts": inputs["lane_shape_dimension_counts"],
                "placement_manifest_declared_zone_count": inputs["placements"].get("zone_count"),
                "local_origin_meters": inputs["origin"],
                "net_overlay_hashes_and_origin_match": True,
            },
            "pbr_materials": {
                "road": asphalt_qa,
                "pavement_available_for_next_local_pass": pavement_qa,
                "pavement_used_for_p11_pad_and_roof": pavement_qa
                if SCENE_PROFILE == "hero_v2"
                else None,
            },
            "road_geometry": road_qa,
            "city_visuals": city_visuals_qa,
            "facade_meshes": mesh_qa,
            "hero_facade": facade_qa,
            "hero_camera": camera_qa,
            "dusk_lighting": lighting_qa,
            "actors": {
                "total_count": len(all_actors),
                "labels": sorted(actor.get_actor_label() for actor in all_actors),
            },
            "capture": {
                "script": str(ROOT / "scripts" / "render" / "capture_retained_city_level.py"),
                "level_asset": LEVEL_ASSET,
                "camera_label": HERO_CAMERA_LABEL,
                "screenshot_path": str(capture_path),
                "qa_report_path": str(capture_report_path),
                "road_material_environment": ASPHALT_MATERIAL,
                "ground_material_environment": "preserve",
                "hero_capture_hidden_actor_label": (
                    VISUAL_ACTOR_LABEL if SCENE_PROFILE == "hero_v2" else ""
                ),
                "required_environment": {
                    "AIQ_CITY_LEVEL_PATH": LEVEL_ASSET,
                    "AIQ_CITY_CAMERA_LABEL": HERO_CAMERA_LABEL,
                    "AIQ_CITY_SCREENSHOT_PATH": str(capture_path),
                    "AIQ_CITY_CAPTURE_REPORT_PATH": str(capture_report_path),
                    "AIQ_CITY_ROAD_MATERIAL_ASSET": ASPHALT_MATERIAL,
                    "AIQ_CITY_GROUND_MATERIAL_ASSET": "preserve",
                    "AIQ_CITY_HIDE_ACTOR_LABEL": (
                        VISUAL_ACTOR_LABEL if SCENE_PROFILE == "hero_v2" else ""
                    ),
                },
            },
            "claim": (
                "Illustrative visual pass only. One residential overlay site is not surveyed "
                "building geometry; no traffic demand, signal state, vehicle replay, or "
                "performance target is claimed."
            ),
        }
        report["profile"] = SCENE_PROFILE
        if set(inputs["lane_shape_dimension_counts"]) == {"2"}:
            report["source_elevation_assumption"] = (
                "All lane shapes in this retained net contain only XY coordinates; road "
                "geometry therefore uses a flat Z=0 assumption because source elevation is absent."
            )
        else:
            report["source_elevation_assumption"] = (
                "Lane shapes contain mixed or missing dimensions; see the source dimension "
                "counts. No general elevation-preservation claim is made."
            )
        if SCENE_PROFILE == "hero_v2":
            report["visual_placeholder_qa"] = placeholder_qa
            report["daylight_lighting"] = report.pop("dusk_lighting")
            report["scene_scope"] = {
                "artifact_kind": "P11 close-up art checkpoint",
                "p11_source_has_building_tag": False,
                "nearest_tls_id": "cluster_13441822896_13441822897_2304474781_2370217996",
                "nearest_tls_distance_meters": 86.27,
                "tls_visible_in_hero_frame": False,
                "replay_trace_present": False,
                "m1_signal_replay_acceptance": False,
                "limitations": [
                    "P11 has no source building tag; facade is illustrative only.",
                    "No validated TLS is present in the hero frame; "
                    "no vehicle replay trace is included.",
                    "This still does not complete M1 replay, TLS, or performance acceptance.",
                ],
            }
        else:
            report["removed_local_placeholder"] = placeholder_qa
        _write_json_new(report_path, report)
        unreal.log("POLYHAVEN_CITY_SCENE_QA " + json.dumps(report, sort_keys=True))
        return report
    finally:
        try:
            lock.unlink(missing_ok=True)
        except OSError as exc:
            unreal.log_warning(f"Could not remove PBR scene QA reservation {lock}: {exc}")


def run() -> dict[str, Any]:
    _project_preflight()
    phase = os.environ.get("AIQ_PBR_PHASE", "prepare").strip().lower()
    if phase not in {"prepare", "populate"}:
        raise ValueError("AIQ_PBR_PHASE must be 'prepare' or 'populate'")
    inputs = _validate_manifests()
    content_dir = Path(unreal.Paths.project_content_dir()).resolve()
    if phase == "prepare":
        return _prepare_phase(inputs, content_dir)
    return _populate_phase(inputs, content_dir)


def main() -> dict[str, Any]:
    try:
        result = run()
        print("POLYHAVEN_CITY_LEVEL_RESULT " + json.dumps(result, indent=2, sort_keys=True))
        return result
    except Exception as exc:
        unreal.log_error(f"POLYHAVEN_CITY_LEVEL_FAILED {type(exc).__name__}: {exc}")
        raise
