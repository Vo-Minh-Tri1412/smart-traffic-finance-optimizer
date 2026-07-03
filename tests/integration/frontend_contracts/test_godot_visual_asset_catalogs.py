from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ZONE_TAXONOMY = [
    "neutral",
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
    "neutral": "NeutralZoneVisual.tscn",
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


def test_vehicle_scenes_bind_imported_glb_visual_assets_as_scene_properties() -> None:
    render_root = PROJECT_ROOT / "render"
    vehicle_scene_assets = {
        "AmbulanceVehicle.tscn": "res://imported_assets/vehicles/ambulance.glb",
        "BusVehicle.tscn": "res://imported_assets/vehicles/van.glb",
        "HeavyTruckVehicle.tscn": "res://imported_assets/vehicles/truck.glb",
        "LightTruckVehicle.tscn": "res://imported_assets/vehicles/delivery.glb",
        "MotorbikeVehicle.tscn": "res://imported_assets/vehicles/hatchback-sports.glb",
        "PrivateCarVehicle.tscn": "res://imported_assets/vehicles/sedan.glb",
        "TaxiVehicle.tscn": "res://imported_assets/vehicles/taxi.glb",
    }

    for scene_name, asset_path in vehicle_scene_assets.items():
        body = (render_root / "scenes" / "vehicles" / scene_name).read_text(encoding="utf-8")
        assert asset_path in body
        assert "visual_asset_scene = ExtResource" in body
        assert "visual_asset_override_material = ExtResource" in body


def test_vehicle_concrete_scenes_do_not_save_generated_visual_asset_children() -> None:
    render_root = PROJECT_ROOT / "render"

    for scene_path in (render_root / "scenes" / "vehicles").glob("*Vehicle.tscn"):
        body = scene_path.read_text(encoding="utf-8")
        assert 'name="VisualAsset"' not in body


def test_vehicle_and_zone_bases_expose_scene_level_tool_asset_fields() -> None:
    render_root = PROJECT_ROOT / "render"
    vehicle_base = render_root / "scripts" / "replay" / "vehicle_base.gd"
    zone_base = render_root / "scripts" / "zones" / "zone_visual_base.gd"

    vehicle_body = vehicle_base.read_text(encoding="utf-8")
    zone_body = zone_base.read_text(encoding="utf-8")

    assert "@tool" in vehicle_body
    assert "@export var visual_asset_scene" in vehicle_body
    assert "@export var visual_asset_scale" in vehicle_body
    assert "@export var visual_asset_override_material" in vehicle_body
    assert "func has_scene_visual_asset_configured" in vehicle_body

    assert "@tool" in zone_body
    assert "@export var ground_material" in zone_body
    assert "@export var building_scenes" in zone_body
    assert "@export var building_density" in zone_body
    assert "func _effective_zone_entry" in zone_body


def test_zone_overlay_uses_polygon_geometry_when_available() -> None:
    render_root = PROJECT_ROOT / "render"
    renderer = render_root / "scripts" / "zones" / "semantic_overlay_renderer.gd"
    zone_base = render_root / "scripts" / "zones" / "zone_visual_base.gd"
    world = render_root / "scripts" / "world" / "district_replay_world.gd"
    geometry = render_root / "scripts" / "world" / "sumo_net_geometry_data.gd"

    renderer_body = renderer.read_text(encoding="utf-8")
    zone_body = zone_base.read_text(encoding="utf-8")
    world_body = world.read_text(encoding="utf-8")
    geometry_body = geometry.read_text(encoding="utf-8")

    assert "func _zone_world_polygon" in renderer_body
    assert "configure_zone_polygon" in renderer_body
    assert "func configure_zone_polygon" in zone_body
    assert "func _ground_polygon_mesh" in zone_body
    assert "Geometry2D.triangulate_polygon" in zone_body
    assert "func world_polygon_for_geo_coordinates" in world_body
    assert "func sumo_point_for_lon_lat" in geometry_body
    assert "_parse_location" in geometry_body


def test_vehicle_factory_prefers_scene_assets_and_keeps_catalog_fallback() -> None:
    render_root = PROJECT_ROOT / "render"
    factory = render_root / "scripts" / "assets" / "vehicle_factory.gd"
    factory_body = factory.read_text(encoding="utf-8")

    assert "has_scene_visual_asset_configured" in factory_body
    assert "apply_external_visual_asset" in factory_body
    assert "_attach_catalog_visual_asset" in factory_body
