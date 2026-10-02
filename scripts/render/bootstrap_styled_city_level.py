"""Create an illustrative, cullable city pass on a duplicate of the tiled map.

Run with the canonical TrafficRender project and Unreal Engine 5.8:

    UnrealEditor-Cmd.exe TrafficRender.uproject -ExecutePythonScript=<this-file>

The source tiled level is kept intact. This bootstraps semantic building and
landscape instances with simple placeholder geometry; it does not represent
surveyed buildings or claim a frame-rate target.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import gc
from collections import Counter
from pathlib import Path
from typing import Any

import unreal


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
SOURCE_LEVEL_ASSET = "/Game/City/District7_Tiled/District7_Tiled"
STYLED_LEVEL_ASSET = "/Game/City/District7_Styled/District7_Styled"
CATALOG_ASSET = "/Game/City/Profiles/RetainedCityAssetCatalog"
PLACEMENT_MANIFEST = ROOT / "render_unreal" / "CitySources" / "district7_visual_placements.v1.json"
GEOMETRY_MANIFEST = ROOT / "render_unreal" / "CitySources" / "district7_geometry_manifest.v1.json"
REPORT_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "styled_city_bootstrap.json"
PREPARE_STATE_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "styled_city_prepare.json"
CENTIMETERS_PER_METER = 100.0
HERO_CAMERA_LABEL = "Retained City Hero Corner"
REL_PLACEMENT_MANIFEST = "CitySources/district7_visual_placements.v1.json"
REL_GEOMETRY_MANIFEST = "CitySources/district7_geometry_manifest.v1.json"
EXPECTED_BUILDINGS = 1087
EXPECTED_LANDSCAPE = 0
EXPECTED_ACTIVE_STYLES = 7

# Keep the manifest's eight categories explicit: a missing or newly introduced
# category should stop the bootstrap instead of becoming an unstyled instance.
STYLE_SPECS = (
    {
        "zone_type": "residential",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/WarmStone",
        "footprint": 20.0,
        "height": (12.0, 38.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "education",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/TealFacade",
        "footprint": 20.0,
        "height": (14.0, 36.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "industrial",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/BrushedSteel",
        "footprint": 20.0,
        "height": (9.0, 24.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "port_logistics",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/Concrete",
        "footprint": 20.0,
        "height": (10.0, 30.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "commercial",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/BlueGlass",
        "footprint": 20.0,
        "height": (20.0, 60.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "healthcare",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/WarmPaint",
        "footprint": 20.0,
        "height": (16.0, 40.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "market_retail",
        "kind": "building",
        "mesh": "/Engine/BasicShapes/Cube",
        "material": "/Game/Demo092/Materials/YellowPaint",
        "footprint": 20.0,
        "height": (7.0, 20.0),
        "cull": 20000.0,
    },
    {
        "zone_type": "neutral",
        "kind": "landscape",
        "mesh": "/Engine/BasicShapes/Sphere",
        "material": "/Game/Demo092/Materials/LeafGreen",
        "footprint": 10.0,
        "height": (4.0, 12.0),
        "cull": 2500.0,
    },
)


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


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _level_file(asset_path: str, content_dir: Path) -> Path:
    if not asset_path.startswith("/Game/"):
        raise ValueError(f"expected /Game asset path: {asset_path}")
    relative = Path(*asset_path.removeprefix("/Game/").split("/"))
    return content_dir / relative.with_suffix(".umap")


def _catalog_file(asset_path: str, content_dir: Path) -> Path:
    if not asset_path.startswith("/Game/"):
        raise ValueError(f"expected /Game asset path: {asset_path}")
    relative = Path(*asset_path.removeprefix("/Game/").split("/"))
    return content_dir / relative.with_suffix(".uasset")


def _reserve(path: Path, purpose: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.styled-city.lock")
    try:
        with lock.open("x", encoding="utf-8") as reservation:
            reservation.write(f"reserved by bootstrap_styled_city_level.py: {purpose}\n")
    except FileExistsError as exc:
        raise FileExistsError(f"path is reserved by another styled-city bootstrap: {path}") from exc
    return lock


def _load_json(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_manifests(
    placements_path: Path, geometry_path: Path
) -> tuple[dict[str, Any], dict[str, Any], Counter]:
    placements = _load_json(placements_path, "placement manifest")
    geometry = _load_json(geometry_path, "geometry manifest")
    if placements.get("schema_version") != "city_visual_placements.v1":
        raise ValueError("placement manifest must use city_visual_placements.v1")
    if placements.get("purpose") != "illustrative_visual_only":
        raise ValueError("placement manifest must declare illustrative_visual_only scope")
    if placements.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("placement manifest must use SUMO XY meters")
    if (
        geometry.get("schema_version") != "geometry_manifest.v1"
        or geometry.get("geometry_source") != "sumo_net_xml"
    ):
        raise ValueError("geometry manifest must describe retained SUMO net geometry")
    if geometry.get("coordinate_system") != "sumo_xy_meters":
        raise ValueError("geometry manifest must use SUMO XY meters")

    net_hash = placements.get("source_net_sha256")
    overlay_hash = placements.get("source_overlay_sha256")
    if not isinstance(net_hash, str) or len(net_hash) != 64:
        raise ValueError("placement manifest has no valid source net SHA-256")
    if not isinstance(overlay_hash, str) or len(overlay_hash) != 64:
        raise ValueError("placement manifest has no valid source overlay SHA-256")
    if geometry.get("source_net_sha256") != net_hash:
        raise ValueError("placement and road geometry manifests refer to different SUMO nets")
    if geometry.get("semantic_overlay_sha256") != overlay_hash:
        raise ValueError(
            "placement and road geometry manifests refer to different semantic overlays"
        )

    placement_origin = placements.get("local_origin")
    geometry_origin = geometry.get("local_origin")
    if not isinstance(placement_origin, dict) or not isinstance(geometry_origin, dict):
        raise ValueError("both manifests must have local_origin objects")
    origin = {
        axis: _finite(placement_origin.get(axis), f"placement local_origin.{axis}")
        for axis in ("x", "y")
    }
    for axis in ("x", "y"):
        geometry_value = _finite(geometry_origin.get(axis), f"geometry local_origin.{axis}")
        if not math.isclose(origin[axis], geometry_value, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"placement and geometry local origins differ on {axis}")

    rows = placements.get("placements")
    if not isinstance(rows, list) or placements.get("placement_count") != len(rows):
        raise ValueError("placement_count does not match placements array")
    counts: Counter = Counter()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("placement manifest contains a non-object row")
        counts[(row.get("zone_type"), row.get("kind"))] += 1
    expected = {(s["zone_type"], s["kind"]) for s in STYLE_SPECS}
    if not set(counts).issubset(expected):
        raise ValueError(f"placement manifest has a zone/kind without a catalog style: {counts}")
    building_count = sum(count for (zone, kind), count in counts.items() if kind == "building")
    landscape_count = sum(count for (zone, kind), count in counts.items() if kind == "landscape")
    if building_count != EXPECTED_BUILDINGS or landscape_count != EXPECTED_LANDSCAPE:
        raise ValueError(
            "retained placement counts changed: "
            f"buildings={building_count}, landscape={landscape_count}"
        )
    return placements, geometry, counts


def _asset_path(asset: Any) -> str:
    if asset is None:
        return ""
    value = asset.get_path_name()
    return value.split(".", 1)[0]


def _soft_asset_path(value: Any) -> str:
    direct = _asset_path(value)
    if direct:
        return direct
    for method_name in ("get_asset_path_string", "to_string"):
        method = getattr(value, method_name, None)
        if method:
            try:
                candidate = str(method())
            except Exception:
                continue
            if candidate.startswith(("/Game/", "/Engine/")):
                return candidate.split(".", 1)[0]
    text = str(value)
    match = re.search(r"(?:/Game|/Engine)/[A-Za-z0-9_./]+", text)
    if not match:
        return ""
    return match.group(0).split(".", 1)[0]


def _query_mesh_lods(mesh_path: str) -> tuple[int | None, bool]:
    mesh = unreal.load_asset(mesh_path)
    if not mesh:
        raise FileNotFoundError(f"required city mesh is missing: {mesh_path}")
    available = hasattr(mesh, "get_num_lods")
    if not available:
        return None, False
    try:
        return int(mesh.get_num_lods()), True
    except Exception as exc:
        unreal.log_warning(f"Could not query LOD count for {mesh_path}: {exc}")
        return None, True


def _validate_catalog(catalog: Any) -> list[dict[str, Any]]:
    if not catalog or _asset_path(catalog) != CATALOG_ASSET:
        raise RuntimeError(f"could not load city catalog data asset: {CATALOG_ASSET}")
    if (
        catalog.get_class().get_path_name()
        != "/Script/TrafficRenderRuntime.TrafficCityAssetCatalog"
    ):
        raise RuntimeError(f"asset at {CATALOG_ASSET} is not a TrafficCityAssetCatalog")
    rows = list(catalog.get_editor_property("styles"))
    if len(rows) != len(STYLE_SPECS):
        raise RuntimeError(
            f"city catalog must contain {len(STYLE_SPECS)} styles, found {len(rows)}"
        )

    expected_by_zone = {spec["zone_type"]: spec for spec in STYLE_SPECS}
    seen: set[str] = set()
    qa_styles = []
    for style in rows:
        zone_type = str(style.get_editor_property("zone_type"))
        spec = expected_by_zone.get(zone_type)
        if not spec or zone_type in seen:
            raise RuntimeError(f"city catalog has an unknown or duplicate style: {zone_type!r}")
        seen.add(zone_type)
        kind = str(style.get_editor_property("kind"))
        mesh_path = _soft_asset_path(style.get_editor_property("mesh"))
        material_path = _soft_asset_path(style.get_editor_property("material_override"))
        footprint = float(style.get_editor_property("max_footprint_diameter_meters"))
        min_height = float(style.get_editor_property("min_height_meters"))
        max_height = float(style.get_editor_property("max_height_meters"))
        cull_distance = float(style.get_editor_property("end_cull_distance_meters"))
        source = str(style.get_editor_property("asset_source"))
        license_name = str(style.get_editor_property("license"))
        expected = (
            kind == spec["kind"]
            and mesh_path == spec["mesh"]
            and material_path == spec["material"]
            and math.isclose(footprint, spec["footprint"], rel_tol=0.0, abs_tol=1e-5)
            and math.isclose(min_height, spec["height"][0], rel_tol=0.0, abs_tol=1e-5)
            and math.isclose(max_height, spec["height"][1], rel_tol=0.0, abs_tol=1e-5)
            and math.isclose(cull_distance, spec["cull"], rel_tol=0.0, abs_tol=1e-5)
            and source == "Unreal Engine built-in geometry"
            and license_name == "Epic Engine content"
        )
        if not expected:
            raise RuntimeError(
                f"city catalog style differs from the reviewed bootstrap profile: {zone_type}; "
                f"mesh={mesh_path!r}, material={material_path!r}"
            )
        lod_count, lod_api_available = _query_mesh_lods(mesh_path)
        qa_style = {
            "zone_type": zone_type,
            "kind": kind,
            "mesh_asset": mesh_path,
            "mesh_lod_count": lod_count,
            "mesh_lod_api_available": lod_api_available,
            "material_asset": material_path,
            "max_footprint_diameter_meters": footprint,
            "height_range_meters": [min_height, max_height],
            "end_cull_distance_meters": cull_distance,
            "asset_source": source,
            "license": license_name,
        }
        if zone_type == "neutral":
            qa_style["semantic_note"] = (
                "Catalog retains a neutral Sphere placeholder, but the sourced manifest has no "
                "neutral placements; no trees, parks, or vegetation are inferred or rendered."
            )
        qa_styles.append(qa_style)
    if seen != set(expected_by_zone):
        raise RuntimeError(
            f"city catalog is missing expected styles: {sorted(set(expected_by_zone) - seen)}"
        )
    return sorted(qa_styles, key=lambda row: row["zone_type"])


def _create_catalog(catalog_class: Any, styles_class: Any) -> tuple[Any, list[dict[str, Any]]]:
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory_class = getattr(unreal, "DataAssetFactory", None)
    if not tools or not factory_class:
        raise RuntimeError("Unreal AssetTools or DataAssetFactory is unavailable")

    resolved: list[tuple[dict[str, Any], Any, Any]] = []
    for spec in STYLE_SPECS:
        mesh = unreal.load_asset(spec["mesh"])
        material = unreal.load_asset(spec["material"])
        if not mesh:
            raise FileNotFoundError(f"required city mesh is missing: {spec['mesh']}")
        if not material:
            raise FileNotFoundError(f"required city material is missing: {spec['material']}")
        resolved.append((spec, mesh, material))

    factory = factory_class()
    catalog = tools.create_asset(
        "RetainedCityAssetCatalog", "/Game/City/Profiles", catalog_class, factory
    )
    if not catalog or _asset_path(catalog) != CATALOG_ASSET:
        raise RuntimeError(f"Unreal failed to create catalog data asset at {CATALOG_ASSET}")

    rows = []
    for spec, mesh, material in resolved:
        style = styles_class()
        style.set_editor_property("zone_type", unreal.Name(spec["zone_type"]))
        style.set_editor_property("kind", unreal.Name(spec["kind"]))
        # Reflected soft object properties accept an asset reference. Keep the loaded
        # objects alive until the catalog is saved so Unreal can serialize soft paths.
        style.set_editor_property("mesh", mesh)
        style.set_editor_property("material_override", material)
        style.set_editor_property("max_footprint_diameter_meters", spec["footprint"])
        style.set_editor_property("min_height_meters", spec["height"][0])
        style.set_editor_property("max_height_meters", spec["height"][1])
        style.set_editor_property("end_cull_distance_meters", spec["cull"])
        style.set_editor_property("asset_source", "Unreal Engine built-in geometry")
        style.set_editor_property("license", "Epic Engine content")
        rows.append(style)

    catalog.set_editor_property("styles", rows)
    if not unreal.EditorAssetLibrary.save_loaded_asset(catalog):
        raise RuntimeError(f"Unreal failed to save catalog asset: {CATALOG_ASSET}")
    catalog_path = _asset_path(catalog)
    if catalog_path != CATALOG_ASSET or len(catalog.get_editor_property("styles")) != len(
        STYLE_SPECS
    ):
        raise RuntimeError("saved city catalog failed path/style-count readback")
    return catalog, _validate_catalog(catalog)


def _check_build_result(value: Any) -> tuple[bool, str]:
    if isinstance(value, tuple):
        bools = [item for item in value if isinstance(item, bool)]
        errors = [item for item in value if isinstance(item, str) and item]
        return any(bools), "; ".join(errors)
    if isinstance(value, bool):
        return value, ""
    return bool(value), str(value) if isinstance(value, str) else ""


def _spawn_hero_camera(actors: Any, origin: dict[str, float]) -> dict[str, Any]:
    junction_x_m = 1011.0
    junction_y_m = 7502.0
    target = unreal.Vector(
        (junction_x_m - origin["x"]) * CENTIMETERS_PER_METER,
        (junction_y_m - origin["y"]) * CENTIMETERS_PER_METER,
        1000.0,
    )
    location = unreal.Vector(
        target.x - 120.0 * CENTIMETERS_PER_METER,
        target.y - 140.0 * CENTIMETERS_PER_METER,
        80.0 * CENTIMETERS_PER_METER,
    )
    rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
    camera = actors.spawn_actor_from_class(unreal.CameraActor, location, rotation)
    if not camera:
        raise RuntimeError("Unreal failed to spawn hero corner camera")
    camera.set_actor_label(HERO_CAMERA_LABEL)
    camera.camera_component.set_field_of_view(64.0)
    return {
        "actor_label": HERO_CAMERA_LABEL,
        "junction_sumo_xy_meters": [junction_x_m, junction_y_m],
        "location_unreal_cm": [location.x, location.y, location.z],
        "target_unreal_cm": [target.x, target.y, target.z],
        "rotation_degrees": [rotation.roll, rotation.pitch, rotation.yaw],
        "field_of_view_degrees": 64.0,
        "placement_note": "120 m west, 140 m south, 80 m high of the retained SUMO junction",
    }


def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def _prepare_phase(
    source_file: Path,
    styled_file: Path,
    catalog_file: Path,
    state_path: Path,
    report_path: Path,
    placements_path: Path,
    geometry_path: Path,
    placements: dict[str, Any],
    placement_counts: Counter,
    catalog_class: Any,
    styles_class: Any,
    source_sha_before: str,
) -> dict[str, Any]:
    if not source_file.is_file() or not unreal.EditorAssetLibrary.does_asset_exist(
        SOURCE_LEVEL_ASSET
    ):
        raise FileNotFoundError(f"retained source tiled level is missing: {SOURCE_LEVEL_ASSET}")
    if unreal.EditorAssetLibrary.does_asset_exist(STYLED_LEVEL_ASSET) or styled_file.exists():
        raise FileExistsError(f"refusing to overwrite existing styled level: {STYLED_LEVEL_ASSET}")
    if state_path.exists() or report_path.exists():
        raise FileExistsError(
            f"refusing to overwrite existing bootstrap state/report: {state_path}"
        )

    catalog_in_registry = unreal.EditorAssetLibrary.does_asset_exist(CATALOG_ASSET)
    catalog_on_disk = catalog_file.exists()
    catalog_exists = catalog_in_registry or catalog_on_disk
    resume_catalog = os.environ.get("AIQ_CITY_RESUME_CATALOG", "0") == "1"
    if catalog_exists and not (catalog_in_registry and catalog_on_disk and resume_catalog):
        raise FileExistsError(
            f"refusing to overwrite existing catalog asset: {CATALOG_ASSET}; "
            "set AIQ_CITY_RESUME_CATALOG=1 only to validate and reuse a known partial bootstrap catalog"
        )

    locks: list[Path] = []
    try:
        locks.append(_reserve(styled_file, "prepared styled level"))
        locks.append(_reserve(state_path, "prepare state"))
        if not catalog_exists:
            locks.append(_reserve(catalog_file, "new catalog"))

        if catalog_exists:
            catalog = unreal.load_asset(CATALOG_ASSET)
            qa_styles = _validate_catalog(catalog)
            catalog_action = "validated_and_reused_existing_partial_catalog"
        else:
            catalog, qa_styles = _create_catalog(catalog_class, styles_class)
            catalog_action = "created"

        source_level = unreal.load_asset(SOURCE_LEVEL_ASSET)
        if not source_level:
            raise RuntimeError(f"could not load source tiled level: {SOURCE_LEVEL_ASSET}")
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        styled_asset = asset_tools.duplicate_asset(
            "District7_Styled", "/Game/City/District7_Styled", source_level
        )
        if not styled_asset or _asset_path(styled_asset) != STYLED_LEVEL_ASSET:
            raise RuntimeError(f"Unreal failed to duplicate source level to {STYLED_LEVEL_ASSET}")
        save_result = unreal.EditorAssetLibrary.save_loaded_asset(styled_asset)
        if save_result is False or not styled_file.is_file():
            raise RuntimeError(f"Unreal did not save the duplicated level package: {styled_file}")

        # This process stops after preparing and saving the world package. The
        # populate phase starts a fresh editor process and loads it by package path.
        del styled_asset
        del source_level
        del asset_tools
        gc.collect()
        source_sha_after = _sha256(source_file)
        if source_sha_after != source_sha_before:
            raise RuntimeError("source tiled level changed while creating the styled duplicate")

        prepare_state = {
            "schema_version": "styled_city_prepare.v1",
            "status": "prepared",
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "source_level_asset": SOURCE_LEVEL_ASSET,
            "source_level_sha256": source_sha_after,
            "styled_level_asset": STYLED_LEVEL_ASSET,
            "styled_level_file": str(styled_file.resolve()),
            "styled_level_file_sha256": _sha256(styled_file),
            "styled_level_size_bytes": styled_file.stat().st_size,
            "catalog_asset": CATALOG_ASSET,
            "catalog_action": catalog_action,
            "catalog_file": str(catalog_file.resolve()),
            "catalog_file_sha256": _sha256(catalog_file),
            "catalog_style_count": len(qa_styles),
            "styles": qa_styles,
            "placement_manifest_file": str(placements_path),
            "placement_manifest_file_sha256": _sha256(placements_path),
            "geometry_manifest_file": str(geometry_path),
            "source_net_sha256": placements["source_net_sha256"],
            "source_overlay_sha256": placements["source_overlay_sha256"],
            "placement_profile_sha256": placements.get("placement_profile_sha256"),
            "local_origin_meters": placements["local_origin"],
            "manifest_zone_kind_counts": {
                f"{zone}:{kind}": count for (zone, kind), count in sorted(placement_counts.items())
            },
            "claim": "Prepared duplicate only; no visual actor or traffic demand has been added in this phase.",
        }
        _write_json_new(state_path, prepare_state)
        unreal.log("STYLED_CITY_PREPARED " + json.dumps(prepare_state, sort_keys=True))
        return prepare_state
    finally:
        for lock in locks:
            try:
                lock.unlink(missing_ok=True)
            except OSError as exc:
                unreal.log_warning(f"Could not remove bootstrap reservation {lock}: {exc}")


def _validate_prepare_state(
    state_path: Path,
    source_file: Path,
    styled_file: Path,
    catalog_file: Path,
    placements_path: Path,
    geometry_path: Path,
    placements: dict[str, Any],
) -> dict[str, Any]:
    if not state_path.is_file():
        raise FileNotFoundError(f"prepare phase state is missing: {state_path}")
    if not source_file.is_file() or not styled_file.is_file() or not catalog_file.is_file():
        raise FileNotFoundError(
            "prepare phase did not leave the required source, level, and catalog files"
        )
    state = _load_json(state_path, "prepare phase state")
    if state.get("schema_version") != "styled_city_prepare.v1" or state.get("status") != "prepared":
        raise ValueError("prepare phase state is invalid")
    expected_paths = {
        "source_level_asset": SOURCE_LEVEL_ASSET,
        "styled_level_asset": STYLED_LEVEL_ASSET,
        "catalog_asset": CATALOG_ASSET,
    }
    for key, expected in expected_paths.items():
        if state.get(key) != expected:
            raise ValueError(f"prepare phase state {key} does not match this bootstrap")
    expected_hashes = {
        "source_level_sha256": _sha256(source_file),
        "styled_level_file_sha256": _sha256(styled_file),
        "catalog_file_sha256": _sha256(catalog_file),
        "placement_manifest_file_sha256": _sha256(placements_path),
        "source_net_sha256": placements["source_net_sha256"],
        "source_overlay_sha256": placements["source_overlay_sha256"],
        "placement_profile_sha256": placements.get("placement_profile_sha256"),
    }
    for key, actual in expected_hashes.items():
        if state.get(key) != actual:
            raise ValueError(f"prepared bootstrap input/output changed since phase one: {key}")
    if state.get("catalog_style_count") != len(STYLE_SPECS):
        raise ValueError("prepared catalog style count differs from this bootstrap")
    return state


def _populate_phase(
    source_file: Path,
    styled_file: Path,
    catalog_file: Path,
    state_path: Path,
    report_path: Path,
    placements_path: Path,
    geometry_path: Path,
    placements: dict[str, Any],
    placement_counts: Counter,
) -> dict[str, Any]:
    if report_path.exists():
        raise FileExistsError(f"refusing to overwrite existing QA report: {report_path}")
    if not unreal.EditorAssetLibrary.does_asset_exist(STYLED_LEVEL_ASSET):
        raise FileNotFoundError(
            f"prepared styled level asset is not registered: {STYLED_LEVEL_ASSET}"
        )
    if not unreal.EditorAssetLibrary.does_asset_exist(CATALOG_ASSET):
        raise FileNotFoundError(f"prepared city catalog is not registered: {CATALOG_ASSET}")
    prepare_state = _validate_prepare_state(
        state_path,
        source_file,
        styled_file,
        catalog_file,
        placements_path,
        geometry_path,
        placements,
    )
    catalog = unreal.load_asset(CATALOG_ASSET)
    qa_styles = _validate_catalog(catalog)
    locks: list[Path] = []
    try:
        locks.append(_reserve(report_path, "final QA report"))
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if not levels or not editor or not actors:
            raise RuntimeError("Unreal level, editor, or actor subsystem is unavailable")
        # This must run in the fresh second process. Do not load the UWorld asset
        # with unreal.load_asset before this call.
        if not levels.load_level(STYLED_LEVEL_ASSET):
            raise RuntimeError(f"Unreal failed to load prepared level: {STYLED_LEVEL_ASSET}")
        world = editor.get_editor_world()
        if not world:
            raise RuntimeError("Unreal editor world is unavailable after loading the styled level")

        existing_labels = {actor.get_actor_label() for actor in actors.get_all_level_actors()}
        for reserved_label in ("Retained City Illustrative Visuals", HERO_CAMERA_LABEL):
            if reserved_label in existing_labels:
                raise RuntimeError(
                    f"prepared level unexpectedly already has actor {reserved_label!r}"
                )

        visual_class = unreal.load_class(
            None, "/Script/TrafficRenderRuntime.TrafficCityVisualActor"
        )
        if not visual_class:
            raise RuntimeError("TrafficCityVisualActor class is not loaded")
        geometry_class = unreal.load_class(
            None, "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
        )
        if not geometry_class:
            raise RuntimeError("TrafficSumoGeometryActor class is not loaded")
        road_actors = [
            actor
            for actor in actors.get_all_level_actors()
            if actor.get_class().get_path_name()
            == "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
        ]
        if len(road_actors) != 1:
            raise RuntimeError(
                f"expected one retained SUMO geometry actor, found {len(road_actors)}"
            )
        road_actors[0].set_editor_property("geometry_manifest_path", REL_GEOMETRY_MANIFEST)

        visual_actor = actors.spawn_actor_from_class(
            visual_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0)
        )
        if not visual_actor:
            raise RuntimeError("Unreal failed to spawn TrafficCityVisualActor")
        visual_actor.set_actor_label("Retained City Illustrative Visuals")
        visual_actor.set_editor_property("asset_catalog", catalog)
        visual_actor.set_editor_property("placement_manifest_path", REL_PLACEMENT_MANIFEST)
        visual_actor.set_editor_property("expected_net_sha256", placements["source_net_sha256"])
        visual_actor.set_editor_property(
            "expected_overlay_sha256", placements["source_overlay_sha256"]
        )

        build_result = visual_actor.build_from_placement_manifest(str(placements_path))
        build_succeeded, build_error = _check_build_result(build_result)
        unreal.log(f"CITY_VISUAL_BUILD_RETURN {build_result!r}")
        summary_text = visual_actor.get_build_summary_json()
        if not isinstance(summary_text, str):
            raise RuntimeError("city visual actor returned no build summary")
        summary = json.loads(summary_text)
        actual_counts = {
            "building": int(summary.get("rendered_building_count", 0)),
            "landscape": int(summary.get("rendered_landscape_count", 0)),
            "active_style": int(summary.get("rendered_style_count", 0)),
        }
        expected_counts = {
            "building": EXPECTED_BUILDINGS,
            "landscape": EXPECTED_LANDSCAPE,
            "active_style": EXPECTED_ACTIVE_STYLES,
        }
        if actual_counts != expected_counts:
            raise RuntimeError(
                "city visual actor did not build the sourced retained manifest: "
                f"return={build_result!r}, error={build_error!r}, counts={actual_counts}"
            )
        if not build_succeeded:
            if build_error:
                raise RuntimeError(f"city visual actor reported an error: {build_error}")
            unreal.log_warning(
                "City visual build binding returned falsy with no OutError, but native counters "
                f"confirm all expected instances: {actual_counts}"
            )

        hero_camera = _spawn_hero_camera(actors, placements["local_origin"])
        save_result = levels.save_current_level()
        if save_result is False or not styled_file.is_file():
            raise RuntimeError(f"Unreal did not save the populated level package: {styled_file}")

        level_actors = actors.get_all_level_actors()
        visual_catalog_path = _asset_path(visual_actor.get_editor_property("asset_catalog"))
        if visual_catalog_path != CATALOG_ASSET:
            raise RuntimeError(
                f"visual actor did not retain catalog reference: {visual_catalog_path!r}"
            )
        source_sha_after = _sha256(source_file)
        if source_sha_after != prepare_state["source_level_sha256"]:
            raise RuntimeError("source tiled level changed while creating the styled duplicate")

        lod_counts = [style["mesh_lod_count"] for style in qa_styles]
        all_lod_counts_known = all(isinstance(count, int) and count > 0 for count in lod_counts)
        if all_lod_counts_known and all(count == 1 for count in lod_counts):
            lod_assessment = "The placeholder Cube/Sphere meshes expose only LOD0; multi-LOD meshes are not configured yet. HISM instance culling is configured per style."
        elif not all_lod_counts_known:
            lod_assessment = "Unreal Python did not report every mesh LOD count; HISM instance culling is configured per style."
        else:
            lod_assessment = (
                "Mesh LOD counts were recorded; HISM instance culling is configured per style."
            )

        report = {
            "schema_version": "styled_city_bootstrap.v1",
            "status": "created",
            "scope": "illustrative semantic building placements; placeholder geometry; no traffic demand or vehicle replay",
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "source_level_asset": SOURCE_LEVEL_ASSET,
            "source_level_sha256_before_and_after": source_sha_after,
            "source_level_preserved": True,
            "styled_level_asset": STYLED_LEVEL_ASSET,
            "styled_level_file": str(styled_file.resolve()),
            "styled_level_size_bytes": styled_file.stat().st_size,
            "prepared_level_sha256": prepare_state["styled_level_file_sha256"],
            "catalog_asset": CATALOG_ASSET,
            "catalog_style_count": len(qa_styles),
            "placement_manifest_file": str(placements_path),
            "placement_manifest_file_sha256": _sha256(placements_path),
            "placement_profile_sha256": placements.get("placement_profile_sha256"),
            "geometry_manifest_file": str(geometry_path),
            "geometry_manifest_file_sha256": _sha256(geometry_path),
            "source_net_sha256": placements["source_net_sha256"],
            "source_overlay_sha256": placements["source_overlay_sha256"],
            "local_origin_meters": placements["local_origin"],
            "manifest_zone_kind_counts": {
                f"{zone}:{kind}": count for (zone, kind), count in sorted(placement_counts.items())
            },
            "omitted_unsourced_neutral_sites": placements.get("skipped_by_reason", {}).get(
                "neutral_visual_omitted", 0
            ),
            "neutral_semantics": "Unclassified neutral overlay fragments are omitted; the catalog placeholder does not imply mapped vegetation.",
            "rendered_counts": actual_counts,
            "visual_actor": {
                "label": visual_actor.get_actor_label(),
                "class": visual_actor.get_class().get_path_name(),
                "catalog_asset": visual_catalog_path,
            },
            "saved_manifest_paths": {
                "road_geometry_actor": REL_GEOMETRY_MANIFEST,
                "city_visual_actor": REL_PLACEMENT_MANIFEST,
            },
            "hero_camera": hero_camera,
            "actors": {
                "total_count": len(level_actors),
                "labels": sorted(actor.get_actor_label() for actor in level_actors),
            },
            "styles": qa_styles,
            "lod_and_culling": {
                "mechanism": "UHierarchicalInstancedStaticMeshComponent instances with per-style EndCullDistanceMeters",
                "mesh_lod_assessment": lod_assessment,
                "multi_lod_meshes_configured": any(count and count > 1 for count in lod_counts),
                "fps_target_verified": False,
            },
            "claim": "Styled level is a visual map bootstrap only. Built-in Cube/Sphere assets are placeholders; render performance and final art quality require review and benchmarking.",
        }
        _write_json_new(report_path, report)
        unreal.log("STYLED_CITY_BOOTSTRAP_QA " + json.dumps(report, sort_keys=True))
        return report
    finally:
        for lock in locks:
            try:
                lock.unlink(missing_ok=True)
            except OSError as exc:
                unreal.log_warning(f"Could not remove bootstrap reservation {lock}: {exc}")


def run() -> dict[str, Any]:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise RuntimeError(f"wrong Unreal project loaded: {project_dir}; expected {PROJECT_ROOT}")
    phase = os.environ.get("AIQ_CITY_BOOTSTRAP_PHASE", "prepare").strip().lower()
    if phase not in {"prepare", "populate"}:
        raise ValueError("AIQ_CITY_BOOTSTRAP_PHASE must be 'prepare' or 'populate'")

    content_dir = Path(unreal.Paths.project_content_dir()).resolve()
    source_file = _level_file(SOURCE_LEVEL_ASSET, content_dir)
    styled_file = _level_file(STYLED_LEVEL_ASSET, content_dir)
    catalog_file = _catalog_file(CATALOG_ASSET, content_dir)
    placements_path = _env_path("AIQ_CITY_PLACEMENTS_MANIFEST", PLACEMENT_MANIFEST)
    geometry_path = _env_path("AIQ_CITY_GEOMETRY_MANIFEST", GEOMETRY_MANIFEST)
    report_path = _env_path("AIQ_CITY_BOOTSTRAP_REPORT_PATH", REPORT_PATH)
    state_path = _env_path("AIQ_CITY_BOOTSTRAP_STATE_PATH", PREPARE_STATE_PATH)
    placements, geometry, placement_counts = _validate_manifests(placements_path, geometry_path)
    catalog_class = unreal.load_class(None, "/Script/TrafficRenderRuntime.TrafficCityAssetCatalog")
    styles_class = getattr(unreal, "TrafficCityVisualStyle", None)
    if not catalog_class or not styles_class:
        raise RuntimeError(
            "TrafficCityAssetCatalog or TrafficCityVisualStyle is not reflected in Unreal Python"
        )

    if phase == "prepare":
        if not source_file.is_file():
            raise FileNotFoundError(f"retained source tiled level is missing: {source_file}")
        return _prepare_phase(
            source_file,
            styled_file,
            catalog_file,
            state_path,
            report_path,
            placements_path,
            geometry_path,
            placements,
            placement_counts,
            catalog_class,
            styles_class,
            _sha256(source_file),
        )

    return _populate_phase(
        source_file,
        styled_file,
        catalog_file,
        state_path,
        report_path,
        placements_path,
        geometry_path,
        placements,
        placement_counts,
    )


try:
    RESULT = run()
    print("STYLED_CITY_BOOTSTRAP_RESULT " + json.dumps(RESULT, indent=2, sort_keys=True))
except Exception as exc:
    unreal.log_error(f"STYLED_CITY_BOOTSTRAP_FAILED {type(exc).__name__}: {exc}")
    raise
