from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from ai_quantum_hvtc.simulation.engines.sumo.config import (
    SumoRuntimeConfig,
    resolve_sumo_binary,
)
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.profiles import (
    DEFAULT_SUMO_PROFILE,
    SumoSimulationProfile,
)


@dataclass(frozen=True)
class ExistingSumoNetRunPaths:
    work_dir: Path
    net: Path
    routes: Path
    additional: Path
    config: Path
    tripinfo: Path
    summary: Path
    edge_data: Path
    fcd: Path
    controller_log: Path
    simulation_profile: SumoSimulationProfile


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
    if not net.is_file():
        raise SumoRuntimeError(f"SUMO net file not found: {net}")
    if not routes.is_file():
        raise SumoRuntimeError(f"SUMO route file not found: {routes}")

    profile = simulation_profile or DEFAULT_SUMO_PROFILE
    if (
        simulation_profile is None
        and step_length_seconds != DEFAULT_SUMO_PROFILE.step_length_seconds
    ):
        profile = SumoSimulationProfile(
            profile_id="custom",
            step_length_seconds=step_length_seconds,
            action_step_length_seconds=DEFAULT_SUMO_PROFILE.action_step_length_seconds,
            fcd_period_seconds=DEFAULT_SUMO_PROFILE.fcd_period_seconds,
        )
    run_dir = work_dir / scenario_id / controller_id
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = ExistingSumoNetRunPaths(
        work_dir=run_dir,
        net=net.resolve(),
        routes=routes.resolve(),
        additional=run_dir / "additional.xml",
        config=run_dir / "district.sumocfg",
        tripinfo=run_dir / "tripinfo.xml",
        summary=run_dir / "summary.xml",
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
    paths.controller_log.write_text("", encoding="utf-8")
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
    import subprocess

    completed = subprocess.run(
        command,
        cwd=paths.work_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SumoRuntimeError(
            "SUMO existing-net command failed:\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
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
    tree.write(path, encoding="utf-8", xml_declaration=True)
