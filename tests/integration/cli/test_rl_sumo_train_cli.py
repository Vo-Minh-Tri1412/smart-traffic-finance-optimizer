from __future__ import annotations

from pathlib import Path

from scripts.training.rl_sumo_train import main

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")
PROFILE_PATH = Path("configs/training/rl_reward_profile_v0.example.toml")


def test_rl_sumo_train_dry_run_reports_reward_contract(capsys: object, tmp_path: Path) -> None:
    exit_code = main(
        [
            "--spec",
            str(SPEC_PATH),
            "--scenario",
            "normal_weekday",
            "--reward-profile",
            str(PROFILE_PATH),
            "--out-dir",
            str(tmp_path / "rl"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "dry_run"' in captured.out
    assert '"reward_profile_status": "draft"' in captured.out
    assert "hard constraints require" in captured.out


def test_rl_sumo_train_rejects_train_and_dry_run_together(tmp_path: Path) -> None:
    try:
        main(
            [
                "--spec",
                str(SPEC_PATH),
                "--scenario",
                "normal_weekday",
                "--reward-profile",
                str(PROFILE_PATH),
                "--out-dir",
                str(tmp_path / "rl"),
                "--dry-run",
                "--train",
            ]
        )
    except SystemExit as exc:
        assert str(exc) == "Choose either --dry-run or --train, not both."
    else:
        raise AssertionError("expected SystemExit")
