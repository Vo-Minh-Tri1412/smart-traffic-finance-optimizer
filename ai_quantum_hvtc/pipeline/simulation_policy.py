from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SimulationPolicyRunConfig:
    spec_path: Path
    scenario_id: str
    baseline_controller_id: str
    candidate_controller_ids: tuple[str, ...]
    engine_id: str
    budget_vnd: float
