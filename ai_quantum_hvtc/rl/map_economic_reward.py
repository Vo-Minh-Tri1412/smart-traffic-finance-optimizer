"""SUMO-RL adapter for the map-specific incremental economic reward.

SUMO's ``getTimeLoss`` value is cumulative for a vehicle.  This adapter keeps a
per-signal baseline and only monetizes the increment observed while that vehicle
is in the signal's controlled lanes.  The raw VND ledger is retained separately
from the normalized/clipped scalar returned to PPO.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ai_quantum_hvtc.map_economics import MapEconomicProfile, MapEconomicReward
from ai_quantum_hvtc.map_economics.resolution import TripEconomicContext
from ai_quantum_hvtc.simulation.domain import DistrictSpec


class _TrafficSignalLike(Protocol):
    id: str
    lanes: list[str]
    sumo: Any


@dataclass(frozen=True)
class SignalEconomicStep:
    """Inspectable economic ledger for one signal reward evaluation."""

    signal_id: str
    simulation_time_seconds: float
    observed_vehicle_count: int
    monetized_vehicle_count: int
    first_sighting_count: int
    raw_public_cost_vnd_estimate: float
    raw_public_cost_vnd_lower: float
    raw_public_cost_vnd_upper: float
    normalized_unclipped: float
    normalized_clipped: float
    resolution_counts: Mapping[str, int]
    assumption_vehicle_count: int


class SumoMapEconomicReward:
    """Callable SUMO-RL reward with a separate auditable VND ledger."""

    def __init__(self, profile: MapEconomicProfile, spec: DistrictSpec) -> None:
        self.profile = profile
        self.spec = spec
        self.evaluator = MapEconomicReward(profile)
        self.last_step_by_signal: dict[str, SignalEconomicStep] = {}
        self.cumulative_public_cost_vnd_by_signal: dict[str, float] = {}
        self._previous_time_loss: dict[tuple[str, str], float] = {}
        self._last_simulation_time: dict[str, float] = {}
        self._signal_owners: dict[str, object] = {}
        self._flow_by_prefix = sorted(
            spec.flows.items(), key=lambda item: len(item[0]), reverse=True
        )

    def __call__(self, traffic_signal: _TrafficSignalLike) -> float:
        signal_id = str(traffic_signal.id)
        if self._signal_owners.get(signal_id) is not traffic_signal:
            self.reset(signal_id=signal_id)
            self._signal_owners[signal_id] = traffic_signal
        simulation_time = _finite_nonnegative(traffic_signal.sumo.simulation.getTime())
        previous_simulation_time = self._last_simulation_time.get(signal_id)
        if previous_simulation_time is not None and simulation_time < previous_simulation_time:
            self.reset(signal_id=signal_id)
            self._signal_owners[signal_id] = traffic_signal
        self._last_simulation_time[signal_id] = simulation_time

        vehicle_ids = _unique_vehicle_ids(traffic_signal)
        active_keys = {(signal_id, vehicle_id) for vehicle_id in vehicle_ids}
        raw_estimate = 0.0
        raw_lower = 0.0
        raw_upper = 0.0
        monetized_count = 0
        first_sighting_count = 0
        assumption_count = 0
        resolution_counts: Counter[str] = Counter()

        for vehicle_id in vehicle_ids:
            key = (signal_id, vehicle_id)
            current_time_loss = _finite_nonnegative(
                traffic_signal.sumo.vehicle.getTimeLoss(vehicle_id)
            )
            previous_time_loss = self._previous_time_loss.get(key)
            self._previous_time_loss[key] = current_time_loss
            if previous_time_loss is None or current_time_loss < previous_time_loss:
                first_sighting_count += 1
                continue
            delay_delta = current_time_loss - previous_time_loss
            if delay_delta <= 0:
                continue

            flow_id = _flow_id_from_vehicle_id(vehicle_id, self._flow_by_prefix)
            flow = self.spec.flows.get(flow_id or "")
            route_edges = _vehicle_route_edges(traffic_signal, vehicle_id)
            breakdown = self.evaluator.evaluate_trip_delay_delta(
                delay_delta_seconds=delay_delta,
                context=TripEconomicContext(
                    trip_id=vehicle_id,
                    od_pair_id=flow_id or "",
                    origin_zone_id=flow.origin_zone if flow is not None else "",
                    destination_zone_id=(flow.destination_zone if flow is not None else ""),
                    route_edge_ids=route_edges,
                ),
            )
            raw_estimate += breakdown.raw_public_cost.estimate
            raw_lower += breakdown.raw_public_cost.lower
            raw_upper += breakdown.raw_public_cost.upper
            monetized_count += 1
            resolution_counts[breakdown.resolution_level] += 1
            assumption_count += int(breakdown.contains_assumptions)

        stale_keys = [
            key
            for key in self._previous_time_loss
            if key[0] == signal_id and key not in active_keys
        ]
        for key in stale_keys:
            del self._previous_time_loss[key]

        normalization = self.profile.reward_policy.normalization_vnd_per_step.estimate
        normalized_unclipped = -raw_estimate / normalization
        normalized_clipped = min(
            self.profile.reward_policy.clip_max,
            max(self.profile.reward_policy.clip_min, normalized_unclipped),
        )
        ledger = SignalEconomicStep(
            signal_id=signal_id,
            simulation_time_seconds=simulation_time,
            observed_vehicle_count=len(vehicle_ids),
            monetized_vehicle_count=monetized_count,
            first_sighting_count=first_sighting_count,
            raw_public_cost_vnd_estimate=raw_estimate,
            raw_public_cost_vnd_lower=raw_lower,
            raw_public_cost_vnd_upper=raw_upper,
            normalized_unclipped=normalized_unclipped,
            normalized_clipped=normalized_clipped,
            resolution_counts=dict(sorted(resolution_counts.items())),
            assumption_vehicle_count=assumption_count,
        )
        self.last_step_by_signal[signal_id] = ledger
        self.cumulative_public_cost_vnd_by_signal[signal_id] = (
            self.cumulative_public_cost_vnd_by_signal.get(signal_id, 0.0) + raw_estimate
        )
        return normalized_clipped

    def reset(self, *, signal_id: str | None = None) -> None:
        """Clear episode state globally or for a single traffic signal."""

        if signal_id is None:
            self._previous_time_loss.clear()
            self._last_simulation_time.clear()
            self.last_step_by_signal.clear()
            self.cumulative_public_cost_vnd_by_signal.clear()
            self._signal_owners.clear()
            return
        self._previous_time_loss = {
            key: value for key, value in self._previous_time_loss.items() if key[0] != signal_id
        }
        self._last_simulation_time.pop(signal_id, None)
        self.last_step_by_signal.pop(signal_id, None)
        self.cumulative_public_cost_vnd_by_signal.pop(signal_id, None)
        self._signal_owners.pop(signal_id, None)


def build_sumo_map_economic_reward(
    profile: MapEconomicProfile,
    spec: DistrictSpec,
) -> SumoMapEconomicReward:
    return SumoMapEconomicReward(profile, spec)


def _unique_vehicle_ids(traffic_signal: _TrafficSignalLike) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for lane_id in getattr(traffic_signal, "lanes", []):
        for raw_vehicle_id in traffic_signal.sumo.lane.getLastStepVehicleIDs(lane_id):
            vehicle_id = str(raw_vehicle_id)
            if vehicle_id not in seen:
                seen.add(vehicle_id)
                ordered.append(vehicle_id)
    return tuple(ordered)


def _flow_id_from_vehicle_id(
    vehicle_id: str,
    flow_by_prefix: list[tuple[str, Any]],
) -> str | None:
    for flow_id, _flow in flow_by_prefix:
        if vehicle_id.startswith(flow_id + "_") or vehicle_id.startswith(flow_id + "."):
            return flow_id
    return None


def _vehicle_route_edges(
    traffic_signal: _TrafficSignalLike,
    vehicle_id: str,
) -> tuple[str, ...]:
    get_route = getattr(traffic_signal.sumo.vehicle, "getRoute", None)
    if not callable(get_route):
        return ()
    return tuple(str(edge_id) for edge_id in get_route(vehicle_id))


def _finite_nonnegative(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("SUMO economic reward requires finite non-negative measurements") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("SUMO economic reward requires finite non-negative measurements")
    return result
