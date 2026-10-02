"""Import verified Poly Haven facade and road-surface files into a new UE folder.

Run with the canonical Unreal Engine 5.8 project:

    UnrealEditor-Cmd.exe TrafficRender.uproject -ExecutePythonScript=<this-file> -NullRHI

This imports assets only. It does not load, save, or modify any level or catalog.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
MANIFEST_PATH = (
    ROOT / "artifacts" / "city_assets" / "polyhaven" / "manifest.v1-4a6a6d12b0df21cd.json"
)
QA_PATH = ROOT / "artifacts" / "tmp" / "city_pipeline" / "polyhaven_import_qa.json"
URBAN_DESTINATION = "/Game/City/Assets/PolyHaven/UrbanFacade"
SURFACE_DESTINATION = "/Game/City/Assets/PolyHaven/Surfaces"
MATERIAL_DESTINATION = "/Game/City/Assets/PolyHaven/Materials"
EXPECTED_ASSETS = {
    "modular_urban_apartments_facade": ("model", "2k"),
    "clean_asphalt": ("texture", "2k"),
    "concrete_pavement_03": ("texture", "2k"),
}
LOD_TARGETS = (
    ("double_window_module", "window_centered_double_01"),
    ("door_window_module", "door_window_small_04"),
    ("large_window_module", "window_centered_large_01"),
)
LOW_POLY_WALL_NAMES = (
    "wall_standard_standard_01",
    "wall_window_centered_double_01",
)


class ImportFailure(RuntimeError):
    """Raised when source, import, texture, material, or LOD QA fails."""


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


def _content_path(asset_directory: str) -> Path:
    if not asset_directory.startswith("/Game/"):
        raise ImportFailure(f"expected a /Game package directory: {asset_directory}")
    relative = PurePosixPath(asset_directory.removeprefix("/Game/"))
    return Path(unreal.Paths.project_content_dir()).resolve().joinpath(*relative.parts)


def _preflight_new_package_directory(asset_directory: str) -> None:
    existing = unreal.EditorAssetLibrary.list_assets(
        asset_directory, recursive=True, include_folder=False
    )
    if existing:
        raise FileExistsError(
            f"refusing to import over existing UE assets in {asset_directory}: {list(existing)[:8]}"
        )
    on_disk = _content_path(asset_directory)
    if on_disk.exists():
        generated = [
            path
            for path in on_disk.rglob("*")
            if path.is_file() and path.suffix.lower() in {".uasset", ".umap"}
        ]
        if generated:
            raise FileExistsError(
                "refusing to import over existing UE packages in "
                f"{asset_directory}: {generated[:8]}"
            )


def _load_and_verify_source_manifest() -> tuple[
    dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]
]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "polyhaven_city_assets.v1"
    ):
        raise ImportFailure("Poly Haven source manifest has an unsupported schema")
    if manifest.get("license") != "CC0 1.0 Universal":
        raise ImportFailure("source manifest does not record the expected CC0 license")
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise ImportFailure("source manifest has no assets array")
    by_id = {asset.get("id"): asset for asset in assets if isinstance(asset, dict)}
    if set(by_id) != set(EXPECTED_ASSETS):
        raise ImportFailure(f"source manifest asset ids differ: {sorted(by_id)}")

    verified_files: dict[str, dict[str, Any]] = {}
    for asset_id, (expected_type, expected_resolution) in EXPECTED_ASSETS.items():
        asset = by_id[asset_id]
        if asset.get("type") != expected_type or asset.get("resolution") != expected_resolution:
            raise ImportFailure(f"unexpected source type/resolution for {asset_id}")
        if asset.get("license") != "CC0 1.0 Universal":
            raise ImportFailure(f"source asset does not record CC0: {asset_id}")
        file_rows = asset.get("files")
        if not isinstance(file_rows, list) or not file_rows:
            raise ImportFailure(f"source asset has no files: {asset_id}")
        for row in file_rows:
            relative_value = row.get("path")
            if not isinstance(relative_value, str):
                raise ImportFailure(f"source file path is malformed for {asset_id}")
            relative = PurePosixPath(relative_value)
            if relative.is_absolute() or ".." in relative.parts:
                raise ImportFailure(f"source file path escapes the repository: {relative_value}")
            local_path = ROOT.joinpath(*relative.parts)
            if not local_path.is_file():
                raise FileNotFoundError(f"manifest source file is missing: {local_path}")
            size = local_path.stat().st_size
            sha256 = _sha256(local_path)
            if size != row.get("size_bytes") or sha256 != row.get("sha256"):
                raise ImportFailure(
                    f"source SHA-256/size mismatch before UE import: {relative_value}"
                )
            row_copy = dict(row)
            row_copy["local_path"] = str(local_path.resolve())
            verified_files[relative_value] = row_copy
    return manifest, by_id, verified_files


def _asset_import_task(
    filename: Path, destination: str, destination_name: str | None = None
) -> Any:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(filename))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", False)
    if destination_name:
        task.set_editor_property("destination_name", destination_name)
    return task


def _task_object_paths(task: Any) -> list[str]:
    paths = task.get_editor_property("imported_object_paths")
    return sorted(str(path) for path in paths)


def _load_imported_objects(paths: list[str]) -> list[Any]:
    objects = []
    for path in paths:
        asset = unreal.load_asset(path)
        if not asset:
            raise ImportFailure(f"UE reported an imported object that cannot be loaded: {path}")
        objects.append(asset)
    return objects


def _material_slots(mesh: Any) -> list[dict[str, Any]]:
    slots = []
    for index, static_material in enumerate(mesh.get_editor_property("static_materials")):
        slot_name = str(static_material.get_editor_property("material_slot_name"))
        material = static_material.get_editor_property("material_interface")
        material_path = material.get_path_name() if material else ""
        slots.append(
            {
                "index": index,
                "slot_name": slot_name,
                "material_asset": material_path,
                "assigned": bool(material),
            }
        )
    return slots


def _mesh_vertex_count(mesh: Any, lod_index: int) -> int:
    count = int(unreal.EditorStaticMeshLibrary.get_number_verts(mesh, lod_index))
    if count < 0:
        raise ImportFailure(
            "EditorStaticMeshLibrary could not read vertices for "
            f"{mesh.get_path_name()} LOD{lod_index}"
        )
    return count


def _texture_settings(
    texture: Any, role: str, asset_id: str, material_texture_qa: dict[str, dict[str, str]]
) -> dict[str, Any]:
    role_suffix = role.removeprefix("texture_")
    if role_suffix == "Diffuse":
        srgb = True
        compression = unreal.TextureCompressionSettings.TC_DEFAULT
        material_semantic = "base_color"
    elif role_suffix == "nor_dx":
        srgb = False
        compression = unreal.TextureCompressionSettings.TC_NORMALMAP
        material_semantic = "normal"
    elif role_suffix == "arm":
        srgb = False
        compression = unreal.TextureCompressionSettings.TC_MASKS
        material_semantic = "arm"
    else:
        raise ImportFailure(f"unexpected standalone texture role: {role}")
    texture.set_editor_property("srgb", srgb)
    texture.set_editor_property("compression_settings", compression)
    if not unreal.EditorAssetLibrary.save_loaded_asset(texture):
        raise ImportFailure(f"failed to save imported texture settings: {texture.get_path_name()}")
    path = texture.get_path_name()
    if material_semantic in material_texture_qa[asset_id]:
        raise ImportFailure(f"duplicate {material_semantic} texture for {asset_id}: {path}")
    material_texture_qa[asset_id][material_semantic] = path
    readback_srgb = bool(texture.get_editor_property("srgb"))
    readback_compression = texture.get_editor_property("compression_settings")
    if readback_srgb != srgb or readback_compression != compression:
        raise ImportFailure(f"texture settings readback differs from expected: {path}")
    return {
        "asset": path,
        "semantic": material_semantic,
        "srgb": readback_srgb,
        "compression_settings": str(readback_compression),
    }


def _create_pbr_material(
    asset_tools: Any,
    material_name: str,
    material_texture_paths: dict[str, str],
) -> dict[str, Any]:
    material = asset_tools.create_asset(
        material_name,
        MATERIAL_DESTINATION,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise ImportFailure(f"failed to create PBR material: {material_name}")

    material_editor = unreal.MaterialEditingLibrary
    expressions = {}
    for semantic, texture_path in material_texture_paths.items():
        texture = unreal.load_asset(texture_path)
        if not texture:
            raise ImportFailure(f"PBR source texture is missing: {texture_path}")
        sample = material_editor.create_material_expression(
            material, unreal.MaterialExpressionTextureSample
        )
        if not sample:
            raise ImportFailure(f"failed to create texture sample in {material_name}: {semantic}")
        sample.set_editor_property("texture", texture)
        if semantic == "normal":
            sample.set_editor_property(
                "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            )
        elif semantic == "arm":
            sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        expressions[semantic] = sample

    material_editor.connect_material_property(
        expressions["base_color"], "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    material_editor.connect_material_property(
        expressions["normal"], "RGB", unreal.MaterialProperty.MP_NORMAL
    )
    for channel, property_name in (
        ("R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
        ("G", unreal.MaterialProperty.MP_ROUGHNESS),
        ("B", unreal.MaterialProperty.MP_METALLIC),
    ):
        material_editor.connect_material_property(expressions["arm"], channel, property_name)
    material_editor.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material):
        raise ImportFailure(f"failed to save PBR material: {material_name}")
    return {
        "asset": material.get_path_name(),
        "texture_inputs": dict(material_texture_paths),
        "mapping": {
            "Diffuse.RGB": "Base Color",
            "nor_dx.RGB": "Normal",
            "arm.R": "Ambient Occlusion",
            "arm.G": "Roughness",
            "arm.B": "Metallic",
            "uv": "TextureCoordinate0 / native imported UVs",
        },
    }


def _lod_candidates(mesh_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    rows_by_name = {row["name"]: row for row in mesh_rows}
    used_paths: set[str] = set()
    for role, mesh_name in LOD_TARGETS:
        chosen = rows_by_name.get(mesh_name)
        if not chosen:
            raise ImportFailure(
                f"expected imported facade module {mesh_name!r} is missing; "
                f"available mesh names={sorted(rows_by_name)[:40]}"
            )
        if chosen["vertices_lod0"] <= 500:
            raise ImportFailure(
                f"selected LOD module is below the 500-vertex threshold: "
                f"{mesh_name} has {chosen['vertices_lod0']} LOD0 vertices"
            )
        if chosen["asset_path"] in used_paths:
            raise ImportFailure(f"duplicate StaticMesh selected for LOD generation: {mesh_name}")
        selected[role] = chosen
        used_paths.add(chosen["asset_path"])
    return selected


def _build_facade_lods(selected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    options = unreal.EditorScriptingMeshReductionOptions()
    settings = unreal.EditorScriptingMeshReductionSettings
    options.set_editor_property(
        "reduction_settings",
        [settings(1.0, 1.0), settings(0.5, 0.5), settings(0.25, 0.25)],
    )
    options.set_editor_property("auto_compute_lod_screen_size", False)
    results = []
    for role, row in selected.items():
        mesh = unreal.load_asset(row["asset_path"])
        if not mesh:
            raise ImportFailure(
                f"selected facade mesh disappeared before LOD build: {row['asset_path']}"
            )
        result = unreal.EditorStaticMeshLibrary.set_lods(mesh, options)
        lod_count = int(unreal.EditorStaticMeshLibrary.get_lod_count(mesh))
        if lod_count < 3:
            raise ImportFailure(
                f"set_lods returned {result!r} but only produced {lod_count} LODs "
                f"for {row['asset_path']}"
            )
        vertices = [_mesh_vertex_count(mesh, lod_index) for lod_index in range(min(lod_count, 3))]
        if not (vertices[0] > vertices[1] > vertices[2] > 0):
            raise ImportFailure(
                f"LOD vertex counts did not decline for {row['asset_path']}: {vertices}"
            )
        if not unreal.EditorAssetLibrary.save_loaded_asset(mesh):
            raise ImportFailure(f"failed to save LOD settings for {row['asset_path']}")
        results.append(
            {
                "semantic_role": role,
                "asset_path": row["asset_path"],
                "name": row["name"],
                "set_lods_return": result,
                "lod_count": lod_count,
                "vertices_lod0_lod1_lod2": vertices,
                "screen_size_thresholds": [1.0, 0.5, 0.25],
                "triangle_retention": [1.0, 0.5, 0.25],
            }
        )
    return results


def _run_import(qa: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise ImportFailure(f"wrong Unreal project loaded: {project_dir}; expected {PROJECT_ROOT}")
    if QA_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing import QA: {QA_PATH}")

    manifest, source_assets, verified_files = _load_and_verify_source_manifest()
    qa["source_manifest"] = str(MANIFEST_PATH)
    qa["source_manifest_sha256"] = _sha256(MANIFEST_PATH)
    qa["source_license"] = manifest["license"]
    qa["source_license_url"] = manifest["license_url"]
    qa["api_credit_required"] = manifest.get("api_credit_required")
    qa["verified_source_file_count"] = len(verified_files)
    qa["source_sha256_verified"] = True
    qa["source_files_verified"] = [
        {
            "path": relative_path,
            "size_bytes": row["size_bytes"],
            "sha256": row["sha256"],
        }
        for relative_path, row in sorted(verified_files.items())
    ]
    qa["assets"] = [
        {
            "id": asset_id,
            "name": source_assets[asset_id].get("name"),
            "resolution": source_assets[asset_id].get("resolution"),
            "source_page": source_assets[asset_id].get("source_page"),
            "license": source_assets[asset_id].get("license"),
            "source_total_bytes": source_assets[asset_id].get("total_bytes"),
        }
        for asset_id in sorted(source_assets)
    ]

    for destination in (URBAN_DESTINATION, SURFACE_DESTINATION, MATERIAL_DESTINATION):
        _preflight_new_package_directory(destination)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    model_asset = source_assets["modular_urban_apartments_facade"]
    gltf_rows = [
        row
        for row in model_asset["files"]
        if row["role"] == "model" and row["path"].lower().endswith(".gltf")
    ]
    if len(gltf_rows) != 1:
        raise ImportFailure(
            f"expected exactly one 2K GLTF entry in the manifest, found {len(gltf_rows)}"
        )
    gltf_path = Path(verified_files[gltf_rows[0]["path"]]["local_path"])
    model_task = _asset_import_task(gltf_path, URBAN_DESTINATION)
    unreal.log(f"POLYHAVEN_IMPORT_GLTf {gltf_path}")
    asset_tools.import_asset_tasks([model_task])
    imported_paths = _task_object_paths(model_task)
    urban_paths = unreal.EditorAssetLibrary.list_assets(
        URBAN_DESTINATION, recursive=True, include_folder=False
    )
    if not imported_paths or not urban_paths:
        raise ImportFailure(
            "GLTF import produced no UE assets; "
            f"task_paths={imported_paths}, folder_assets={list(urban_paths)}"
        )
    imported_objects = _load_imported_objects(list(urban_paths))
    static_meshes = [obj for obj in imported_objects if isinstance(obj, unreal.StaticMesh)]
    if len(static_meshes) <= 1:
        imported_class_paths = [
            (obj.get_path_name(), obj.get_class().get_path_name()) for obj in imported_objects
        ]
        raise ImportFailure(
            "Poly Haven facade GLTF did not import as a modular StaticMesh set; "
            f"task_paths={imported_paths}, imported_classes={imported_class_paths}"
        )
    qa["imported_asset_ids"] = ["modular_urban_apartments_facade"]
    qa["imported_asset_paths"] = {"urban_facade_task": imported_paths}

    texture_tasks: list[Any] = []
    texture_jobs: list[tuple[Any, dict[str, Any]]] = []
    expected_texture_paths: dict[str, dict[str, str]] = {
        "clean_asphalt": {},
        "concrete_pavement_03": {},
    }
    for asset_id in ("clean_asphalt", "concrete_pavement_03"):
        for file_row in source_assets[asset_id]["files"]:
            role = file_row["role"]
            local_path = Path(verified_files[file_row["path"]]["local_path"])
            destination_name = local_path.stem
            task = _asset_import_task(local_path, SURFACE_DESTINATION, destination_name)
            texture_tasks.append(task)
            texture_jobs.append((task, {"asset_id": asset_id, "file_row": file_row}))
            semantic = role.removeprefix("texture_")
            expected_texture_paths[asset_id][semantic] = f"{SURFACE_DESTINATION}/{destination_name}"
    asset_tools.import_asset_tasks(texture_tasks)

    texture_qa: list[dict[str, Any]] = []
    material_texture_paths: dict[str, dict[str, str]] = {
        "clean_asphalt": {},
        "concrete_pavement_03": {},
    }
    for task, context in sorted(texture_jobs, key=lambda pair: pair[1]["file_row"]["path"]):
        filename = Path(context["file_row"]["path"]).name
        asset_id = context["asset_id"]
        file_row = context["file_row"]
        imported_texture_objects = [
            obj
            for obj in _load_imported_objects(_task_object_paths(task))
            if isinstance(obj, unreal.Texture2D)
        ]
        expected_object_path = expected_texture_paths[asset_id][
            file_row["role"].removeprefix("texture_")
        ]
        if len(imported_texture_objects) != 1:
            imported_texture_objects = [
                unreal.load_asset(path)
                for path in unreal.EditorAssetLibrary.list_assets(
                    SURFACE_DESTINATION, recursive=False, include_folder=False
                )
                if path == expected_object_path
            ]
        if len(imported_texture_objects) != 1 or not imported_texture_objects[0]:
            raise ImportFailure(
                f"expected exactly one imported Texture2D for {filename}; "
                f"task_paths={_task_object_paths(task)}"
            )
        texture = imported_texture_objects[0]
        semantic = file_row["role"].removeprefix("texture_")
        texture_qa.append(
            _texture_settings(texture, file_row["role"], asset_id, material_texture_paths)
        )
        texture_qa[-1].update(
            {
                "source_path": file_row["path"],
                "source_sha256": file_row["sha256"],
                "source_role": file_row["role"],
                "asset_id": asset_id,
                "semantic": semantic,
                "imported_object_paths": _task_object_paths(task),
            }
        )

    material_qa = []
    for asset_id, material_name in (
        ("clean_asphalt", "M_CityAsphalt2K"),
        ("concrete_pavement_03", "M_CityPavement2K"),
    ):
        textures = material_texture_paths[asset_id]
        if set(textures) != {"base_color", "normal", "arm"}:
            raise ImportFailure(f"PBR texture set is incomplete for {asset_id}: {textures}")
        material_qa.append(_create_pbr_material(asset_tools, material_name, textures))
    qa["imported_asset_ids"].extend(["clean_asphalt", "concrete_pavement_03"])

    mesh_qa: list[dict[str, Any]] = []
    missing_material_slots = []
    for mesh in sorted(static_meshes, key=lambda obj: obj.get_path_name()):
        material_slots = _material_slots(mesh)
        if any(not slot["assigned"] for slot in material_slots):
            missing_material_slots.append(mesh.get_path_name())
        mesh_qa.append(
            {
                "asset_path": mesh.get_path_name(),
                "name": mesh.get_name(),
                "vertices_lod0": _mesh_vertex_count(mesh, 0),
                "lod_count_before_generation": int(
                    unreal.EditorStaticMeshLibrary.get_lod_count(mesh)
                ),
                "material_slot_count": len(material_slots),
                "material_slots": material_slots,
            }
        )
    if missing_material_slots:
        raise ImportFailure(
            f"GLTF imported meshes have empty material slots: {missing_material_slots[:12]}"
        )

    selected_lod_meshes = _lod_candidates(mesh_qa)
    lod_qa = _build_facade_lods(selected_lod_meshes)
    qa.update(
        {
            "status": "success",
            "imported_asset_paths": {
                "urban_facade_task": imported_paths,
                "urban_facade_folder_assets": list(urban_paths),
                "surface_textures": sorted(
                    texture_path
                    for mapping in material_texture_paths.values()
                    for texture_path in mapping.values()
                ),
                "materials": [row["asset"] for row in material_qa],
            },
            "facade": {
                "source_gltf": gltf_rows[0]["path"],
                "static_mesh_count": len(static_meshes),
                "static_meshes": mesh_qa,
                "selected_lod_meshes": lod_qa,
                "lod0_only_small_wall_modules": [
                    row
                    for row in mesh_qa
                    if row["name"] in LOW_POLY_WALL_NAMES and row["vertices_lod0"] <= 500
                ],
                "small_wall_lod_policy": (
                    "Low-poly wall panels remain LOD0; their placement stage should use "
                    "HISM and distance culling."
                ),
                "source_import_material_slots_preserved": True,
            },
            "surface_textures": texture_qa,
            "pbr_materials": material_qa,
            "scene_or_level_modified": False,
            "catalog_modified": False,
        }
    )
    return qa


def run() -> dict[str, Any]:
    if QA_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing Poly Haven import QA: {QA_PATH}")
    qa: dict[str, Any] = {
        "schema_version": "polyhaven_ue_import_qa.v1",
        "status": "failed",
        "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
        "new_package_directories": [
            URBAN_DESTINATION,
            SURFACE_DESTINATION,
            MATERIAL_DESTINATION,
        ],
        "imported_asset_paths": {},
        "imported_asset_ids": [],
        "missing_assets": [],
        "errors": [],
        "scene_or_level_modified": False,
        "catalog_modified": False,
    }
    try:
        result = _run_import(qa)
        _write_qa(result)
        unreal.log("POLYHAVEN_UE_IMPORT_QA " + json.dumps(result, sort_keys=True))
        return result
    except Exception as exc:
        qa["errors"].append(f"{type(exc).__name__}: {exc}")
        imported_ids = set(qa.get("imported_asset_ids", []))
        qa["missing_assets"] = sorted(set(EXPECTED_ASSETS) - imported_ids)
        with contextlib.suppress(FileExistsError):
            _write_qa(qa)
        unreal.log_error("POLYHAVEN_UE_IMPORT_FAILED " + json.dumps(qa, sort_keys=True))
        raise


try:
    RESULT = run()
    print("POLYHAVEN_UE_IMPORT_RESULT " + json.dumps(RESULT, indent=2, sort_keys=True))
except Exception as exc:
    unreal.log_error(f"POLYHAVEN_UE_IMPORT_FATAL {type(exc).__name__}: {exc}")
    raise
