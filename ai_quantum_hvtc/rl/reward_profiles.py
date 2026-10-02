from __future__ import annotations

import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ai_quantum_hvtc.simulation.domain import DistrictSpec


class RewardProfileError(ValueError):
    """Raised when a reward profile is missing required fields or references."""


_SUPPORTED_HARD_CONSTRAINT_ENFORCEMENTS = frozenset(
    {"action_filter_required", "reward_penalty_only"}
)


class _TrafficSignalLike(Protocol):
    id: str
    lanes: list[str]
    sumo: Any

    def get_total_queued(self) -> int: ...

    def get_pressure(self) -> float: ...

    def get_average_speed(self) -> float: ...


@dataclass(frozen=True)
class RoutePriorityWeight:
    flow_id: str
    weight: float
    description: str = ""


@dataclass(frozen=True)
class TimeWindowWeight:
    label: str
    start: int
    end: int
    weight: float
    flow_ids: tuple[str, ...] = ()
    trip_purposes: tuple[str, ...] = ()

    def applies_to(self, *, sim_time: float, flow_id: str | None, trip_purpose: str | None) -> bool:
        if not (self.start <= int(sim_time) < self.end):
            return False
        if self.flow_ids and (flow_id is None or flow_id not in self.flow_ids):
            return False
        return not (
            self.trip_purposes and (trip_purpose is None or trip_purpose not in self.trip_purposes)
        )


@dataclass(frozen=True)
class HardConstraint:
    constraint_id: str
    constraint_type: str
    vehicle_types: tuple[str, ...]
    enforcement: str
    status: str
    priority_level_min: int | None = None
    max_wait_seconds: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class RewardProfile:
    profile_id: str
    status: str
    owner: str
    description: str
    base_weights: Mapping[str, float]
    vehicle_type_weights: Mapping[str, float]
    trip_purpose_weights: Mapping[str, float]
    scenario_weights: Mapping[str, float]
    route_priority_weights: tuple[RoutePriorityWeight, ...] = ()
    time_window_weights: tuple[TimeWindowWeight, ...] = ()
    hard_constraints: tuple[HardConstraint, ...] = ()
    require_approved_for_training: bool = True
    hard_constraints_block_training: bool = True
    waiting_time_scale_seconds: float = 100.0

    def route_weight(self, flow_id: str | None) -> float:
        if flow_id is None:
            return 1.0
        for item in self.route_priority_weights:
            if item.flow_id == flow_id:
                return item.weight
        return 1.0

    def time_weight(
        self,
        *,
        sim_time: float,
        flow_id: str | None,
        trip_purpose: str | None,
    ) -> float:
        weight = 1.0
        for item in self.time_window_weights:
            if item.applies_to(sim_time=sim_time, flow_id=flow_id, trip_purpose=trip_purpose):
                weight *= item.weight
        return weight


def load_reward_profile(path: Path | str) -> RewardProfile:
    profile_path = Path(path)
    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RewardProfileError(f"{profile_path}: root TOML value must be a table")
    return reward_profile_from_mapping(data, source=str(profile_path))


def reward_profile_from_mapping(
    data: Mapping[str, Any],
    *,
    source: str = "<mapping>",
) -> RewardProfile:
    metadata = _required_table(data, "metadata", source=source)
    training_gate = _optional_table(data, "training_gate")
    return RewardProfile(
        profile_id=_required_str(metadata, "profile_id", source=source),
        status=_required_str(metadata, "status", source=source),
        owner=_required_str(metadata, "owner", source=source),
        description=str(metadata.get("description", "")),
        base_weights=_float_table(_required_table(data, "base_weights", source=source)),
        vehicle_type_weights=_float_table(_optional_table(data, "vehicle_type_weights")),
        trip_purpose_weights=_float_table(_optional_table(data, "trip_purpose_weights")),
        scenario_weights=_float_table(_optional_table(data, "scenario_weights")),
        route_priority_weights=_route_priority_weights(data.get("route_priority_weights", [])),
        time_window_weights=_time_window_weights(data.get("time_window_weights", [])),
        hard_constraints=_hard_constraints(data.get("hard_constraints", [])),
        require_approved_for_training=bool(
            training_gate.get("require_approved_for_training", True)
        ),
        hard_constraints_block_training=bool(
            training_gate.get("hard_constraints_block_training", True)
        ),
        waiting_time_scale_seconds=float(training_gate.get("waiting_time_scale_seconds", 100.0)),
    )


