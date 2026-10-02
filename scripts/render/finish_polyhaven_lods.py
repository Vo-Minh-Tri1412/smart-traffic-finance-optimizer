"""Add real LODs to selected imported Poly Haven facade modules only.

Run in a fresh UE 5.8 command process. The first LOD target is the large window
module; the script stops there if reduction or vertex-count verification fails.
No levels, catalogs, materials, or textures are modified.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
MANIFEST_PATH = (
    ROOT / "artifacts" / "city_assets" / "polyhaven" / "manifest.v1-4a6a6d12b0df21cd.json"
)
EXPECTED_MANIFEST_SHA256 = "1637a8a2bffe836967e623a0e7f2886e5b07e1a3fc3c74eaec5a62a6624c972b"
IMPORT_QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_import_qa.json"
INSPECT_QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_asset_inspect_qa.json"
QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_lod_qa.json"
BASE_PATH = "/Game/City/Assets/PolyHaven"
URBAN_PATH = BASE_PATH + "/UrbanFacade/modular_urban_apartments_facade_2k"
MESH_PATH = URBAN_PATH + "/StaticMeshes"
SURFACE_PATH = BASE_PATH + "/Surfaces"
MATERIAL_PATH = BASE_PATH + "/Materials"

LOD_TARGETS = (
    {"name": "window_centered_double_01", "role": "large_window", "lod0_vertices": 1390},
    {"name": "door_window_small_04", "role": "door_window_module", "lod0_vertices": 1384},
    {"name": "window_centered_large_01", "role": "large_window", "lod0_vertices": 1265},
)
LOW_POLY_WALLS = (
    {"name": "wall_standard_standard_01", "lod0_vertices": 144},
    {"name": "wall_window_centered_double_01", "lod0_vertices": 166},
)


class LodRecoveryError(RuntimeError):
    """Imported source, PBR preflight, or LOD readback failed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_qa(payload: dict[str, Any]) -> None:
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with QA_PATH.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def _package_path(asset: Any) -> str:
    return asset.get_path_name().split(".", 1)[0] if asset else ""


def _asset(asset_path: str, expected_class: Any) -> Any:
    value = unreal.load_asset(asset_path)
    if not value:
        raise LodRecoveryError(f"required imported UE asset is missing: {asset_path}")
    if not isinstance(value, expected_class):
        raise LodRecoveryError(
            f"imported asset has wrong class: {asset_path} -> {value.get_class().get_path_name()}"
        )
    return value


def _lod_count(mesh: Any) -> int:
    count = int(unreal.EditorStaticMeshLibrary.get_lod_count(mesh))
    if count < 0:
        raise LodRecoveryError(f"could not read LOD count for {_package_path(mesh)}")
    return count


def _vertex_count(mesh: Any, lod_index: int) -> int:
    count = int(unreal.EditorStaticMeshLibrary.get_number_verts(mesh, lod_index))
    if count < 0:
        raise LodRecoveryError(
            f"could not read LOD{lod_index} vertex count for {_package_path(mesh)}"
        )
    return count


def _material_slots(mesh: Any) -> list[dict[str, Any]]:
    slots = []
    for index, slot in enumerate(mesh.get_editor_property("static_materials")):
        material = slot.get_editor_property("material_interface")
        slots.append(
            {
                "index": index,
                "slot_name": str(slot.get_editor_property("material_slot_name")),
                "material_asset": _package_path(material),
                "assigned": bool(material),
            }
        )
    return slots


def _bounds_and_pivot(mesh: Any) -> dict[str, Any]:
    bounds = mesh.get_bounds()
    origin = bounds.origin
    extent = bounds.box_extent
    return {
        "space": "StaticMesh local space, Unreal centimeters",
        "asset_pivot_cm": [0.0, 0.0, 0.0],
        "bounds_center_relative_to_pivot_cm": [origin.x, origin.y, origin.z],
        "bounds_extent_cm": [extent.x, extent.y, extent.z],
        "bounds_size_cm": [extent.x * 2.0, extent.y * 2.0, extent.z * 2.0],
        "sphere_radius_cm": bounds.sphere_radius,
    }


