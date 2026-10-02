from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO, cast

import pytest

from ai_quantum_hvtc.simulation.engines.sumo import (
    SumoRuntimeConfig,
    SumoRuntimeError,
    existing_net,
    prepare_existing_sumo_net_run,
    run_existing_sumo_net,
)
from ai_quantum_hvtc.simulation.engines.sumo.profiles import DEFAULT_SUMO_PROFILE


def _input_files(tmp_path: Path) -> tuple[Path, Path]:
    net = tmp_path / "district.net.xml"
    routes = tmp_path / "district.rou.xml"
    net.write_text("<net />", encoding="utf-8")
    routes.write_text("<routes />", encoding="utf-8")
    return net, routes


def _prepare(tmp_path: Path, **overrides: object):
    net, routes = _input_files(tmp_path)
    options: dict[str, object] = {
        "net": net,
        "routes": routes,
        "work_dir": tmp_path / "runs",
        "scenario_id": "normal_weekday",
        "controller_id": "fixed_time",
        "seed": 42,
        "horizon_seconds": 60,
    }
    options.update(overrides)
    return prepare_existing_sumo_net_run(**options)


@pytest.mark.parametrize(
    "scenario_id",
    [
        "",
        ".",
        "..",
        "../escape",
        r"..\escape",
        "/absolute",
        r"C:\absolute",
        "CON",
        "con.txt",
        "COM1.log",
        "scenario.",
        "scenario ",
    ],
)
def test_prepare_rejects_unsafe_scenario_id(tmp_path: Path, scenario_id: str) -> None:
    with pytest.raises(SumoRuntimeError, match="scenario_id"):
        _prepare(tmp_path, scenario_id=scenario_id)


@pytest.mark.parametrize("seed", [True, -1, 2**31])
def test_prepare_rejects_invalid_seed(tmp_path: Path, seed: object) -> None:
    with pytest.raises(SumoRuntimeError, match="seed"):
        _prepare(tmp_path, seed=seed)


@pytest.mark.parametrize("horizon_seconds", [True, 0, -1])
def test_prepare_rejects_invalid_horizon(tmp_path: Path, horizon_seconds: object) -> None:
    with pytest.raises(SumoRuntimeError, match="horizon_seconds"):
        _prepare(tmp_path, horizon_seconds=horizon_seconds)


@pytest.mark.parametrize("step_length_seconds", [True, 0, -1.0, float("inf"), float("nan")])
def test_prepare_rejects_invalid_step_length(tmp_path: Path, step_length_seconds: object) -> None:
    with pytest.raises(SumoRuntimeError, match="step_length_seconds"):
        _prepare(tmp_path, step_length_seconds=step_length_seconds)


def test_prepare_rejects_invalid_profile_values(tmp_path: Path) -> None:
    profile = replace(DEFAULT_SUMO_PROFILE, fcd_period_seconds=float("nan"))

    with pytest.raises(SumoRuntimeError, match="simulation_profile.fcd_period_seconds"):
        _prepare(tmp_path, simulation_profile=profile)


def test_prepare_reserves_final_directory_without_overwrite(tmp_path: Path) -> None:
    net, routes = _input_files(tmp_path)
    run_dir = tmp_path / "runs" / "normal_weekday" / "fixed_time"
    run_dir.mkdir(parents=True)
    sentinel = run_dir / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(SumoRuntimeError, match="already exists"):
        prepare_existing_sumo_net_run(
            net=net,
            routes=routes,
            work_dir=tmp_path / "runs",
            scenario_id="normal_weekday",
            controller_id="fixed_time",
            seed=42,
            horizon_seconds=60,
        )

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_relative_work_dir_is_resolved_before_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _prepare(tmp_path, work_dir=Path("relative-runs"))
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(existing_net, "resolve_sumo_binary", lambda _: "sumo")
    monkeypatch.setattr(existing_net.subprocess, "run", fake_run)

    run_existing_sumo_net(paths, SumoRuntimeConfig())

    assert paths.work_dir == (tmp_path / "relative-runs" / "normal_weekday" / "fixed_time")
    assert paths.work_dir.is_absolute()
    assert observed["cwd"] == paths.work_dir
    command = cast(list[str], observed["command"])
    assert command[2] == str(paths.config)
    assert paths.config.is_absolute()


