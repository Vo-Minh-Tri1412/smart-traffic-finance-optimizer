from __future__ import annotations

import tempfile
from pathlib import Path

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.engines.base import SimulationEngine
from ai_quantum_hvtc.simulation.engines.sumo.config import SumoRuntimeConfig
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.parser import parse_sumo_result
from ai_quantum_hvtc.simulation.engines.sumo.profiles import (
    DEFAULT_SUMO_PROFILE,
    SumoSimulationProfile,
)
from ai_quantum_hvtc.simulation.engines.sumo.runner import run_sumo_pipeline
from ai_quantum_hvtc.simulation.metrics import SimulationResult


class SumoAdapter(SimulationEngine):
    engine_id = "sumo"

    def __init__(
        self,
        *,
        runtime_config: SumoRuntimeConfig | None = None,
        work_dir: Path | None = None,
        simulation_profile: SumoSimulationProfile = DEFAULT_SUMO_PROFILE,
    ) -> None:
        self._runtime_config = runtime_config or SumoRuntimeConfig()
        self._work_dir = work_dir
        self._simulation_profile = simulation_profile

    def run(
        self,
        *,
        spec: DistrictSpec,
        scenario_id: str,
        controller_id: str,
        seed: int,
    ) -> SimulationResult:
        if controller_id == "rl_policy":
            raise SumoRuntimeError(
                "SUMO RL training/evaluation is not implemented yet; use fixed_time or rule_based."
            )
        if self._work_dir is not None:
            return self._run_in_work_dir(
                spec=spec,
                scenario_id=scenario_id,
                controller_id=controller_id,
                seed=seed,
                work_dir=self._work_dir,
            )

        with tempfile.TemporaryDirectory(prefix="ai_quantum_hvtc_sumo_") as tmp_dir:
            return self._run_in_work_dir(
                spec=spec,
                scenario_id=scenario_id,
                controller_id=controller_id,
                seed=seed,
                work_dir=Path(tmp_dir),
            )

    def _run_in_work_dir(
        self,
        *,
        spec: DistrictSpec,
        scenario_id: str,
        controller_id: str,
        seed: int,
        work_dir: Path,
    ) -> SimulationResult:
        paths = export_sumo_project(
            spec=spec,
            scenario_id=scenario_id,
            controller_id=controller_id,
            seed=seed,
            work_dir=work_dir,
            simulation_profile=self._simulation_profile,
        )
        run_sumo_pipeline(paths, self._runtime_config, controller_id=controller_id)
        return parse_sumo_result(
            paths=paths,
            spec=spec,
            scenario_id=scenario_id,
            controller_id=controller_id,
            seed=seed,
        )
