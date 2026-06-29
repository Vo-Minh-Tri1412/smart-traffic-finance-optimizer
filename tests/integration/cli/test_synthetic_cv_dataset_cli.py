from __future__ import annotations

from pathlib import Path

from scripts.cloud.drive_desktop_sync import main as drive_sync_main
from scripts.data.prepare_synthetic_cv_dataset import main as prepare_dataset_main


def test_prepare_synthetic_cv_dataset_cli_init_and_validate(tmp_path) -> None:
    output_root = tmp_path / "cv_yolo"

    init_code = prepare_dataset_main(
        [
            "--dataset-id",
            "SYNTH-CV-CLI",
            "--output-root",
            str(output_root),
            "--init-template",
        ]
    )
    validate_code = prepare_dataset_main(
        [
            "--dataset-root",
            str(output_root / "SYNTH-CV-CLI"),
            "--validate",
        ]
    )

    assert init_code == 0
    assert validate_code == 0


def test_drive_sync_push_dataset_dry_run_and_apply(tmp_path) -> None:
    source = tmp_path / "source_dataset"
    source.mkdir()
    (source / "dataset_manifest.json").write_text(
        '{"dataset_id":"SYNTH-CV-CLI"}\n', encoding="utf-8"
    )
    drive_root = tmp_path / "drive_data_hub"
    drive_root.mkdir()

    dry_run_code = drive_sync_main(
        [
            "--drive-root",
            str(drive_root),
            "push-dataset",
            "--stream",
            "cv_yolo",
            "--dataset-id",
            "SYNTH-CV-CLI",
            "--source",
            str(source),
        ]
    )
    apply_code = drive_sync_main(
        [
            "--drive-root",
            str(drive_root),
            "--apply",
            "push-dataset",
            "--stream",
            "cv_yolo",
            "--dataset-id",
            "SYNTH-CV-CLI",
            "--source",
            str(source),
        ]
    )

    target_file = (
        Path(drive_root)
        / "02_Processed_Data"
        / "cv_yolo"
        / "SYNTH-CV-CLI"
        / "dataset_manifest.json"
    )
    assert dry_run_code == 0
    assert apply_code == 0
    assert target_file.read_text(encoding="utf-8") == '{"dataset_id":"SYNTH-CV-CLI"}\n'
