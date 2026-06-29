from __future__ import annotations

import pytest

from scripts.render.godot_synthetic_cv_smoke import find_godot_executable, main


def test_godot_synthetic_cv_smoke_runs_when_godot_is_available(tmp_path) -> None:
    godot_exe = find_godot_executable()
    if godot_exe is None:
        pytest.skip("Godot executable is not available in this environment")

    output_root = tmp_path / "cv_yolo"
    code = main(
        [
            "--dataset-id",
            "SYNTH-CV-GODOT-PYTEST",
            "--output-root",
            str(output_root),
            "--godot-exe",
            str(godot_exe),
            "--force",
        ]
    )

    dataset_root = output_root / "SYNTH-CV-GODOT-PYTEST"
    assert code == 0
    assert (dataset_root / "images" / "train" / "godot_smoke_train_000.png").is_file()
    assert (dataset_root / "labels" / "train" / "godot_smoke_train_000.txt").is_file()
    assert (dataset_root / "images" / "val" / "godot_smoke_val_000.png").is_file()
    assert (dataset_root / "labels" / "val" / "godot_smoke_val_000.txt").is_file()
