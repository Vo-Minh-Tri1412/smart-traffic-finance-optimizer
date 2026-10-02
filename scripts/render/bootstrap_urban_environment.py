"""Seed editable urban Data Assets and materials; preserve later artist edits."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def run() -> None:
    import unreal

    root = Path(__file__).resolve().parents[2]
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    edits = unreal.MaterialEditingLibrary
    directory = "/Game/LiveTraffic/Urban/Materials"

    def constant(material: Any, value: float) -> Any:
        node = edits.create_material_expression(material, unreal.MaterialExpressionConstant)
        node.set_editor_property("r", value)
        return node

    def vector(material: Any, name: str, color: tuple[float, float, float]) -> Any:
        node = edits.create_material_expression(
            material,
            unreal.MaterialExpressionVectorParameter,
        )
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", unreal.LinearColor(*color, 1.0))
        return node

    def operation(material: Any, cls: Any, a: Any, b: Any = None) -> Any:
        node = edits.create_material_expression(material, cls)
        if not edits.connect_material_expressions(a, "", node, "A" if b is not None else ""):
            raise RuntimeError(f"Could not connect material input: {cls}")
        if b is not None:
            edits.connect_material_expressions(b, "", node, "B")
        return node

    def material(name: str, color: tuple[float, float, float], windows: bool = False) -> Any:
        path = f"{directory}/{name}"
        result = unreal.load_asset(path)
        if result is not None:
            if not (windows and os.environ.get("AIQ_URBAN_REPAIR_MATERIALS") == "1"):
                return result
            edits.delete_all_material_expressions(result)
        else:
            result = tools.create_asset(
                name,
                directory,
                unreal.Material,
                unreal.MaterialFactoryNew(),
            )
        result.set_editor_property("two_sided", True)
        base = vector(result, "FacadeColor", color)
        if windows:
            uv = edits.create_material_expression(
                result,
                unreal.MaterialExpressionTextureCoordinate,
            )
            fract = operation(result, unreal.MaterialExpressionFrac, uv)
            masks = []
            for axis, low, high in [(0, 0.18, 0.82), (1, 0.20, 0.76)]:
                channel = edits.create_material_expression(
                    result,
                    unreal.MaterialExpressionComponentMask,
                )
                channel.set_editor_property("r", axis == 0)
                channel.set_editor_property("g", axis == 1)
                if not edits.connect_material_expressions(fract, "", channel, ""):
                    raise RuntimeError("Could not connect facade UV channel")
                lower = operation(
                    result,
                    unreal.MaterialExpressionSubtract,
                    channel,
                    constant(result, low),
                )
                upper = operation(
                    result,
                    unreal.MaterialExpressionSubtract,
                    constant(result, high),
                    channel,
                )
                for edge in [lower, upper]:
                    sharp = operation(
                        result,
                        unreal.MaterialExpressionMultiply,
                        edge,
                        constant(result, 30),
                    )
                    masks.append(operation(result, unreal.MaterialExpressionSaturate, sharp))
            mask = masks[0]
            for edge in masks[1:]:
                mask = operation(result, unreal.MaterialExpressionMultiply, mask, edge)
            blend = edits.create_material_expression(
                result,
                unreal.MaterialExpressionLinearInterpolate,
            )
            edits.connect_material_expressions(base, "", blend, "A")
            glass = vector(result, "WindowColor", (0.025, 0.065, 0.09))
            edits.connect_material_expressions(glass, "", blend, "B")
            edits.connect_material_expressions(mask, "", blend, "Alpha")
            base = blend
        edits.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
        roughness = constant(result, 0.7)
        edits.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
        edits.recompile_material(result)
        unreal.EditorAssetLibrary.save_loaded_asset(result)
        return result

    facades = [
        material("M_FacadeWarm", (0.46, 0.36, 0.25), True),
        material("M_FacadeStone", (0.45, 0.47, 0.43), True),
        material("M_FacadeTerracotta", (0.45, 0.23, 0.16), True),
    ]
    roof = material("M_Roof", (0.10, 0.13, 0.14))
    white = material("M_LaneWhite", (0.85, 0.84, 0.77))
    yellow = material("M_CenterYellow", (0.95, 0.53, 0.035))
    curb = material("M_Curb", (0.52, 0.53, 0.48))
    sidewalk = unreal.load_asset("/Game/City/Assets/PolyHaven/Materials/M_CityPavement2K")
    if sidewalk is None:
        sidewalk = material("M_Sidewalk", (0.42, 0.43, 0.39))

    tree_folder = "/Game/LiveTraffic/Urban/Trees/tree-large"
    tree_mesh_folder = f"{tree_folder}/tree-large/StaticMeshes"
    texture_path = "/Game/LiveTraffic/Urban/Textures/colormap"
    if not unreal.EditorAssetLibrary.list_assets(tree_mesh_folder, True, False):
        task = unreal.AssetImportTask()
        task.set_editor_property(
            "filename",
            str(root / "render_assets/street_furniture/trees/tree-large.glb"),
        )
        task.set_editor_property("destination_path", tree_folder)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        tools.import_asset_tasks([task])
    if not unreal.EditorAssetLibrary.does_asset_exist(texture_path):
        task = unreal.AssetImportTask()
        task.set_editor_property(
            "filename",
            str(root / "render_assets/textures/kenney_suburban/colormap.png"),
        )
        task.set_editor_property("destination_path", "/Game/LiveTraffic/Urban/Textures")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        tools.import_asset_tasks([task])
    tree_material_path = f"{directory}/M_TreePalette"
    if not unreal.EditorAssetLibrary.does_asset_exist(tree_material_path):
        tree_material = tools.create_asset(
            "M_TreePalette",
            directory,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        sample = edits.create_material_expression(
            tree_material,
            unreal.MaterialExpressionTextureSample,
        )
        sample.set_editor_property("texture", unreal.load_asset(texture_path))
        edits.connect_material_property(sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        edits.recompile_material(tree_material)
        unreal.EditorAssetLibrary.save_loaded_asset(tree_material)

    def profile(name: str, cls: Any) -> tuple[Any, bool]:
        path = f"/Game/LiveTraffic/Profiles/{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            return unreal.load_asset(path), False
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", cls)
        asset = tools.create_asset(name, "/Game/LiveTraffic/Profiles", cls, factory)
        if asset is None:
            raise RuntimeError(f"Could not create {path}")
        return asset, True

    catalog, created = profile("UrbanAssets", unreal.TrafficUrbanAssetCatalog)
    if created:
        catalog.set_editor_property("facade_materials", facades)
        for key, value in {
            "roof_material": roof,
            "white_marking_material": white,
            "yellow_marking_material": yellow,
            "sidewalk_material": sidewalk,
            "curb_material": curb,
            "tree_material_override": unreal.load_asset(tree_material_path),
        }.items():
            catalog.set_editor_property(key, value)
        parts = [
            unreal.load_asset(path)
            for path in unreal.EditorAssetLibrary.list_assets(
                tree_mesh_folder,
                True,
                False,
            )
        ]
        if not parts:
            raise RuntimeError("Tree import produced no mesh parts")
        catalog.set_editor_property("tree_mesh_parts", parts)
        catalog.set_editor_property("tree_source", "Retained Kenney tree-large.glb")
        catalog.set_editor_property("tree_license", "CC0 1.0")
        unreal.EditorAssetLibrary.save_loaded_asset(catalog)
    placement, created = profile("UrbanPlacement", unreal.TrafficUrbanPlacementProfile)
    if created:
        source = root / "render_unreal/CitySources/urban_geometry.v1.json"
        geometry = json.loads(source.read_text(encoding="utf-8"))
        placement.set_editor_property("geometry_source_path", "CitySources/urban_geometry.v1.json")
        placement.set_editor_property(
            "geometry_source_sha256",
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        placement.set_editor_property(
            "geometry_source_sha1",
            hashlib.sha1(source.read_bytes()).hexdigest(),
        )
        placement.set_editor_property("expected_net_sha256", geometry["source_net_sha256"])
        rules = []
        for tag, minimum, maximum in [
            ("*", 6, 15),
            ("house", 4, 9),
            ("apartments", 12, 30),
            ("residential", 6, 18),
            ("office", 12, 36),
            ("commercial", 9, 24),
            ("industrial", 4, 10),
            ("school", 6, 15),
        ]:
            rule = unreal.TrafficBuildingHeightRule()
            rule.set_editor_property("building_tag", tag)
            rule.set_editor_property("min_height_meters", minimum)
            rule.set_editor_property("max_height_meters", maximum)
            rules.append(rule)
        placement.set_editor_property("height_rules", rules)
        placement.set_editor_property(
            "height_assumption",
            "Editable synthetic heights; OSM footprint positions, not surveyed elevation.",
        )
        unreal.EditorAssetLibrary.save_loaded_asset(placement)
    elif not placement.get_editor_property("geometry_source_sha1"):
        source = root / "render_unreal/CitySources/urban_geometry.v1.json"
        placement.set_editor_property(
            "geometry_source_sha1",
            hashlib.sha1(source.read_bytes()).hexdigest(),
        )
        unreal.EditorAssetLibrary.save_loaded_asset(placement)
    urban, created = profile("UrbanEnvironment", unreal.TrafficUrbanSceneProfile)
    if created:
        urban.set_editor_property("catalog", catalog)
        urban.set_editor_property("placement", placement)
        unreal.EditorAssetLibrary.save_loaded_asset(urban)
    scene_path = "/Game/LiveTraffic/Profiles/UrbanScene"
    if not unreal.EditorAssetLibrary.does_asset_exist(scene_path):
        scene = unreal.EditorAssetLibrary.duplicate_asset(
            "/Game/LiveTraffic/Profiles/LiveScene",
            scene_path,
        )
        live_catalog = unreal.EditorAssetLibrary.duplicate_asset(
            "/Game/LiveTraffic/Profiles/LiveAssets",
            "/Game/LiveTraffic/Profiles/UrbanLiveAssets",
        )
        asphalt = unreal.load_asset("/Game/City/Assets/PolyHaven/Materials/M_CityAsphalt2K")
        if asphalt:
            live_catalog.set_editor_property("road_material", asphalt)
        unreal.EditorAssetLibrary.save_loaded_asset(live_catalog)
        scene.set_editor_property("catalog", live_catalog)
        scene.set_editor_property("urban_environment", urban)
        unreal.EditorAssetLibrary.save_loaded_asset(scene)
        controller = unreal.EditorAssetLibrary.load_blueprint_class(
            "/Game/LiveTraffic/Blueprints/BP_LiveController",
        )
        unreal.get_default_object(controller).set_editor_property("scene_profile", scene)
        unreal.EditorAssetLibrary.save_asset("/Game/LiveTraffic/Blueprints/BP_LiveController")
    unreal.log("SUMO_URBAN native editable buildings/markings/sidewalks/greenery profiles ready")


if __name__ == "__main__":
    run()
