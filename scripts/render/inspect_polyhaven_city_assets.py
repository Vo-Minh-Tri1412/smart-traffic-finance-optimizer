"""Read back imported Poly Haven UE assets and report real mesh/texture state.

This script loads only assets in the new Poly Haven folders. It does not import,
save, modify, or load any level or catalog.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
MANIFEST_PATH = (
    ROOT / "artifacts" / "city_assets" / "polyhaven" / "manifest.v1-4a6a6d12b0df21cd.json"
)
IMPORT_QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_import_qa.json"
QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_asset_inspect_qa.v2.json"
BASE_PATH = "/Game/City/Assets/PolyHaven"
URBAN_PATH = BASE_PATH + "/UrbanFacade"
SURFACES_PATH = BASE_PATH + "/Surfaces"
MATERIALS_PATH = BASE_PATH + "/Materials"


def _asset_path(asset: Any) -> str:
    return asset.get_path_name() if asset else ""


def _load_objects(package_paths: Any) -> list[Any]:
    objects = []
    for package_path in package_paths:
        asset = unreal.load_asset(package_path)
        if asset:
            objects.append(asset)
    return objects


def _texture_path(expression: Any) -> str:
    try:
        texture = expression.get_editor_property("texture")
        return _asset_path(texture)
    except Exception:
        return ""


def _material_report(package_path: str) -> dict[str, Any]:
    material = unreal.load_asset(package_path)
    if not material:
        return {"asset": package_path, "present": False, "texture_samples": []}
    samples = []
    inspection_error = ""
    try:
        expressions = list(unreal.MaterialEditingLibrary.get_material_expressions(material))
        for expression in expressions:
            class_path = expression.get_class().get_path_name()
            if class_path.endswith("MaterialExpressionTextureSample"):
                samples.append(
                    {
                        "expression_class": class_path,
                        "texture_asset": _texture_path(expression),
                        "sampler_type": str(expression.get_editor_property("sampler_type")),
                    }
                )
    except Exception as exc:
        inspection_error = f"{type(exc).__name__}: {exc}"
    used_textures = []
    used_texture_error = ""
    try:
        used_textures = sorted(
            _asset_path(texture)
            for texture in unreal.MaterialEditingLibrary.get_material_used_textures(material)
            if texture
        )
    except Exception as exc:
        used_texture_error = f"{type(exc).__name__}: {exc}"
    property_inputs = []
    for property_name in (
        "MP_BASE_COLOR",
        "MP_NORMAL",
        "MP_AMBIENT_OCCLUSION",
        "MP_ROUGHNESS",
        "MP_METALLIC",
    ):
        try:
            property_value = getattr(unreal.MaterialProperty, property_name)
            node = unreal.MaterialEditingLibrary.get_material_property_input_node(
                material, property_value
            )
            output_name = (
                unreal.MaterialEditingLibrary.get_material_property_input_node_output_name(
                    material, property_value
                )
            )
            property_inputs.append(
                {
                    "property": property_name,
                    "input_node": _asset_path(node),
                    "input_node_class": node.get_class().get_path_name() if node else "",
                    "output_name": str(output_name),
                    "readable": bool(node),
                }
            )
        except Exception as exc:
            property_inputs.append(
                {
                    "property": property_name,
                    "readable": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "asset": _asset_path(material),
        "present": True,
        "class": material.get_class().get_path_name(),
        "texture_samples": samples,
        "inspection_error": inspection_error,
        "used_texture_assets": used_textures,
        "used_texture_error": used_texture_error,
        "property_inputs": property_inputs,
    }


def _texture_report(
    package_path: str, expected_srgb: bool, expected_compression: Any
) -> dict[str, Any]:
    texture = unreal.load_asset(package_path)
    if not texture:
        return {"asset": package_path, "present": False}
    srgb = bool(texture.get_editor_property("srgb"))
    compression = texture.get_editor_property("compression_settings")
    return {
        "asset": _asset_path(texture),
        "present": True,
        "class": texture.get_class().get_path_name(),
        "srgb": srgb,
        "compression_settings": str(compression),
        "settings_match_expected": srgb == expected_srgb and compression == expected_compression,
    }


def _inspect_meshes(package_paths: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meshes = [obj for obj in _load_objects(package_paths) if isinstance(obj, unreal.StaticMesh)]
    rows = []
    category_counts = Counter()
    for mesh in sorted(meshes, key=lambda item: item.get_path_name()):
        name = mesh.get_name()
        try:
            lod_count = int(unreal.EditorStaticMeshLibrary.get_lod_count(mesh))
            vertices = [
                int(unreal.EditorStaticMeshLibrary.get_number_verts(mesh, lod_index))
                for lod_index in range(max(1, lod_count))
            ]
        except Exception as exc:
            lod_count = None
            vertices = []
            lod_error = f"{type(exc).__name__}: {exc}"
        else:
            lod_error = ""
        name_lower = name.lower()
        categories = [word for word in ("wall", "window", "door") if word in name_lower]
        for category in categories:
            category_counts[category] += 1
        try:
            static_materials = list(mesh.get_editor_property("static_materials"))
            material_slots = [
                {
                    "slot_name": str(slot.get_editor_property("material_slot_name")),
                    "material_asset": _asset_path(slot.get_editor_property("material_interface")),
                    "assigned": bool(slot.get_editor_property("material_interface")),
                }
                for slot in static_materials
            ]
        except Exception as exc:
            material_slots = []
            lod_error = "; ".join(
                part for part in (lod_error, f"material_slots: {type(exc).__name__}: {exc}") if part
            )
        rows.append(
            {
                "asset_path": mesh.get_path_name(),
                "name": name,
                "semantic_name_matches": categories,
                "lod_count": lod_count,
                "vertices_by_lod": vertices,
                "lod0_vertices_over_500": bool(vertices and vertices[0] > 500),
                "material_slot_count": len(material_slots),
                "material_slots": material_slots,
                "inspection_error": lod_error,
            }
        )

    named_counts = {
        category: {
            "meshes_with_name_token": category_counts[category],
            "meshes_over_500_lod0_vertices": sum(
                1
                for row in rows
                if category in row["semantic_name_matches"] and row["lod0_vertices_over_500"]
            ),
        }
        for category in ("wall", "window", "door")
    }
    stats = {
        "static_mesh_count": len(meshes),
        "named_module_counts": named_counts,
        "lod0_vertex_min": min(
            (row["vertices_by_lod"][0] for row in rows if row["vertices_by_lod"]), default=None
        ),
        "lod0_vertex_max": max(
            (row["vertices_by_lod"][0] for row in rows if row["vertices_by_lod"]), default=None
        ),
        "mesh_names_over_500_vertices": [
            row["name"] for row in rows if row["lod0_vertices_over_500"]
        ],
    }
    return rows, stats


def _write_report(payload: dict[str, Any]) -> None:
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with QA_PATH.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def run() -> dict[str, Any]:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise RuntimeError(f"wrong Unreal project loaded: {project_dir}; expected {PROJECT_ROOT}")
    if QA_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing asset inspection QA: {QA_PATH}")

    registry_paths = unreal.EditorAssetLibrary.list_assets(
        URBAN_PATH, recursive=True, include_folder=False
    )
    surface_paths = unreal.EditorAssetLibrary.list_assets(
        SURFACES_PATH, recursive=True, include_folder=False
    )
    material_paths = unreal.EditorAssetLibrary.list_assets(
        MATERIALS_PATH, recursive=True, include_folder=False
    )
    mesh_rows, mesh_stats = _inspect_meshes(registry_paths)

    texture_expectations = (
        ("clean_asphalt_diff_2k", True, unreal.TextureCompressionSettings.TC_DEFAULT),
        ("clean_asphalt_nor_dx_2k", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
        ("clean_asphalt_arm_2k", False, unreal.TextureCompressionSettings.TC_MASKS),
        ("concrete_pavement_03_diff_2k", True, unreal.TextureCompressionSettings.TC_DEFAULT),
        ("concrete_pavement_03_nor_dx_2k", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
        ("concrete_pavement_03_arm_2k", False, unreal.TextureCompressionSettings.TC_MASKS),
    )
    textures = [
        _texture_report(
            SURFACES_PATH + "/" + name,
            expected_srgb,
            expected_compression,
        )
        for name, expected_srgb, expected_compression in texture_expectations
    ]
    materials = [
        _material_report(MATERIALS_PATH + "/M_CityAsphalt2K"),
        _material_report(MATERIALS_PATH + "/M_CityPavement2K"),
    ]
    import_qa = None
    if IMPORT_QA_PATH.is_file():
        try:
            import_qa = json.loads(IMPORT_QA_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            import_qa = {"read_error": f"{type(exc).__name__}: {exc}"}

    missing = []
    if not mesh_rows:
        missing.append("facade StaticMeshes")
    missing.extend(row["asset"] for row in textures if not row.get("present"))
    missing.extend(row["asset"] for row in materials if not row.get("present"))
    settings_mismatches = [
        row["asset"]
        for row in textures
        if row.get("present") and not row.get("settings_match_expected")
    ]

    report = {
        "schema_version": "polyhaven_asset_inspect_qa.v1",
        "status": "inspected",
        "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
        "source_manifest": str(MANIFEST_PATH),
        "source_license": "CC0 1.0 Universal",
        "source_license_url": "https://polyhaven.com/license",
        "previous_import_qa": import_qa,
        "asset_directories": {
            "urban_facade": URBAN_PATH,
            "surfaces": SURFACES_PATH,
            "materials": MATERIALS_PATH,
        },
        "asset_registry_counts": {
            "urban_facade_folder_assets": len(registry_paths),
            "surface_texture_assets": len(surface_paths),
            "pbr_material_assets": len(material_paths),
        },
        "facade_stats": mesh_stats,
        "facade_meshes": mesh_rows,
        "surface_textures": textures,
        "pbr_materials": materials,
        "missing_assets": missing,
        "texture_setting_mismatches": settings_mismatches,
        "read_only": True,
        "scene_or_level_modified": False,
        "catalog_modified": False,
    }
    _write_report(report)
    unreal.log("POLYHAVEN_ASSET_INSPECT_QA " + json.dumps(report, sort_keys=True))
    return report


try:
    RESULT = run()
    print("POLYHAVEN_ASSET_INSPECT_RESULT " + json.dumps(RESULT, indent=2, sort_keys=True))
except Exception as exc:
    unreal.log_error(f"POLYHAVEN_ASSET_INSPECT_FAILED {type(exc).__name__}: {exc}")
    raise
