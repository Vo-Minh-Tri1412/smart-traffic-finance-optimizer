"""Change assumed height through native Data Assets in the Editor, without C++ edits."""

from __future__ import annotations

import json
from pathlib import Path


def run() -> None:
    import unreal

    root = Path(__file__).resolve().parents[2]
    geometry = json.loads(
        (root / "render_unreal/CitySources/urban_geometry.v1.json").read_text(encoding="utf-8"),
    )
    building_id = geometry["buildings"][0]["id"]
    placement_path = "/Game/LiveTraffic/Profiles/UrbanPlacement_HeightCheck"
    if unreal.EditorAssetLibrary.does_asset_exist(placement_path):
        raise FileExistsError("The height edit check already exists")
    placement = unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/LiveTraffic/Profiles/UrbanPlacement",
        placement_path,
    )
    overrides = placement.get_editor_property("building_height_overrides")
    overrides[building_id] = 24.0
    placement.set_editor_property("building_height_overrides", overrides)
    unreal.EditorAssetLibrary.save_loaded_asset(placement)
    urban = unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/LiveTraffic/Profiles/UrbanEnvironment",
        "/Game/LiveTraffic/Profiles/UrbanEnvironment_HeightCheck",
    )
    urban.set_editor_property("placement", placement)
    unreal.EditorAssetLibrary.save_loaded_asset(urban)
    scene = unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/LiveTraffic/Profiles/UrbanScene",
        "/Game/LiveTraffic/Profiles/UrbanScene_HeightCheck",
    )
    scene.set_editor_property("urban_environment", urban)
    unreal.EditorAssetLibrary.save_loaded_asset(scene)
    unreal.log(f"SUMO_URBAN height check: {building_id}=24 m via Editor Data Asset")


if __name__ == "__main__":
    run()
