from __future__ import annotations

import json
from pathlib import Path

from ai_quantum_hvtc.simulation.traces.versions import RENDER_BRIDGE_SCHEMA_VERSIONS
from scripts.render.godot_render_bridge_quality_report import build_quality_report

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_render_bridge_architecture_docs_exist_and_name_core_patterns() -> None:
    architecture = PROJECT_ROOT / "docs" / "02_ARCHITECTURE" / "SUMO_RENDER_BRIDGE_FRAMEWORK.md"
    contracts = PROJECT_ROOT / "docs" / "02_ARCHITECTURE" / "RENDER_BRIDGE_CONTRACTS.md"
    refactor = PROJECT_ROOT / "docs" / "02_ARCHITECTURE" / "GODOT_BRIDGE_REFACTOR_PLAN.md"

    for path in [architecture, contracts, refactor]:
        assert path.is_file(), f"missing render bridge doc: {path}"

    body = architecture.read_text(encoding="utf-8")
    for expected in [
        "SUMO2Unity",
        "Sumonity",
        "CARLA SUMO co-simulation",
        "SumoUE4",
        "Authority ownership",
        "SumoRenderBridge",
    ]:
        assert expected in body


def test_render_bridge_schema_versions_are_declared_in_python_and_godot() -> None:
    expected_versions = {
        "geometry_manifest": "geometry_manifest.v1",
        "vehicle_trace": "vehicle_trace.v2",
        "visibility_trace": "visibility_trace.v1",
        "traffic_light_trace": "traffic_light_trace.v1",
        "semantic_overlay": "semantic_overlay.v2",
        "event_trace": "event_trace.v1",
        "render_run_manifest": "render_run_manifest.v1",
        "sensor_dataset_manifest": "sensor_dataset_manifest.v1",
    }
    assert expected_versions == RENDER_BRIDGE_SCHEMA_VERSIONS

    godot_versions = (
        PROJECT_ROOT / "render" / "scripts" / "contracts" / "schema_versions.gd"
    ).read_text(encoding="utf-8")
    for version in expected_versions.values():
        assert version in godot_versions


def test_godot_bridge_and_visual_style_files_exist() -> None:
    required_paths = [
        PROJECT_ROOT / "render" / "scripts" / "bridge" / "sumo_render_bridge.gd",
        PROJECT_ROOT / "render" / "scripts" / "traffic" / "traffic_light_state_layer.gd",
        PROJECT_ROOT / "render" / "scripts" / "assets" / "road_style_catalog.gd",
        PROJECT_ROOT / "render" / "scripts" / "assets" / "road_style_entry.gd",
        PROJECT_ROOT / "render" / "scripts" / "roads" / "road_scene_builder.gd",
        PROJECT_ROOT / "render" / "scripts" / "roads" / "road_visual_root.gd",
        PROJECT_ROOT / "render" / "scripts" / "roads" / "lane_visual_base.gd",
        PROJECT_ROOT / "render" / "resources" / "catalogs" / "RoadStyleCatalog.tres",
        PROJECT_ROOT / "render" / "scenes" / "roads" / "RoadVisualRoot.tscn",
        PROJECT_ROOT / "render" / "scenes" / "roads" / "LaneVisualBase.tscn",
    ]
    missing = [path for path in required_paths if not path.is_file()]
    assert not missing

    main_scene = (PROJECT_ROOT / "render" / "scenes" / "main" / "Main.tscn").read_text(
        encoding="utf-8"
    )
    assert "SumoRenderBridge" in main_scene
    assert "TrafficLightStateLayer" in main_scene

    world_script = (
        PROJECT_ROOT / "render" / "scripts" / "world" / "district_replay_world.gd"
    ).read_text(encoding="utf-8")
    assert "RoadSceneBuilder" in world_script
    assert "render_lane_as_scenes" in world_script
    assert "SUMO lane scene builder" in world_script
    assert "editor_preview_enabled" in world_script

    overlay_script = (
        PROJECT_ROOT / "render" / "scripts" / "zones" / "semantic_overlay_renderer.gd"
    ).read_text(encoding="utf-8")
    assert "editor_preview_enabled" in overlay_script


def test_trace_replay_controller_keeps_vehicle_selection_out_of_replay_logic() -> None:
    body = (
        PROJECT_ROOT / "render" / "scripts" / "replay" / "trace_replay_controller.gd"
    ).read_text(encoding="utf-8")

    assert "VehicleFactory" in body
    assert "VehiclePool" in body
    assert 'vehicle_type == "BUS"' not in body
    assert 'vehicle_type == "PRIVATE_CAR"' not in body


def test_render_bridge_quality_report_flags_alignment_and_fallbacks() -> None:
    summary = {
        "loaded_frames": 3,
        "spawned_vehicle_count": 2,
        "largest_active_vehicle_count": 2,
        "off_lane_vehicle_count": 1,
        "max_off_lane_distance_m": 12.5,
        "lane_count": 10,
        "road_count": 10,
        "intersection_count": 4,
        "rendered_lane_count": 10,
        "rendered_junction_count": 4,
        "vehicle_scene_count": 3,
        "vehicle_fallback_spawn_count": 1,
        "zone_overlay": {"spawned_zone_count": 2, "fallback_zone_count": 1},
    }

    report = build_quality_report(summary)

    assert not report["quality_passed"]
    assert "vehicles_outside_sumo_lane_geometry" in report["warnings"]
    assert "vehicle_asset_fallback_used" in report["warnings"]
    assert "zone_asset_fallback_used" in report["warnings"]
    json.dumps(report)
