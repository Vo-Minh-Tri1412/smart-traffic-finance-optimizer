from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

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
    if controller_id == "rule_based":
        _run_rule_based_controller(paths, config)
        return
    if controller_id != "fixed_time":
        raise SumoRuntimeError(
            f"SUMO controller '{controller_id}' is not implemented; use fixed_time or rule_based."
        )

    netconvert = _required_binary(config.netconvert_binary)
    sumo = _required_binary(config.sumo_binary)
    _build_network(paths, netconvert)
    _run_command(_sumo_command(sumo, paths), cwd=paths.work_dir)


def _build_network(paths: SumoExportPaths, netconvert: str) -> None:
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


def _run_rule_based_controller(paths: SumoExportPaths, config: SumoRuntimeConfig) -> None:
    try:
        import traci  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SumoRuntimeError(
            "TraCI is required for the SUMO rule_based controller but is not installed."
        ) from exc

    netconvert = _required_binary(config.netconvert_binary)
    sumo = _required_binary(config.sumo_binary)
    _build_network(paths, netconvert)
    command = _sumo_command(sumo, paths)
    end_time = _sumo_end_time(paths)
    paths.controller_log.parent.mkdir(parents=True, exist_ok=True)
    with paths.controller_log.open("w", encoding="utf-8") as log_file:
        traci.start(command)
        try:
            next_decision_by_tls = {tls_id: 0.0 for tls_id in traci.trafficlight.getIDList()}
            while traci.simulation.getMinExpectedNumber() > 0:
                time_seconds = float(traci.simulation.getTime())
                if time_seconds >= end_time:
                    break
                for tls_id in traci.trafficlight.getIDList():
                    if time_seconds < next_decision_by_tls.get(tls_id, 0.0):
                        continue
                    current_phase = int(traci.trafficlight.getPhase(tls_id))
                    next_phase = _best_rule_based_phase(traci, tls_id, current_phase)
                    if next_phase is not None and next_phase != current_phase:
                        traci.trafficlight.setPhase(tls_id, next_phase)
                        log_file.write(
                            json.dumps(
                                {
                                    "time_seconds": time_seconds,
                                    "tls_id": tls_id,
                                    "from_phase": current_phase,
                                    "to_phase": next_phase,
                                    "reason": "max_weighted_queue",
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        )
                    next_decision_by_tls[tls_id] = time_seconds + 30.0
                traci.simulationStep()
        finally:
            traci.close()


def _best_rule_based_phase(traci: Any, tls_id: str, current_phase: int) -> int | None:
    controlled_lanes = list(traci.trafficlight.getControlledLanes(tls_id))
    if not controlled_lanes:
        return None
    programs = traci.trafficlight.getAllProgramLogics(tls_id)
    if not programs:
        return None

    lane_scores = {
        lane_id: _weighted_lane_score(traci, lane_id) for lane_id in set(controlled_lanes)
    }
    phases = programs[0].phases
    if current_phase >= len(phases):
        current_phase = 0
    current_score = _phase_score(phases[current_phase].state, controlled_lanes, lane_scores)
    best_phase = current_phase
    best_score = current_score
    for phase_index, phase in enumerate(programs[0].phases):
        state = str(phase.state)
        if "G" not in state and "g" not in state:
            continue
        score = _phase_score(state, controlled_lanes, lane_scores)
        if score > best_score:
            best_score = score
            best_phase = phase_index
    if best_score <= current_score + 2.0:
        return current_phase
    return best_phase


def _phase_score(
    state: str,
    controlled_lanes: list[str],
    lane_scores: dict[str, float],
) -> float:
    score = 0.0
    for signal_index, lane_id in enumerate(controlled_lanes):
        if signal_index < len(state) and state[signal_index] in {"G", "g"}:
            score += lane_scores.get(lane_id, 0.0)
    return score


def _weighted_lane_score(traci: Any, lane_id: str) -> float:
    try:
        score = float(traci.lane.getLastStepHaltingNumber(lane_id))
        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id):
            vehicle_type = traci.vehicle.getTypeID(vehicle_id)
            if vehicle_type == "AMBULANCE":
                score += 50.0
            elif vehicle_type in {"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE"}:
                score += 12.0
    except Exception:
        return 0.0
    return score


def _sumo_command(sumo: str, paths: SumoExportPaths) -> list[str]:
    return [sumo, "-c", str(paths.config), "--no-step-log", "true", "--no-warnings", "true"]


def _sumo_end_time(paths: SumoExportPaths) -> float:
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(paths.config)
        end = tree.getroot().find("./time/end")
        if end is not None:
            return float(end.attrib.get("value", "0"))
    except (OSError, ValueError, ET.ParseError):
        return float("inf")
    return float("inf")


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
