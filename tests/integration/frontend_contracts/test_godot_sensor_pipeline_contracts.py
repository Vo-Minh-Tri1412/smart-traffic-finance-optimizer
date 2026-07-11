from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_godot_sensor_catalogs_are_editor_resources() -> None:
    camera_catalog = PROJECT_ROOT / "render" / "resources" / "catalogs" / "CameraRigCatalog.tres"
    label_mapping = PROJECT_ROOT / "render" / "resources" / "catalogs" / "LabelMappingCatalog.tres"

    camera_text = camera_catalog.read_text(encoding="utf-8")
    label_text = label_mapping.read_text(encoding="utf-8")

    assert "camera_rig_catalog.gd" in camera_text
    assert "CAM_INTERSECTION_HIGH_01" in camera_text
    assert "CAM_HOSPITAL_GATE_01" in camera_text
    assert "label_mapping_catalog.gd" in label_text
    assert "PRIVATE_CAR" in label_text
    assert "AMBULANCE" in label_text


def test_godot_sensor_pipeline_entrypoints_exist() -> None:
    expected_paths = [
        "render/scenes/sensors/DetectionCamera3D.tscn",
        "render/resources/configs/camera_calibration.v1.example.json",
        "render/scripts/sensors/camera_calibration_loader.gd",
        "render/scripts/sensors/detection_camera_3d.gd",
        "render/scripts/sensors/object_id_registry.gd",
        "render/scripts/sensors/sensor_render_pipeline.gd",
        "render/scripts/sensors/sensor_dataset_writer.gd",
        "render/scripts/sensors/run_sensor_dataset_smoke.gd",
        "scripts/render/godot_sensor_dataset_smoke.py",
    ]
    for relative_path in expected_paths:
        assert (PROJECT_ROOT / relative_path).is_file(), relative_path


def test_sensor_pipeline_keeps_json_outputs_cross_system() -> None:
    writer = (
        PROJECT_ROOT / "render" / "scripts" / "sensors" / "sensor_dataset_writer.gd"
    ).read_text(encoding="utf-8")
    assert "sensor_frame_manifest.jsonl" in writer
    assert "render_manifest.json" in writer
    assert "data.yaml" in writer


def test_godot_sensor_calibration_and_vehicle_proxy_are_renderer_independent() -> None:
    loader = (
        PROJECT_ROOT / "render" / "scripts" / "sensors" / "camera_calibration_loader.gd"
    ).read_text(encoding="utf-8")
    camera = (PROJECT_ROOT / "render" / "scripts" / "sensors" / "detection_camera_3d.gd").read_text(
        encoding="utf-8"
    )
    vehicle_scene = (
        PROJECT_ROOT / "render" / "scenes" / "vehicles" / "VehicleBase.tscn"
    ).read_text(encoding="utf-8")
    vehicle = (PROJECT_ROOT / "render" / "scripts" / "replay" / "vehicle_base.gd").read_text(
        encoding="utf-8"
    )
    world = (PROJECT_ROOT / "render" / "scripts" / "world" / "district_replay_world.gd").read_text(
        encoding="utf-8"
    )

    assert 'SCHEMA_VERSION := "camera_calibration.v1"' in loader
    assert "configure_from_calibration" in camera
    assert "world_position_for_sumo_coordinate" in camera
    assert "PhysicalProxy" in vehicle_scene
    assert "world_position_for_trace_vehicle" in vehicle
    assert "_fit_active_visual_asset_to_physical_proxy" in vehicle
    assert "visual_physical_fit_error_world_units" in vehicle
    assert "SUMO FCD x/y already include the sublane displacement" in world