def test_prepare_rejects_scenario_symlink_escape(tmp_path: Path) -> None:
    net, routes = _input_files(tmp_path)
    root = tmp_path / "runs"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "normal_weekday"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(SumoRuntimeError, match="outside"):
        prepare_existing_sumo_net_run(
            net=net,
            routes=routes,
            work_dir=root,
            scenario_id="normal_weekday",
            controller_id="fixed_time",
            seed=42,
            horizon_seconds=60,
        )
    assert not (outside / "fixed_time").exists()


def test_run_saves_logs_and_refuses_second_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _prepare(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        cast(BinaryIO, kwargs["stdout"]).write(b"SUMO out\n")
        cast(BinaryIO, kwargs["stderr"]).write(b"SUMO err\n")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(existing_net, "resolve_sumo_binary", lambda _: "sumo")
    monkeypatch.setattr(existing_net.subprocess, "run", fake_run)

    run_existing_sumo_net(paths, SumoRuntimeConfig())

    assert paths.execution_started.is_file()
    assert paths.stdout_log.read_text(encoding="utf-8") == "SUMO out\n"
    assert paths.stderr_log.read_text(encoding="utf-8") == "SUMO err\n"
    assert len(calls) == 1

    with pytest.raises(SumoRuntimeError, match="already started"):
        run_existing_sumo_net(paths, SumoRuntimeConfig())
    assert len(calls) == 1


def test_run_saves_logs_before_raising_on_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _prepare(tmp_path)
    stdout_text = "stdout-prefix\n" + "o" * 5000 + "stdout-tail"
    stderr_text = "stderr-prefix\n" + "e" * 5000 + "stderr-tail"

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        cast(BinaryIO, kwargs["stdout"]).write(stdout_text.encode("utf-8"))
        cast(BinaryIO, kwargs["stderr"]).write(stderr_text.encode("utf-8"))
        return subprocess.CompletedProcess(command, 17)

    monkeypatch.setattr(existing_net, "resolve_sumo_binary", lambda _: "sumo")
    monkeypatch.setattr(existing_net.subprocess, "run", fake_run)

    with pytest.raises(SumoRuntimeError, match="command failed") as exc_info:
        run_existing_sumo_net(paths, SumoRuntimeConfig())

    assert paths.stdout_log.read_text(encoding="utf-8") == stdout_text
    assert paths.stderr_log.read_text(encoding="utf-8") == stderr_text
    assert "stdout-prefix" not in str(exc_info.value)
    assert "stderr-prefix" not in str(exc_info.value)
    assert "stdout-tail" in str(exc_info.value)
    assert "stderr-tail" in str(exc_info.value)
    with pytest.raises(SumoRuntimeError, match="already started"):
        run_existing_sumo_net(paths, SumoRuntimeConfig())


def test_run_closes_reserved_stdout_when_stderr_log_cannot_be_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _prepare(tmp_path)
    original_open = Path.open
    stdout_handles: list[BinaryIO] = []

    def tracked_open(path: Path, *args: object, **kwargs: object):
        if path == paths.stderr_log:
            raise FileExistsError("stderr log already exists")
        handle = original_open(path, *args, **kwargs)
        if path == paths.stdout_log:
            stdout_handles.append(cast(BinaryIO, handle))
        return handle

    monkeypatch.setattr(existing_net, "resolve_sumo_binary", lambda _: "sumo")
    monkeypatch.setattr(Path, "open", tracked_open)

    with pytest.raises(SumoRuntimeError, match="output log already exists"):
        run_existing_sumo_net(paths, SumoRuntimeConfig())

    assert len(stdout_handles) == 1
    assert stdout_handles[0].closed
    assert paths.execution_started.is_file()
    with pytest.raises(SumoRuntimeError, match="already started"):
        run_existing_sumo_net(paths, SumoRuntimeConfig())


def test_run_checks_binary_before_consuming_execution_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _prepare(tmp_path)
    monkeypatch.setattr(existing_net, "resolve_sumo_binary", lambda _: None)

    with pytest.raises(SumoRuntimeError, match="was not found"):
        run_existing_sumo_net(paths, SumoRuntimeConfig())

    assert not paths.execution_started.exists()
    assert not paths.stdout_log.exists()
    assert not paths.stderr_log.exists()
