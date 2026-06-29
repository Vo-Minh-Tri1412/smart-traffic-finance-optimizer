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


def run_sumo_pipeline(paths: SumoExportPaths, config: SumoRuntimeConfig) -> None:
    netconvert = _required_binary(config.netconvert_binary)
    sumo = _required_binary(config.sumo_binary)
    _run_command(
        [
            netconvert,
            "--node-files",
            str(paths.nodes),
            "--edge-files",
            str(paths.edges),
            "--output-file",
            str(paths.net),
            "--no-turnarounds",
            "true",
        ],
        cwd=paths.work_dir,
    )
    _run_command([sumo, "-c", str(paths.config), "--no-step-log", "true"], cwd=paths.work_dir)


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
