from __future__ import annotations

import math
import re
import subprocess
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from dataclasses import dataclass
from numbers import Number
from pathlib import Path, PureWindowsPath
from typing import SupportsFloat, cast

from ai_quantum_hvtc.simulation.engines.sumo.config import (
    SumoRuntimeConfig,
    resolve_sumo_binary,
)
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.profiles import (
    DEFAULT_SUMO_PROFILE,
    SumoSimulationProfile,
)

_MAX_SEED = 2**31 - 1
_LOG_TAIL_BYTES = 4096
_PORTABLE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RESERVED_WINDOWS_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}"
    for prefix in ("COM", "LPT")
    for number in range(1, 10)
}


@dataclass(frozen=True)
class ExistingSumoNetRunPaths:
    work_dir: Path
    net: Path
    routes: Path
    additional: Path
    config: Path
    tripinfo: Path
    summary: Path
    statistic: Path
    edge_data: Path
    fcd: Path
    controller_log: Path
    simulation_profile: SumoSimulationProfile

    @property
    def execution_started(self) -> Path:
        return self.work_dir / ".execution_started"

    @property
    def stdout_log(self) -> Path:
        return self.work_dir / "stdout.log"

    @property
    def stderr_log(self) -> Path:
        return self.work_dir / "stderr.log"


def prepare_existing_sumo_net_run(
    *,
    net: Path,
    routes: Path,
    work_dir: Path,
    scenario_id: str,
    controller_id: str,
    seed: int,
    horizon_seconds: int,
    step_length_seconds: float = 1.0,
    simulation_profile: SumoSimulationProfile | None = None,
) -> ExistingSumoNetRunPaths:
    if controller_id != "fixed_time":
        raise SumoRuntimeError(
            "Existing SUMO net V1 supports controller 'fixed_time' only; "
            "rule_based/RL should wait until the District 7 demand path is stable."
        )
    _validate_portable_component(scenario_id, name="scenario_id")
    _validate_seed(seed)
    _validate_horizon(horizon_seconds)
    step_value = _validate_positive_number(step_length_seconds, "step_length_seconds")

    profile = simulation_profile or DEFAULT_SUMO_PROFILE
    _validate_profile(profile)
    if not net.is_file():
        raise SumoRuntimeError(f"SUMO net file not found: {net}")
    if not routes.is_file():
        raise SumoRuntimeError(f"SUMO route file not found: {routes}")

    if (
        simulation_profile is None
        and step_value != DEFAULT_SUMO_PROFILE.step_length_seconds
    ):
        profile = SumoSimulationProfile(
            profile_id="custom",
            step_length_seconds=step_value,
            action_step_length_seconds=DEFAULT_SUMO_PROFILE.action_step_length_seconds,
            fcd_period_seconds=DEFAULT_SUMO_PROFILE.fcd_period_seconds,
        )
        _validate_profile(profile)

    run_dir = _reserve_run_directory(work_dir, scenario_id, controller_id)
    paths = ExistingSumoNetRunPaths(
        work_dir=run_dir,
        net=net.resolve(),
        routes=routes.resolve(),
        additional=run_dir / "additional.xml",
        config=run_dir / "district.sumocfg",
        tripinfo=run_dir / "tripinfo.xml",
        summary=run_dir / "summary.xml",
        statistic=run_dir / "statistic.xml",
        edge_data=run_dir / "edge_data.xml",
        fcd=run_dir / "fcd.xml",
        controller_log=run_dir / "controller_interventions.jsonl",
        simulation_profile=profile,
    )
    _write_additional(paths, step_length_seconds=profile.step_length_seconds)
    _write_config(
        paths,
        seed=seed,
        horizon_seconds=horizon_seconds,
        step_length_seconds=profile.step_length_seconds,
    )
    with paths.controller_log.open("x", encoding="utf-8"):
        pass
    return paths


