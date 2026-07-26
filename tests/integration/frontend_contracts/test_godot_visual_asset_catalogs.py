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
        render_root / "resources" / "catalogs" / "RoadStyleCatalog.tres",
        render_root / "resources" / "catalogs" / "TrafficLightAssetCatalog.tres",
        render_root / "scripts" / "assets" / "vehicle_asset_catalog.gd",
        render_root / "scripts" / "assets" / "zone_asset_catalog.gd",
        render_root / "scripts" / "assets" / "building_placement_profile.gd",
        render_root / "scripts" / "assets" / "road_style_catalog.gd",
        render_root / "scripts" / "assets" / "traffic_light_asset_catalog.gd",
        render_root / "scripts" / "assets" / "roadside_prop_entry.gd",
        render_root / "scripts" / "zones" / "semantic_overlay_renderer.gd",
        render_root / "scripts" / "zones" / "semantic_heatmap_renderer.gd",
        render_root / "scenes" / "zones" / "ZoneVisualBase.tscn",
        render_root / "scenes" / "traffic" / "TrafficLightVisualBase.tscn",
        PROJECT_ROOT / "scripts" / "render" / "godot_zone_heatmap_preview.py",
        render_root
        / "resources"
        / "profiles"
        / "building_placement"
        / "residential_building_profile.tres",
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


def test_zone_catalog_uses_building_placement_profiles() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog = render_root / "resources" / "catalogs" / "ZoneAssetCatalog.tres"
    zone_base = render_root / "scripts" / "zones" / "zone_visual_base.gd"
    profile_script = render_root / "scripts" / "assets" / "building_placement_profile.gd"
    heatmap_script = PROJECT_ROOT / "scripts" / "maps" / "render_buildable_zone_heatmap.py"

    catalog_body = catalog.read_text(encoding="utf-8")
    zone_body = zone_base.read_text(encoding="utf-8")
    profile_body = profile_script.read_text(encoding="utf-8")
    heatmap_body = heatmap_script.read_text(encoding="utf-8")

    for expected in [
        "residential_building_profile.tres",
        "commercial_building_profile.tres",
        "education_building_profile.tres",
        "healthcare_building_profile.tres",
        "industrial_building_profile.tres",
        "neutral_building_profile.tres",
    ]:
        assert expected in catalog_body

    assert "@export var placement_profile" in zone_body
    assert "func _desired_building_count" in zone_body
    assert "Geometry2D.is_point_in_polygon" in zone_body
    assert "target_coverage_ratio" in profile_body
    assert "buildable_semantic_overlay.generated.json" in heatmap_body


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
    heatmap_renderer = render_root / "scripts" / "zones" / "semantic_heatmap_renderer.gd"
    zone_base = render_root / "scripts" / "zones" / "zone_visual_base.gd"
    world = render_root / "scripts" / "world" / "district_replay_world.gd"
    geometry = render_root / "scripts" / "world" / "sumo_net_geometry_data.gd"
    capture = render_root / "scripts" / "replay" / "capture_render_preview.gd"
    heatmap_preview = PROJECT_ROOT / "scripts" / "render" / "godot_zone_heatmap_preview.py"

    renderer_body = renderer.read_text(encoding="utf-8")
    heatmap_body = heatmap_renderer.read_text(encoding="utf-8")
    zone_body = zone_base.read_text(encoding="utf-8")
    world_body = world.read_text(encoding="utf-8")
    geometry_body = geometry.read_text(encoding="utf-8")
    capture_body = capture.read_text(encoding="utf-8")
    heatmap_preview_body = heatmap_preview.read_text(encoding="utf-8")

    assert "func _zone_world_polygons" in renderer_body
    assert "world_polygon_for_sumo_coordinates" in renderer_body
    assert "configure_zone_polygon" in renderer_body
    assert "func configure_zone_polygon" in zone_body
    assert "func _ground_polygon_mesh" in zone_body
    assert "Geometry2D.triangulate_polygon" in zone_body
    assert "func world_polygon_for_geo_coordinates" in world_body
    assert "func world_polygon_for_sumo_coordinates" in world_body
    assert "func sumo_point_for_lon_lat" in geometry_body
    assert "_parse_location" in geometry_body
    assert "class_name SemanticHeatmapRenderer" in heatmap_body
    assert "func render_heatmap" in heatmap_body
    assert "render_neutral_zones := false" in heatmap_body
    assert "_build_zone_type_mesh" in heatmap_body
    assert "zone_render_mode" in capture_body
    assert "godot_zone_heatmap" in heatmap_preview_body
    assert "--zone-render-mode" in heatmap_preview_body


def test_vehicle_factory_prefers_scene_assets_and_keeps_catalog_fallback() -> None:
    render_root = PROJECT_ROOT / "render"
    factory = render_root / "scripts" / "assets" / "vehicle_factory.gd"
    factory_body = factory.read_text(encoding="utf-8")

    assert "has_scene_visual_asset_configured" in factory_body
    assert "apply_external_visual_asset" in factory_body
    assert "_attach_catalog_visual_asset" in factory_body


