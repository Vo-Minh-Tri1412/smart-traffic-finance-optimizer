from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_godot_visual_asset_catalog_files_exist() -> None:
    render_root = PROJECT_ROOT / "render"

    required_paths = [
        render_root / "resources" / "catalogs" / "VehicleAssetCatalog.tres",
        render_root / "resources" / "catalogs" / "ZoneAssetCatalog.tres",
        render_root / "scripts" / "assets" / "vehicle_asset_catalog.gd",
        render_root / "scripts" / "assets" / "zone_asset_catalog.gd",
        render_root / "scripts" / "zones" / "semantic_overlay_renderer.gd",
        render_root / "scenes" / "zones" / "ZoneVisualBase.tscn",
    ]

    missing = [path for path in required_paths if not path.is_file()]
    assert not missing


def test_zone_catalog_references_imported_zone_assets() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog = render_root / "resources" / "catalogs" / "ZoneAssetCatalog.tres"
    body = catalog.read_text(encoding="utf-8")

    for expected in [
        "res://imported_assets/buildings/residential/building-type-a.glb",
        "res://imported_assets/buildings/commercial/building-a.glb",
        "res://imported_assets/buildings/industrial/building-a.glb",
        "res://scenes/zones/HospitalZoneVisual.tscn",
        "res://scenes/zones/IndustrialZoneVisual.tscn",
    ]:
        assert expected in body


def test_vehicle_catalog_replaces_json_default_contract() -> None:
    render_root = PROJECT_ROOT / "render"
    controller = render_root / "scripts" / "replay" / "trace_replay_controller.gd"
    body = controller.read_text(encoding="utf-8")

    assert 'asset_manifest_path := "res://resources/catalogs/VehicleAssetCatalog.tres"' in body
    assert "res://resources/configs/asset_manifest.example.json" not in body
