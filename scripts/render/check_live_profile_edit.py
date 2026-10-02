"""Editor-only verification: duplicate profiles, replace the car mesh and camera."""

from __future__ import annotations

from pathlib import Path


def run() -> None:
    import unreal

    root = Path(__file__).resolve().parents[2]
    folder = "/Game/LiveTraffic/Vehicles/van"
    body = f"{folder}/van/StaticMeshes/body"
    if not unreal.EditorAssetLibrary.does_asset_exist(body):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(root / "render_assets/vehicles/van.glb"))
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    meshes = [
        unreal.load_asset(path)
        for path in unreal.EditorAssetLibrary.list_assets(
            f"{folder}/van/StaticMeshes",
            True,
            False,
        )
    ]
    if not meshes:
        raise RuntimeError("Van import produced no meshes")
    catalog_path = "/Game/LiveTraffic/Profiles/LiveAssets_EditCheck"
    scene_path = "/Game/LiveTraffic/Profiles/LiveScene_EditCheck"
    if unreal.EditorAssetLibrary.does_asset_exist(scene_path):
        raise FileExistsError(
            "The edit check already exists; original artist profiles are preserved",
        )
    catalog = unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/LiveTraffic/Profiles/LiveAssets",
        catalog_path,
    )
    definitions = catalog.get_editor_property("vehicles")
    definitions[0].set_editor_property("mesh_parts", meshes)
    definitions[0].set_editor_property("source", "Retained Kenney Car Kit van.glb")
    catalog.set_editor_property("vehicles", definitions)
    unreal.EditorAssetLibrary.save_loaded_asset(catalog)
    scene = unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/LiveTraffic/Profiles/LiveScene",
        scene_path,
    )
    scene.set_editor_property("catalog", catalog)
    scene.set_editor_property("field_of_view", 52.0)
    scene.set_editor_property("follow_offset_meters", unreal.Vector(-14.0, -22.0, 12.0))
    unreal.EditorAssetLibrary.save_loaded_asset(scene)
    unreal.log(f"SUMO_LIVE edit check: {scene_path}; van meshes and FOV 52; no C++ build")


if __name__ == "__main__":
    run()
