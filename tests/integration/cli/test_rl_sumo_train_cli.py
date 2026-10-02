from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.training import rl_sumo_train
from scripts.training.rl_sumo_train import main

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")
PROFILE_PATH = Path("configs/training/rl_reward_profile_v0.example.toml")


def test_rl_sumo_train_dry_run_reports_reward_contract(capsys: object, tmp_path: Path) -> None:
    out_dir = tmp_path / "rl"
    exit_code = main(
        [
            "--spec",
            str(SPEC_PATH),
            "--scenario",
            "normal_weekday",
            "--reward-profile",
            str(PROFILE_PATH),
            "--out-dir",
            str(out_dir),
            "--dry-run",
            "--acknowledge-pending-hard-constraints",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "dry_run"' in captured.out
    assert '"reward_profile_status": "draft"' in captured.out
    assert "hard constraints require" in captured.out
    assert "emergency_vehicle_preemption" in captured.out
    assert not out_dir.exists()


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


def test_rl_sumo_train_never_starts_with_acknowledged_emergency_filter_gap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "rl"

    def fail_if_training_starts(*args: object, **kwargs: object) -> None:
        raise AssertionError("training setup must not run while emergency filtering is pending")

    monkeypatch.setattr(rl_sumo_train, "export_sumo_project", fail_if_training_starts)
    monkeypatch.setattr(rl_sumo_train, "build_sumo_net", fail_if_training_starts)
    monkeypatch.setattr(rl_sumo_train, "_build_training_env", fail_if_training_starts)
    monkeypatch.setattr(rl_sumo_train, "_build_policy", fail_if_training_starts)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--spec",
                str(SPEC_PATH),
                "--scenario",
                "normal_weekday",
                "--reward-profile",
                str(PROFILE_PATH),
                "--out-dir",
                str(out_dir),
                "--train",
                "--allow-local-training",
                "--allow-draft-reward",
                "--acknowledge-pending-hard-constraints",
            ]
        )

    assert "hard constraints require" in str(exc_info.value)
    assert "emergency_vehicle_preemption" in str(exc_info.value)
    assert not out_dir.exists()


def test_duplicate_partial_training_output_fails_before_export_and_preserves_sentinel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "partial-run"
    out_dir.mkdir()
    sentinel = out_dir / "reviewed-checkpoint.bin"
    sentinel.write_bytes(b"preserve this prior output")
    export_called = False

    monkeypatch.setattr(rl_sumo_train, "training_blockers", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        rl_sumo_train,
        "_load_map_economic_context",
        lambda _args: (None, None, []),
    )

    def fail_if_export(*_args: object, **_kwargs: object) -> None:
        nonlocal export_called
        export_called = True
        raise AssertionError("existing output must fail before SUMO export")

    monkeypatch.setattr(rl_sumo_train, "export_sumo_project", fail_if_export)

    with pytest.raises(SystemExit, match="refusing to overwrite or resume"):
        rl_sumo_train.train(_training_args(out_dir))

    assert not export_called
    assert sentinel.read_bytes() == b"preserve this prior output"
    assert sorted(path.name for path in out_dir.iterdir()) == [sentinel.name]


def test_training_reserves_output_before_export_and_leaves_partial_run_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "new-run"
    export_called = False

    monkeypatch.setattr(rl_sumo_train, "training_blockers", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        rl_sumo_train,
        "_load_map_economic_context",
        lambda _args: (None, None, []),
    )

    def stop_at_export(**_kwargs: object) -> None:
        nonlocal export_called
        export_called = True
        assert out_dir.is_dir()
        assert {path.name for path in out_dir.iterdir()} == {"sumo", "models", "logs"}
        raise RuntimeError("stop after verifying reservation")

    monkeypatch.setattr(rl_sumo_train, "export_sumo_project", stop_at_export)

    with pytest.raises(RuntimeError, match="stop after verifying reservation"):
        rl_sumo_train.train(_training_args(out_dir))

    assert export_called
    assert out_dir.is_dir()
    assert {path.name for path in out_dir.iterdir()} == {"sumo", "models", "logs"}


def _training_args(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        cloud_runtime="colab",
        allow_local_training=False,
        spec=SPEC_PATH,
        scenario="normal_weekday",
        reward_profile=PROFILE_PATH,
        allow_draft_reward=True,
        acknowledge_pending_hard_constraints=True,
        map_economic_profile=None,
        allow_unreviewed_map_economics=False,
        out_dir=str(out_dir),
        run_id="TASK-104-TEST",
        seed=42,
        total_timesteps=1,
        agent_mode="multi_agent",
        memory="none",
        frame_stack_size=4,
        num_envs=1,
        rollout_steps=1,
        yellow_time=2,
        min_green=5,
        max_green=50,
    )