def validate_reward_profile_against_spec(
    profile: RewardProfile,
    spec: DistrictSpec,
) -> list[str]:
    errors: list[str] = []
    known_vehicle_types = set(spec.vehicle_types)
    known_trip_purposes = {flow.trip_purpose for flow in spec.flows.values()}
    known_scenarios = set(spec.scenarios)
    known_flows = set(spec.flows)

    errors.extend(
        _unknown_keys("vehicle_type_weights", profile.vehicle_type_weights, known_vehicle_types)
    )
    errors.extend(
        _unknown_keys("trip_purpose_weights", profile.trip_purpose_weights, known_trip_purposes)
    )
    errors.extend(_unknown_keys("scenario_weights", profile.scenario_weights, known_scenarios))

    for route_weight in profile.route_priority_weights:
        if route_weight.flow_id not in known_flows:
            errors.append(
                f"route_priority_weights references unknown flow_id: {route_weight.flow_id}"
            )
    for window_weight in profile.time_window_weights:
        if window_weight.start < 0 or window_weight.end <= window_weight.start:
            errors.append(f"time_window_weights.{window_weight.label} has invalid start/end")
        if window_weight.end > spec.metadata.horizon_seconds:
            errors.append(
                f"time_window_weights.{window_weight.label} ends after simulation horizon"
            )
        for flow_id in window_weight.flow_ids:
            if flow_id not in known_flows:
                errors.append(
                    f"time_window_weights.{window_weight.label} references unknown flow_id: "
                    f"{flow_id}"
                )
        for trip_purpose in window_weight.trip_purposes:
            if trip_purpose not in known_trip_purposes:
                errors.append(
                    f"time_window_weights.{window_weight.label} references unknown trip_purpose: "
                    f"{trip_purpose}"
                )
    for constraint in profile.hard_constraints:
        if constraint.enforcement not in _SUPPORTED_HARD_CONSTRAINT_ENFORCEMENTS:
            errors.append(
                f"hard_constraints.{constraint.constraint_id}.enforcement has unsupported "
                f"value: {constraint.enforcement}"
            )
        for vehicle_type in constraint.vehicle_types:
            if vehicle_type not in known_vehicle_types:
                errors.append(
                    f"hard_constraints.{constraint.constraint_id} references unknown vehicle_type: "
                    f"{vehicle_type}"
                )
    if profile.waiting_time_scale_seconds <= 0:
        errors.append("training_gate.waiting_time_scale_seconds must be > 0")
    return errors


def training_blockers(
    profile: RewardProfile,
    spec: DistrictSpec,
    *,
    allow_draft_reward: bool = False,
    acknowledge_pending_hard_constraints: bool = False,
) -> list[str]:
    blockers = validate_reward_profile_against_spec(profile, spec)
    if (
        profile.require_approved_for_training
        and not allow_draft_reward
        and profile.status != "approved"
    ):
        blockers.append(
            f"reward profile status is '{profile.status}', but training requires 'approved'"
        )
    pending_constraints = [
        constraint
        for constraint in profile.hard_constraints
        if constraint.enforcement != "reward_penalty_only" and constraint.status != "implemented"
    ]
    required_filter_constraints = [
        constraint
        for constraint in pending_constraints
        if constraint.enforcement == "action_filter_required"
    ]
    acknowledgeable_constraints = [
        constraint
        for constraint in pending_constraints
        if constraint.enforcement != "action_filter_required"
    ]
    blocking_constraints = required_filter_constraints.copy()
    if profile.hard_constraints_block_training and not acknowledge_pending_hard_constraints:
        blocking_constraints.extend(acknowledgeable_constraints)
    if blocking_constraints:
        ids = ", ".join(constraint.constraint_id for constraint in blocking_constraints)
        blockers.append(
            "hard constraints require an action-filter/override layer before training: " + ids
        )
    return blockers


