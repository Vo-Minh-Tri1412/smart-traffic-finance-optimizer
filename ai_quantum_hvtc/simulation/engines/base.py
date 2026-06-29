from __future__ import annotations

from abc import ABC, abstractmethod

from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.metrics import SimulationResult


class SimulationEngine(ABC):
    engine_id: str

    @abstractmethod
    def run(
        self,
        *,
        spec: DistrictSpec,
        scenario_id: str,
        controller_id: str,
        seed: int,
    ) -> SimulationResult:
        """Run a simulation and return normalized metrics."""
