from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ZONE_TAXONOMY = [
    "residential",
    "commercial",
    "market_retail",
    "education",
    "healthcare",
    "industrial",
    "port_logistics",
    "transport_hub",
    "public_service",
    "nightlife",
    "gateway",
    "mixed",
]

ZONE_SCENES = {
    "residential": "ResidentialZoneVisual.tscn",
    "commercial": "CommercialZoneVisual.tscn",
    "market_retail": "MarketRetailZoneVisual.tscn",
    "education": "EducationZoneVisual.tscn",
    "healthcare": "HealthcareZoneVisual.tscn",
    "industrial": "IndustrialZoneVisual.tscn",
    "port_logistics": "PortLogisticsZoneVisual.tscn",
    "transport_hub": "TransportHubZoneVisual.tscn",
    "public_service": "PublicServiceZoneVisual.tscn",
    "nightlife": "NightlifeZoneVisual.tscn",
    "gateway": "GatewayZoneVisual.tscn",
    "mixed": "MixedZoneVisual.tscn",
}


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


def test_zone_visual_taxonomy_has_scene_and_catalog_entry() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog = render_root / "resources" / "catalogs" / "ZoneAssetCatalog.tres"
    catalog_body = catalog.read_text(encoding="utf-8")

    for zone_type in ZONE_TAXONOMY:
        scene_path = render_root / "scenes" / "zones" / ZONE_SCENES[zone_type]
        assert scene_path.is_file(), f"missing Godot zone scene for {zone_type}"
        assert f'zone_type = "{zone_type}"' in catalog_body
        assert f"res://scenes/zones/{ZONE_SCENES[zone_type]}" in catalog_body


def test_zone_catalog_aliases_cover_auto_zoning_taxonomy() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog_script = render_root / "scripts" / "assets" / "zone_asset_catalog.gd"
    body = catalog_script.read_text(encoding="utf-8")

    for expected in [
        '"university"',
        '"clinic"',
        '"marketplace"',
        '"depot"',
        '"bus_station"',
        '"government"',
        '"fallback"',
    ]:
        assert expected in body


def test_vehicle_catalog_replaces_json_default_contract() -> None:
    render_root = PROJECT_ROOT / "render"
    controller = render_root / "scripts" / "replay" / "trace_replay_controller.gd"
    body = controller.read_text(encoding="utf-8")

    assert 'asset_manifest_path := "res://resources/catalogs/VehicleAssetCatalog.tres"' in body
    assert "res://resources/configs/asset_manifest.example.json" not in body