def run_existing_sumo_net(paths: ExistingSumoNetRunPaths, config: SumoRuntimeConfig) -> None:
    sumo = resolve_sumo_binary(config.sumo_binary)
    if sumo is None:
        raise SumoRuntimeError(
            f"SUMO binary '{config.sumo_binary}' was not found. Install SUMO or set SUMO_HOME."
        )
    command = [
        sumo,
        "-c",
        str(paths.config),
        "--no-step-log",
        "true",
        "--no-warnings",
        "true",
        *paths.simulation_profile.command_args(),
    ]
    try:
        with paths.execution_started.open("x", encoding="utf-8"):
            pass
    except FileExistsError as exc:
        raise SumoRuntimeError(
            f"SUMO existing-net run has already started: {paths.work_dir}"
        ) from exc
    except OSError as exc:
        raise SumoRuntimeError(
            f"could not reserve SUMO execution marker {paths.execution_started}: {exc}"
        ) from exc

    with ExitStack() as log_stack:
        try:
            stdout_handle = log_stack.enter_context(paths.stdout_log.open("xb"))
            stderr_handle = log_stack.enter_context(paths.stderr_log.open("xb"))
        except FileExistsError as exc:
            raise SumoRuntimeError(
                f"SUMO output log already exists in {paths.work_dir}"
            ) from exc
        except OSError as exc:
            raise SumoRuntimeError(
                f"could not reserve SUMO output logs in {paths.work_dir}: {exc}"
            ) from exc

        completed = subprocess.run(
            command,
            cwd=paths.work_dir,
            check=False,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
    if completed.returncode != 0:
        raise SumoRuntimeError(
            "SUMO existing-net command failed:\n"
            f"command: {' '.join(command)}\n"
            f"stdout tail: {_read_log_tail(paths.stdout_log)}\n"
            f"stderr tail: {_read_log_tail(paths.stderr_log)}"
        )


def _write_additional(paths: ExistingSumoNetRunPaths, *, step_length_seconds: float) -> None:
    root = ET.Element("additional")
    ET.SubElement(
        root,
        "edgeData",
        {
            "id": "edge_metrics",
            "file": paths.edge_data.name,
            "period": f"{step_length_seconds:g}",
            "excludeEmpty": "true",
        },
    )
    _write_xml(root, paths.additional)


def _write_config(
    paths: ExistingSumoNetRunPaths,
    *,
    seed: int,
    horizon_seconds: int,
    step_length_seconds: float,
) -> None:
    root = ET.Element("configuration")
    input_node = ET.SubElement(root, "input")
    ET.SubElement(input_node, "net-file", {"value": str(paths.net)})
    ET.SubElement(input_node, "route-files", {"value": str(paths.routes)})
    ET.SubElement(input_node, "additional-files", {"value": paths.additional.name})

    output_node = ET.SubElement(root, "output")
    ET.SubElement(output_node, "tripinfo-output", {"value": paths.tripinfo.name})
    ET.SubElement(output_node, "tripinfo-output.write-unfinished", {"value": "true"})
    ET.SubElement(output_node, "summary-output", {"value": paths.summary.name})
    ET.SubElement(output_node, "statistic-output", {"value": paths.statistic.name})
    ET.SubElement(output_node, "fcd-output", {"value": paths.fcd.name})
    ET.SubElement(output_node, "fcd-output.skip-empty", {"value": "true"})
    ET.SubElement(
        output_node,
        "fcd-output.attributes",
        {"value": "location,posLat,speedLat,acceleration"},
    )

    time_node = ET.SubElement(root, "time")
    ET.SubElement(time_node, "begin", {"value": "0"})
    ET.SubElement(time_node, "end", {"value": str(horizon_seconds)})
    ET.SubElement(time_node, "step-length", {"value": f"{step_length_seconds:g}"})

    processing_node = ET.SubElement(root, "processing")
    ET.SubElement(processing_node, "ignore-route-errors", {"value": "true"})
    ET.SubElement(processing_node, "time-to-teleport", {"value": "300"})

    random_node = ET.SubElement(root, "random_number")
    ET.SubElement(random_node, "seed", {"value": str(seed)})
    _write_xml(root, paths.config)


def _write_xml(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with path.open("xb") as handle:
        tree.write(handle, encoding="utf-8", xml_declaration=True)


def _validate_portable_component(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise SumoRuntimeError(f"{name} must be a non-empty portable path component")
    windows_path = PureWindowsPath(value)
    if (
        value in {".", ".."}
        or windows_path.is_absolute()
        or windows_path.root
        or windows_path.drive
        or "/" in value
        or "\\" in value
        or not _PORTABLE_COMPONENT.fullmatch(value)
    ):
        raise SumoRuntimeError(f"{name} must be a portable single path component: {value!r}")
    if value.endswith((".", " ")):
        raise SumoRuntimeError(f"{name} cannot end with a dot or space: {value!r}")
    if value.split(".", 1)[0].upper() in _RESERVED_WINDOWS_NAMES:
        raise SumoRuntimeError(f"{name} uses a reserved Windows device name: {value!r}")


def _validate_seed(seed: object) -> None:
    if type(seed) is not int or not 0 <= seed <= _MAX_SEED:
        raise SumoRuntimeError(f"seed must be an integer in [0, {_MAX_SEED}]")


def _validate_horizon(horizon_seconds: object) -> None:
    if type(horizon_seconds) is not int or horizon_seconds <= 0:
        raise SumoRuntimeError("horizon_seconds must be a positive integer")


def _validate_positive_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise SumoRuntimeError(f"{name} must be a finite positive number")
    try:
        number = float(cast(SupportsFloat, value))
    except (OverflowError, TypeError, ValueError) as exc:
        raise SumoRuntimeError(f"{name} must be a finite positive number") from exc
    if not math.isfinite(number) or number <= 0:
        raise SumoRuntimeError(f"{name} must be a finite positive number")
    return number


def _validate_profile(profile: SumoSimulationProfile) -> None:
    if not isinstance(profile, SumoSimulationProfile):
        raise SumoRuntimeError("simulation_profile must be a SumoSimulationProfile")
    _validate_positive_number(
        profile.step_length_seconds, "simulation_profile.step_length_seconds"
    )
    _validate_positive_number(
        profile.action_step_length_seconds, "simulation_profile.action_step_length_seconds"
    )
    _validate_positive_number(profile.fcd_period_seconds, "simulation_profile.fcd_period_seconds")
    if profile.lateral_resolution_m is not None:
        _validate_positive_number(
            profile.lateral_resolution_m, "simulation_profile.lateral_resolution_m"
        )


def _reserve_run_directory(work_dir: Path, scenario_id: str, controller_id: str) -> Path:
    try:
        resolved_root = work_dir.resolve()
        scenario_dir = resolved_root / scenario_id
        _ensure_within_root(resolved_root, scenario_dir, label="scenario_id")
        run_dir = scenario_dir / controller_id
        _ensure_within_root(resolved_root, run_dir, label="controller run")
        run_dir.mkdir(parents=True, exist_ok=False)
        resolved_run_dir = run_dir.resolve()
        _ensure_within_root(resolved_root, resolved_run_dir, label="controller run")
        return resolved_run_dir
    except SumoRuntimeError:
        raise
    except FileExistsError as exc:
        raise SumoRuntimeError(
            f"SUMO existing-net run directory already exists: {run_dir}"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise SumoRuntimeError(f"could not reserve SUMO run directory {work_dir}: {exc}") from exc


def _read_log_tail(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - _LOG_TAIL_BYTES))
            return handle.read(_LOG_TAIL_BYTES).decode("utf-8", errors="replace")
    except OSError as exc:
        return f"<could not read log tail: {exc}>"


def _ensure_within_root(root: Path, candidate: Path, *, label: str) -> None:
    try:
        resolved_candidate = candidate.resolve()
        resolved_candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SumoRuntimeError(
            f"{label} resolves outside requested SUMO work root: {candidate}"
        ) from exc
