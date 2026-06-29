from __future__ import annotations

import json

from ai_quantum_hvtc.sensors import (
    DEFAULT_SYNTHETIC_YOLO_CLASSES,
    init_synthetic_yolo_dataset,
    validate_synthetic_yolo_dataset,
)


def test_init_synthetic_yolo_dataset_creates_contract_files(tmp_path) -> None:
    paths = init_synthetic_yolo_dataset(
        dataset_id="SYNTH-CV-TEST",
        output_root=tmp_path,
        source_run_id="SUMO-RUN-001",
    )

    assert paths.root == tmp_path / "SYNTH-CV-TEST"
    assert (paths.root / "images" / "train").is_dir()
    assert (paths.root / "images" / "val").is_dir()
    assert (paths.root / "labels" / "train").is_dir()
    assert (paths.root / "labels" / "val").is_dir()

    data_yaml = paths.data_yaml.read_text(encoding="utf-8")
    assert "train: images/train" in data_yaml
    assert f"0: {DEFAULT_SYNTHETIC_YOLO_CLASSES[0]}" in data_yaml

    manifest = json.loads(paths.dataset_manifest.read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "SYNTH-CV-TEST"
    assert manifest["source_type"] == "godot_synthetic_camera"

    render_manifest = json.loads(paths.render_manifest.read_text(encoding="utf-8"))
    assert render_manifest["source_run_id"] == "SUMO-RUN-001"
    assert render_manifest["renderer"] == "godot_3d"


def test_validate_template_dataset_is_ok_with_empty_dataset_warning(tmp_path) -> None:
    paths = init_synthetic_yolo_dataset(dataset_id="SYNTH-CV-TEST", output_root=tmp_path)

    result = validate_synthetic_yolo_dataset(paths.root)

    assert result.ok
    assert any("template/smoke only" in warning for warning in result.warnings)


def test_validate_warns_for_invalid_yolo_label_values(tmp_path) -> None:
    paths = init_synthetic_yolo_dataset(dataset_id="SYNTH-CV-TEST", output_root=tmp_path)
    image_path = paths.root / "images" / "train" / "frame_001.png"
    image_path.write_bytes(b"not-a-real-image-but-valid-contract-presence")
    label_path = paths.root / "labels" / "train" / "frame_001.txt"
    label_path.write_text("999 1.2 0.5 0.3 0.2\n", encoding="utf-8")

    result = validate_synthetic_yolo_dataset(paths.root)

    assert result.ok
    assert any("class_id 999 outside" in warning for warning in result.warnings)
    assert any("bbox values must be normalized" in warning for warning in result.warnings)


def test_validate_errors_when_required_folder_is_missing(tmp_path) -> None:
    paths = init_synthetic_yolo_dataset(dataset_id="SYNTH-CV-TEST", output_root=tmp_path)
    (paths.root / "labels" / "val" / ".gitkeep").unlink()
    (paths.root / "labels" / "val").rmdir()

    result = validate_synthetic_yolo_dataset(paths.root)

    assert not result.ok
    assert any("Missing folder" in error for error in result.errors)