def test_road_style_catalog_exposes_roadside_asset_slots() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog = render_root / "resources" / "catalogs" / "RoadStyleCatalog.tres"
    entry_script = render_root / "scripts" / "assets" / "road_style_entry.gd"
    lane_visual = render_root / "scripts" / "roads" / "lane_visual_base.gd"
    world = render_root / "scripts" / "world" / "district_replay_world.gd"

    catalog_body = catalog.read_text(encoding="utf-8")
    entry_body = entry_script.read_text(encoding="utf-8")
    lane_body = lane_visual.read_text(encoding="utf-8")
    world_body = world.read_text(encoding="utf-8")

    assert '@export_group("Roadside Assets")' in entry_body
    assert "@export var roadside_prop_scenes" in entry_body
    assert "@export var roadside_prop_entries" in entry_body
    assert "res://imported_assets/traffic_lights/light-square.glb" in catalog_body
    assert "res://imported_assets/street_furniture/signs/sign-highway.glb" in catalog_body
    for role in ["service", "residential", "arterial", "pedestrian"]:
        assert f'road_role = "{role}"' in catalog_body
    assert "RoadsideProps" in lane_body
    assert "func _build_roadside_props" in lane_body
    assert "func _fit_roadside_prop_to_target_size" in lane_body
    assert "func roadside_prop_count" in lane_body
    assert "func _road_role_for_lane" in world_body
    assert "rendered_road_role_counts" in world_body


def test_zone_placement_uses_real_footprints_and_spatial_road_clearance() -> None:
    render_root = PROJECT_ROOT / "render"
    zone = (render_root / "scripts" / "zones" / "zone_visual_base.gd").read_text(encoding="utf-8")
    world = (render_root / "scripts" / "world" / "district_replay_world.gd").read_text(
        encoding="utf-8"
    )
    geometry = (render_root / "scripts" / "world" / "sumo_net_geometry_data.gd").read_text(
        encoding="utf-8"
    )

    assert "_node_local_footprint_rect" in zone
    assert "_footprint_within_zone" in zone
    assert "_footprint_overlaps_existing" in zone
    assert "_footprint_respects_road_clearance" in zone
    assert "is_world_position_clear_of_roads" in world
    assert "is_point_clear_of_roads_m" in geometry
    assert "ROAD_CLEARANCE_CELL_SIZE_M" in geometry


def test_main_renderer_uses_camera_lod_and_fly_preview() -> None:
    render_root = PROJECT_ROOT / "render"
    world = render_root / "scripts" / "world" / "district_replay_world.gd"
    camera = render_root / "scripts" / "world" / "preview_camera_controller.gd"
    main_scene = render_root / "scenes" / "main" / "Main.tscn"

    world_body = world.read_text(encoding="utf-8")
    camera_body = camera.read_text(encoding="utf-8")
    main_body = main_scene.read_text(encoding="utf-8")

    assert "@export var use_camera_road_lod := true" in world_body
    assert "func _build_sumo_lod_region" in world_body
    assert "func road_lod_summary" in world_body
    assert "@export var use_fly_preview := true" in camera_body
    assert "func _handle_fly_keyboard" in camera_body
    assert "auto_fit_on_ready = false" in main_body
    assert "world_scale = 1.0" in main_body
    assert "use_camera_road_lod = true" in main_body
    assert "max_visual_zones" not in main_body
    assert "max_neutral_visual_zones" not in main_body
    assert "zone_lod_prefetch_distance_m" in main_body
    overlay_body = (render_root / "scripts" / "zones" / "semantic_overlay_renderer.gd").read_text(
        encoding="utf-8"
    )
    assert "camera_corridor_incremental" in overlay_body


def test_traffic_light_visual_catalog_is_wired_into_main_scene() -> None:
    render_root = PROJECT_ROOT / "render"
    catalog = render_root / "resources" / "catalogs" / "TrafficLightAssetCatalog.tres"
    visual_layer = render_root / "scripts" / "traffic" / "traffic_light_visual_layer.gd"
    world = render_root / "scripts" / "world" / "district_replay_world.gd"
    main_scene = render_root / "scenes" / "main" / "Main.tscn"

    catalog_body = catalog.read_text(encoding="utf-8")
    visual_layer_body = visual_layer.read_text(encoding="utf-8")
    world_body = world.read_text(encoding="utf-8")
    main_body = main_scene.read_text(encoding="utf-8")

    assert "TrafficLightAssetCatalog" in catalog_body
    assert "res://imported_assets/traffic_lights/light-square.glb" in catalog_body
    assert "TrafficLightVisualBase.tscn" in visual_layer_body
    assert "func traffic_light_junction_world_points" in world_body
    assert "rendered_roadside_prop_count" in world_body
    assert "TrafficLightVisualLayer" in main_body
