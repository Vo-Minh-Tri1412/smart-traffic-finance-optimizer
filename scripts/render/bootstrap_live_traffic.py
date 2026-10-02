"""Create the small material set consumed by the live native SUMO renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run() -> None:
    import unreal

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    edits = unreal.MaterialEditingLibrary
    directory = "/Game/LiveTraffic/Materials"
    specs = {
        "M_Vehicle": ((0.02, 0.45, 1.0), 0.15),
        "M_Red": ((1.0, 0.005, 0.005), 3.0),
        "M_Yellow": ((1.0, 0.5, 0.005), 3.0),
        "M_Green": ((0.005, 1.0, 0.02), 3.0),
        "M_Dark": ((0.015, 0.015, 0.02), 0.0),
        "M_Road": ((0.075, 0.08, 0.09), 0.0),
        "M_Ground": ((0.28, 0.32, 0.27), 0.0),
    }
    for name, (color, glow) in specs.items():
        path = f"{directory}/{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            continue
        material = tools.create_asset(name, directory, unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise RuntimeError(f"Could not create {path}")
        rgb = edits.create_material_expression(
            material,
            unreal.MaterialExpressionVectorParameter,
        )
        rgb.set_editor_property("parameter_name", "TrafficColor")
        rgb.set_editor_property("default_value", unreal.LinearColor(*color, 1.0))
        edits.connect_material_property(rgb, "", unreal.MaterialProperty.MP_BASE_COLOR)
        roughness = edits.create_material_expression(material, unreal.MaterialExpressionConstant)
        roughness.set_editor_property("r", 0.8)
        edits.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
        if glow:
            scale = edits.create_material_expression(material, unreal.MaterialExpressionConstant)
            scale.set_editor_property("r", glow)
            multiply = edits.create_material_expression(material, unreal.MaterialExpressionMultiply)
            edits.connect_material_expressions(rgb, "", multiply, "A")
            edits.connect_material_expressions(scale, "", multiply, "B")
            edits.connect_material_property(multiply, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        edits.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material):
            raise RuntimeError(f"Could not save {path}")
    root = Path(__file__).resolve().parents[2]
    body = "/Game/LiveTraffic/Vehicles/sedan/sedan/StaticMeshes/body"
    texture_path = "/Game/LiveTraffic/Textures/colormap"
    for source, destination, expected in [
        (root / "render_assets/vehicles/sedan.glb", "/Game/LiveTraffic/Vehicles/sedan", body),
        (
            root / "render_assets/textures/kenney_car/colormap.png",
            "/Game/LiveTraffic/Textures",
            texture_path,
        ),
    ]:
        if not unreal.EditorAssetLibrary.does_asset_exist(expected):
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(source))
            task.set_editor_property("destination_path", destination)
            task.set_editor_property("automated", True)
            task.set_editor_property("save", True)
            tools.import_asset_tasks([task])
            if not unreal.EditorAssetLibrary.does_asset_exist(expected):
                raise RuntimeError(f"Import did not create {expected}")
    palette_path = f"{directory}/M_CarPalette"
    if not unreal.EditorAssetLibrary.does_asset_exist(palette_path):
        palette = tools.create_asset(
            "M_CarPalette",
            directory,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        sample = edits.create_material_expression(palette, unreal.MaterialExpressionTextureSample)
        sample.set_editor_property("texture", unreal.load_asset(texture_path))
        edits.connect_material_property(sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        edits.recompile_material(palette)
        if not unreal.EditorAssetLibrary.save_loaded_asset(palette):
            raise RuntimeError("Could not save the Kenney vehicle palette")

    def create_profile(name: str, cls: Any) -> tuple[Any, bool]:
        path = f"/Game/LiveTraffic/Profiles/{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            return unreal.load_asset(path), False
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", cls)
        asset = tools.create_asset(name, "/Game/LiveTraffic/Profiles", cls, factory)
        if asset is None:
            raise RuntimeError(f"Could not create {path}")
        return asset, True

    def create_blueprint(name: str, parent: Any) -> tuple[Any, bool]:
        path = f"/Game/LiveTraffic/Blueprints/{name}"
        created = not unreal.EditorAssetLibrary.does_asset_exist(path)
        if created:
            factory = unreal.BlueprintFactory()
            factory.set_editor_property("parent_class", parent)
            blueprint = tools.create_asset(
                name,
                "/Game/LiveTraffic/Blueprints",
                unreal.Blueprint,
                factory,
            )
            if blueprint is None:
                raise RuntimeError(f"Could not create {path}")
            unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
        return unreal.EditorAssetLibrary.load_blueprint_class(path), created

    vehicle_class, _created = create_blueprint(
        "BP_LiveVehicle",
        unreal.TrafficReplayVehicleActor,
    )

    catalog, created = create_profile("LiveAssets", unreal.TrafficLiveAssetCatalog)
    if created:
        meshes = [
            unreal.load_asset(path)
            for path in unreal.EditorAssetLibrary.list_assets(
                "/Game/LiveTraffic/Vehicles/sedan/sedan/StaticMeshes",
                True,
                False,
            )
        ]
        definition = unreal.TrafficVehicleVisualDefinition()
        definition.set_editor_property("vehicle_type", "*")
        definition.set_editor_property("mesh_parts", meshes)
        definition.set_editor_property("actor_class", vehicle_class)
        definition.set_editor_property("material_override", unreal.load_asset(palette_path))
        definition.set_editor_property(
            "forward_axis",
            unreal.TrafficVisualForwardAxis.NEGATIVE_Y,
        )
        definition.set_editor_property("source", "Retained Kenney Car Kit sedan.glb")
        definition.set_editor_property("license", "CC0 1.0")
        catalog.set_editor_property("vehicles", [definition])
        for property_name, asset_path in {
            "road_material": f"{directory}/M_Road",
            "ground_mesh": "/Engine/BasicShapes/Cube",
            "ground_material": f"{directory}/M_Ground",
            "signal_pole_mesh": "/Engine/BasicShapes/Cube",
            "signal_housing_mesh": "/Engine/BasicShapes/Cube",
            "signal_lens_mesh": "/Engine/BasicShapes/Sphere",
            "signal_red": f"{directory}/M_Red",
            "signal_yellow": f"{directory}/M_Yellow",
            "signal_green": f"{directory}/M_Green",
            "signal_inactive": f"{directory}/M_Dark",
        }.items():
            catalog.set_editor_property(property_name, unreal.load_asset(asset_path))
        unreal.EditorAssetLibrary.save_loaded_asset(catalog)
    placement, created = create_profile("LivePlacement", unreal.TrafficLivePlacementProfile)
    if created:
        unreal.EditorAssetLibrary.save_loaded_asset(placement)
    scene, created = create_profile("LiveScene", unreal.TrafficLiveSceneProfile)
    if created:
        scene.set_editor_property("catalog", catalog)
        scene.set_editor_property("placement", placement)
        unreal.EditorAssetLibrary.save_loaded_asset(scene)
    controller_class, created = create_blueprint(
        "BP_LiveController",
        unreal.TrafficLiveController,
    )
    if created:
        unreal.get_default_object(controller_class).set_editor_property("scene_profile", scene)
        unreal.EditorAssetLibrary.save_asset("/Game/LiveTraffic/Blueprints/BP_LiveController")
    unreal.log("SUMO_LIVE native catalog, placement and scene profiles ready")


if __name__ == "__main__":
    run()