def build_sumo_rl_reward(
    profile: RewardProfile,
    spec: DistrictSpec,
    *,
    scenario_id: str,
) -> Callable[[Any], float]:
    flow_by_prefix = sorted(spec.flows.items(), key=lambda item: len(item[0]), reverse=True)
    scenario_multiplier = profile.scenario_weights.get(scenario_id, 1.0)

    def reward(traffic_signal: _TrafficSignalLike) -> float:
        sim_time = _safe_float(traffic_signal.sumo.simulation.getTime(), default=0.0)
        weighted_waiting = 0.0
        seen_vehicle_ids: set[str] = set()
        for lane_id in getattr(traffic_signal, "lanes", []):
            vehicle_ids = traffic_signal.sumo.lane.getLastStepVehicleIDs(lane_id)
            for vehicle_id in vehicle_ids:
                if vehicle_id in seen_vehicle_ids:
                    continue
                seen_vehicle_ids.add(str(vehicle_id))
                flow_id = _flow_id_from_vehicle_id(str(vehicle_id), flow_by_prefix)
                trip_purpose = spec.flows[flow_id].trip_purpose if flow_id else None
                vehicle_type = _safe_str(
                    traffic_signal.sumo.vehicle.getTypeID(vehicle_id),
                    default="",
                )
                waiting_seconds = _safe_float(
                    traffic_signal.sumo.vehicle.getAccumulatedWaitingTime(vehicle_id),
                    default=0.0,
                )
                weighted_waiting += (
                    waiting_seconds
                    * profile.vehicle_type_weights.get(vehicle_type, 1.0)
                    * profile.trip_purpose_weights.get(trip_purpose or "", 1.0)
                    * profile.route_weight(flow_id)
                    * profile.time_weight(
                        sim_time=sim_time,
                        flow_id=flow_id,
                        trip_purpose=trip_purpose,
                    )
                )

        waiting_penalty = profile.base_weights.get("waiting_time", 1.0) * (
            weighted_waiting / profile.waiting_time_scale_seconds
        )
        queue_penalty = profile.base_weights.get("queue_length", 0.0) * float(
            traffic_signal.get_total_queued()
        )
        pressure_penalty = profile.base_weights.get("pressure_abs", 0.0) * abs(
            float(traffic_signal.get_pressure())
        )
        speed_bonus = profile.base_weights.get("average_speed_bonus", 0.0) * float(
            traffic_signal.get_average_speed()
        )
        return scenario_multiplier * (
            speed_bonus - waiting_penalty - queue_penalty - pressure_penalty
        )

    return reward


def _flow_id_from_vehicle_id(
    vehicle_id: str,
    flow_by_prefix: list[tuple[str, Any]],
) -> str | None:
    for flow_id, _flow in flow_by_prefix:
        if vehicle_id.startswith(flow_id + "_"):
            return flow_id
    return None


def _required_table(data: Mapping[str, Any], name: str, *, source: str) -> Mapping[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise RewardProfileError(f"{source}: missing required table [{name}]")
    return value


def _optional_table(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise RewardProfileError(f"{name} must be a TOML table")
    return value


def _required_str(data: Mapping[str, Any], name: str, *, source: str) -> str:
    value = data.get(name)
    if value is None or str(value).strip() == "":
        raise RewardProfileError(f"{source}: missing required string metadata.{name}")
    return str(value)


def _float_table(data: Mapping[str, Any]) -> dict[str, float]:
    return {str(key): float(value) for key, value in data.items()}


def _route_priority_weights(value: Any) -> tuple[RoutePriorityWeight, ...]:
    return tuple(
        RoutePriorityWeight(
            flow_id=str(item["flow_id"]),
            weight=float(item["weight"]),
            description=str(item.get("description", "")),
        )
        for item in _array_of_tables(value, "route_priority_weights")
    )


def _time_window_weights(value: Any) -> tuple[TimeWindowWeight, ...]:
    return tuple(
        TimeWindowWeight(
            label=str(item["label"]),
            start=int(item["start"]),
            end=int(item["end"]),
            weight=float(item["weight"]),
            flow_ids=_tuple_of_strings(item.get("flow_ids", [])),
            trip_purposes=_tuple_of_strings(item.get("trip_purposes", [])),
        )
        for item in _array_of_tables(value, "time_window_weights")
    )


def _hard_constraints(value: Any) -> tuple[HardConstraint, ...]:
    return tuple(
        HardConstraint(
            constraint_id=str(item["id"]),
            constraint_type=str(item["type"]),
            vehicle_types=_tuple_of_strings(item.get("vehicle_types", [])),
            enforcement=str(item["enforcement"]),
            status=str(item.get("status", "pending_implementation")),
            priority_level_min=_optional_int(item.get("priority_level_min")),
            max_wait_seconds=_optional_float(item.get("max_wait_seconds")),
            notes=str(item.get("notes", "")),
        )
        for item in _array_of_tables(value, "hard_constraints")
    )


def _array_of_tables(value: Any, name: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RewardProfileError(f"{name} must be an array of TOML tables")
    for item in value:
        if not isinstance(item, dict):
            raise RewardProfileError(f"{name} must contain only TOML tables")
    return value


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RewardProfileError("expected a list of strings")
    return tuple(str(item) for item in value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _unknown_keys(
    section_name: str,
    values: Mapping[str, float],
    known_keys: set[str],
) -> list[str]:
    return [
        f"{section_name} references unknown key: {key}" for key in values if key not in known_keys
    ]


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, *, default: str) -> str:
    if value is None:
        return default
    return str(value)
