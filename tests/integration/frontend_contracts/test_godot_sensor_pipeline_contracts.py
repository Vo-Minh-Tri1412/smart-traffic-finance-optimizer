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
