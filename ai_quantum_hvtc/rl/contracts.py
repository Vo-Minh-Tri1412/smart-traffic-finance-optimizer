from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationSpaceContract:
    version: str
    feature_groups: tuple[str, ...]
    source_document: str


@dataclass(frozen=True)
class ActionSpaceContract:
    version: str
    action_type: str
    controlled_intersection_ids: tuple[str, ...]
    caveat: str


OBSERVATION_SPACE_V1 = ObservationSpaceContract(
    version="v1",
    feature_groups=(
        "traffic_pressure",
        "queue_and_waiting_time",
        "priority_vehicle_presence",
        "downstream_capacity",
        "semantic_zone_context",
        "public_finance_context",
    ),
    source_document="docs/02_ARCHITECTURE/OBSERVATION_SPACE_V1.md",
)


ACTION_SPACE_V1 = ActionSpaceContract(
    version="v1",
    action_type="traffic_signal_phase_selection",
    controlled_intersection_ids=(),
    caveat="Controlled intersections are selected per district spec and scenario budget.",
)