def _verify_manifest_and_pbr() -> dict[str, Any]:
    actual_manifest_hash = _sha256(MANIFEST_PATH)
    if actual_manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise LodRecoveryError(
            "Poly Haven source manifest SHA-256 changed: "
            f"{actual_manifest_hash} != {EXPECTED_MANIFEST_SHA256}"
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "polyhaven_city_assets.v1":
        raise LodRecoveryError("Poly Haven source manifest schema changed")
    if manifest.get("license") != "CC0 1.0 Universal":
        raise LodRecoveryError("Poly Haven source manifest no longer records CC0")
    expected_assets = {
        "modular_urban_apartments_facade": ("model", "2k"),
        "clean_asphalt": ("texture", "2k"),
        "concrete_pavement_03": ("texture", "2k"),
    }
    actual_assets = {
        row.get("id"): (row.get("type"), row.get("resolution"))
        for row in manifest.get("assets", [])
        if isinstance(row, dict)
    }
    if actual_assets != expected_assets:
        raise LodRecoveryError(f"Poly Haven manifest selections changed: {actual_assets}")

    texture_specs = (
        ("clean_asphalt_diff_2k", True, unreal.TextureCompressionSettings.TC_DEFAULT),
        ("clean_asphalt_nor_dx_2k", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
        ("clean_asphalt_arm_2k", False, unreal.TextureCompressionSettings.TC_MASKS),
        ("concrete_pavement_03_diff_2k", True, unreal.TextureCompressionSettings.TC_DEFAULT),
        ("concrete_pavement_03_nor_dx_2k", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
        ("concrete_pavement_03_arm_2k", False, unreal.TextureCompressionSettings.TC_MASKS),
    )
    textures = []
    texture_paths: dict[str, set[str]] = {"clean_asphalt": set(), "concrete_pavement_03": set()}
    for texture_name, expected_srgb, expected_compression in texture_specs:
        texture = _asset(SURFACE_PATH + "/" + texture_name, unreal.Texture2D)
        srgb = bool(texture.get_editor_property("srgb"))
        compression = texture.get_editor_property("compression_settings")
        if srgb != expected_srgb or compression != expected_compression:
            raise LodRecoveryError(
                f"texture settings changed for {_package_path(texture)}: "
                f"sRGB={srgb}, compression={compression}"
            )
        path = _package_path(texture)
        asset_id = (
            "clean_asphalt" if texture_name.startswith("clean_asphalt") else "concrete_pavement_03"
        )
        texture_paths[asset_id].add(path)
        textures.append(
            {
                "asset": path,
                "srgb": srgb,
                "compression_settings": str(compression),
            }
        )

    materials = []
    for asset_id, material_name in (
        ("clean_asphalt", "M_CityAsphalt2K"),
        ("concrete_pavement_03", "M_CityPavement2K"),
    ):
        material = _asset(MATERIAL_PATH + "/" + material_name, unreal.Material)
        expected_paths = texture_paths[asset_id]
        try:
            used = unreal.MaterialEditingLibrary.get_material_used_textures(material)
            used_paths = sorted(_package_path(texture) for texture in used if texture)
            readback_matches = set(used_paths) == expected_paths
            readback_error = (
                ""
                if readback_matches
                else "material texture readback differs from imported surface set"
            )
        except Exception as exc:
            used_paths = []
            readback_matches = False
            readback_error = f"{type(exc).__name__}: {exc}"
        materials.append(
            {
                "asset": _package_path(material),
                "class": material.get_class().get_path_name(),
                "used_texture_assets": used_paths,
                "expected_texture_assets": sorted(expected_paths),
                "used_texture_set_matches": readback_matches,
                "readback_error": readback_error,
                "note": (
                    "Material packages are present; graph readback is recorded without "
                    "blocking LOD recovery."
                ),
            }
        )

    return {
        "source_manifest": str(MANIFEST_PATH),
        "source_manifest_sha256": actual_manifest_hash,
        "source_license": manifest["license"],
        "source_license_url": manifest.get("license_url"),
        "api_credit_required": manifest.get("api_credit_required"),
        "surface_textures": textures,
        "pbr_materials": materials,
    }


def _mesh_record(mesh: Any, role: str, expected_lod0_vertices: int) -> dict[str, Any]:
    path = _package_path(mesh)
    count = _lod_count(mesh)
    vertices = [_vertex_count(mesh, index) for index in range(count)]
    if vertices[0] != expected_lod0_vertices:
        raise LodRecoveryError(
            f"unexpected imported LOD0 vertex count for {path}: "
            f"{vertices[0]} != {expected_lod0_vertices}"
        )
    materials = _material_slots(mesh)
    if not materials or any(not row["assigned"] for row in materials):
        raise LodRecoveryError(f"imported material slots are missing for {path}: {materials}")
    return {
        "asset_path": path,
        "name": mesh.get_name(),
        "semantic_role": role,
        "vertices_by_lod": vertices,
        "lod_count": count,
        "material_slots_before": materials,
        "bounds_and_pivot": _bounds_and_pivot(mesh),
    }


def _generate_lods(mesh: Any, material_slots_before: list[dict[str, Any]]) -> dict[str, Any]:
    options = unreal.EditorScriptingMeshReductionOptions()
    settings = unreal.EditorScriptingMeshReductionSettings
    options.set_editor_property(
        "reduction_settings",
        [settings(1.0, 1.0), settings(0.5, 0.5), settings(0.25, 0.25)],
    )
    options.set_editor_property("auto_compute_lod_screen_size", False)
    result = unreal.EditorStaticMeshLibrary.set_lods(mesh, options)
    lod_count = _lod_count(mesh)
    if lod_count < 3:
        raise LodRecoveryError(
            f"set_lods returned {result!r}; {_package_path(mesh)} has {lod_count} LODs"
        )
    vertices = [_vertex_count(mesh, index) for index in range(3)]
    if not (vertices[0] > vertices[1] > vertices[2] > 0):
        raise LodRecoveryError(f"LOD vertices do not decline for {_package_path(mesh)}: {vertices}")
    material_slots_after = _material_slots(mesh)
    if material_slots_after != material_slots_before:
        raise LodRecoveryError(
            f"LOD generation changed material slots for {_package_path(mesh)}: "
            f"before={material_slots_before}, after={material_slots_after}"
        )
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh):
        raise LodRecoveryError(f"failed to save LOD changes for {_package_path(mesh)}")
    return {
        "set_lods_return": result,
        "lod_count": lod_count,
        "vertices_lod0_lod1_lod2": vertices,
        "screen_size_thresholds": [1.0, 0.5, 0.25],
        "triangle_retention": [1.0, 0.5, 0.25],
        "material_slots_after": material_slots_after,
        "material_slots_unchanged": True,
    }


def _run_recovery(qa: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise LodRecoveryError(
            f"wrong Unreal project loaded: {project_dir}; expected {PROJECT_ROOT}"
        )
    if QA_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing LOD QA: {QA_PATH}")

    qa.update(_verify_manifest_and_pbr())
    mesh_registry_paths = unreal.EditorAssetLibrary.list_assets(
        MESH_PATH, recursive=False, include_folder=False
    )
    static_meshes = [
        obj
        for obj in (unreal.load_asset(path) for path in mesh_registry_paths)
        if isinstance(obj, unreal.StaticMesh)
    ]
    if len(static_meshes) != 147:
        raise LodRecoveryError(
            f"imported facade StaticMesh count changed: expected 147, found {len(static_meshes)}"
        )
    qa["imported_asset_counts_before_after"] = {
        "urban_facade_assets_before": len(
            unreal.EditorAssetLibrary.list_assets(URBAN_PATH, recursive=True, include_folder=False)
        ),
        "facade_static_meshes_before": len(static_meshes),
        "facade_static_meshes_after": None,
        "surfaces_before": len(
            unreal.EditorAssetLibrary.list_assets(
                SURFACE_PATH, recursive=False, include_folder=False
            )
        ),
        "materials_before": len(
            unreal.EditorAssetLibrary.list_assets(
                MATERIAL_PATH, recursive=False, include_folder=False
            )
        ),
        "total_polyhaven_assets_before": len(
            unreal.EditorAssetLibrary.list_assets(BASE_PATH, recursive=True, include_folder=False)
        ),
    }

    for wall in LOW_POLY_WALLS:
        mesh = _asset(MESH_PATH + "/" + wall["name"], unreal.StaticMesh)
        count = _lod_count(mesh)
        vertices = [_vertex_count(mesh, lod_index) for lod_index in range(count)]
        if vertices != [wall["lod0_vertices"]]:
            raise LodRecoveryError(
                f"low-poly wall module changed unexpectedly: {wall['name']} vertices={vertices}"
            )
        wall["asset_path"] = _package_path(mesh)
        wall["lod_count"] = count
        wall["vertices_by_lod"] = vertices
        wall["bounds_and_pivot"] = _bounds_and_pivot(mesh)
        wall["policy"] = (
            "LOD0 only; low vertex count is more appropriate with HISM/distance culling."
        )
        wall["material_slots"] = _material_slots(mesh)
    qa["low_poly_wall_modules"] = [dict(row) for row in LOW_POLY_WALLS]

    target_records = []
    for spec in LOD_TARGETS:
        mesh_path = MESH_PATH + "/" + spec["name"]
        mesh = _asset(mesh_path, unreal.StaticMesh)
        record = _mesh_record(mesh, spec["role"], spec["lod0_vertices"])
        if record["lod_count"] not in {1, 3}:
            raise LodRecoveryError(
                f"partial LOD state for {_package_path(mesh)}: "
                f"LOD count {record['lod_count']}; refusing to replace existing LODs"
            )
        if record["lod_count"] == 3:
            current_vertices = record["vertices_by_lod"][:3]
            if not (current_vertices[0] > current_vertices[1] > current_vertices[2] > 0):
                raise LodRecoveryError(
                    f"existing LODs are not progressively reduced for {_package_path(mesh)}: "
                    f"{current_vertices}"
                )
        target_records.append((spec, mesh, record))

    lod_rows = []
    for index, (_spec, mesh, record) in enumerate(target_records):
        if record["lod_count"] == 1:
            if index == 0:
                # First target is intentionally a quick gate before touching the others.
                unreal.log(
                    f"POLYHAVEN_LOD_FIRST_TARGET {_package_path(mesh)} "
                    f"LOD0 vertices={record['vertices_by_lod'][0]}"
                )
            recovery = _generate_lods(mesh, record["material_slots_before"])
            record.update(recovery)
            record["status"] = "generated_and_verified"
        elif record["lod_count"] == 3:
            current_vertices = record["vertices_by_lod"][:3]
            record["vertices_lod0_lod1_lod2"] = current_vertices
            record["material_slots_after"] = record["material_slots_before"]
            record["material_slots_unchanged"] = True
            record["status"] = "existing_lods_verified"
        lod_rows.append(record)
        qa["lod_meshes"] = list(lod_rows)
        # Persist and log the first window result before trying the two next modules.
        if index == 0:
            unreal.log("POLYHAVEN_LOD_FIRST_TARGET_COMPLETE " + json.dumps(record, sort_keys=True))

    qa["lod_meshes"] = lod_rows
    qa["imported_asset_counts_before_after"]["urban_facade_assets_after"] = len(
        unreal.EditorAssetLibrary.list_assets(URBAN_PATH, recursive=True, include_folder=False)
    )
    qa["imported_asset_counts_before_after"]["facade_static_meshes_after"] = len(
        unreal.EditorAssetLibrary.list_assets(MESH_PATH, recursive=False, include_folder=False)
    )
    qa["imported_asset_counts_before_after"]["total_polyhaven_assets_after"] = len(
        unreal.EditorAssetLibrary.list_assets(BASE_PATH, recursive=True, include_folder=False)
    )
    qa["wall_policy"] = (
        "No wall panel exceeded the 500-vertex target; retain these LOD0 meshes and use "
        "HISM/distance culling at placement time."
    )
    qa["scene_or_level_modified"] = False
    qa["catalog_modified"] = False
    qa["status"] = "success"
    return qa


def run() -> dict[str, Any]:
    qa: dict[str, Any] = {
        "schema_version": "polyhaven_lod_recovery_qa.v1",
        "status": "failed",
        "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
        "lod_meshes": [],
        "low_poly_wall_modules": [],
        "errors": [],
        "scene_or_level_modified": False,
        "catalog_modified": False,
    }
    if QA_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing LOD QA: {QA_PATH}")
    try:
        result = _run_recovery(qa)
        _write_qa(result)
        unreal.log("POLYHAVEN_LOD_RECOVERY_QA " + json.dumps(result, sort_keys=True))
        return result
    except Exception as exc:
        qa["errors"].append(f"{type(exc).__name__}: {exc}")
        with contextlib.suppress(OSError):
            qa["source_manifest_sha256"] = _sha256(MANIFEST_PATH)
        with contextlib.suppress(FileExistsError):
            _write_qa(qa)
        unreal.log_error("POLYHAVEN_LOD_RECOVERY_FAILED " + json.dumps(qa, sort_keys=True))
        raise


try:
    RESULT = run()
    print("POLYHAVEN_LOD_RECOVERY_RESULT " + json.dumps(RESULT, indent=2, sort_keys=True))
except Exception as exc:
    unreal.log_error(f"POLYHAVEN_LOD_RECOVERY_FATAL {type(exc).__name__}: {exc}")
    raise
