from __future__ import annotations

import subprocess
from pathlib import Path

from ai_quantum_hvtc.simulation.engines.sumo.config import (
    SumoRuntimeConfig,
    resolve_sumo_binary,
)
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.exporter import SumoExportPaths


def has_sumo_runtime(config: SumoRuntimeConfig | None = None) -> bool:
    active_config = config or SumoRuntimeConfig()
    return (
        resolve_sumo_binary(active_config.sumo_binary) is not None
        and resolve_sumo_binary(active_config.netconvert_binary) is not None
    )


def run_sumo_pipeline(
    paths: SumoExportPaths,
    config: SumoRuntimeConfig,
    *,
    controller_id: str,
) -> None:
    if controller_id not in {"fixed_time", "rule_based"}:
        raise SumoRuntimeError(
            f"SUMO controller '{controller_id}' is not implemented; use fixed_time or rule_based."
        )

    netconvert = _required_binary(config.netconvert_binary)
    sumo = _required_binary(config.sumo_binary)
    _build_network(paths, netconvert, controller_id=controller_id)
    if controller_id == "rule_based":
        # SUMO's actuated traffic light is the first non-RL rule-based baseline.
        # It is deliberately conservative: stable enough for comparison, not claimed as AI.
        paths.controller_log.write_text("", encoding="utf-8")
    _run_command(_sumo_command(sumo, paths), cwd=paths.work_dir)


def _build_network(paths: SumoExportPaths, netconvert: str, *, controller_id: str) -> None:
    command = [
        netconvert,
        "--node-files",
        str(paths.nodes),
        "--edge-files",
        str(paths.edges),
        "--output-file",
        str(paths.net),
        "--no-turnarounds",
        "true",
    ]
    if controller_id == "rule_based":
        command.extend(["--tls.default-type", "actuated"])
    _run_command(command, cwd=paths.work_dir)


def _sumo_command(sumo: str, paths: SumoExportPaths) -> list[str]:
    return [
        sumo,
        "-c",
        str(paths.config),
        "--no-step-log",
        "true",
        "--no-warnings",
        "true",
        *paths.simulation_profile.command_args(),
    ]


def _required_binary(binary_name: str) -> str:
    resolved = resolve_sumo_binary(binary_name)
    if resolved is None:
        raise SumoRuntimeError(
            f"SUMO binary '{binary_name}' was not found. Install SUMO or set SUMO_HOME."
        )
    return resolved


def _run_command(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SumoRuntimeError(
            "SUMO command failed:\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )
