"""Pure incremental economic-delay reward calculation.

The input is a *delta* in delay or time-loss seconds. Passing SUMO's cumulative
``getTimeLoss()`` value directly would count the same cost repeatedly.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .models import MapEconomicProfile
from .resolution import ResolvedValuation, TripEconomicContext, resolve_trip_valuation


@dataclass(frozen=True)
class MonetaryInterval:
    estimate: float
    lower: float
    upper: float
    unit: str
    price_year: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EconomicRewardBreakdown:
    trip_id: str
    delay_delta_seconds: float
    reliability_delta_seconds: float
    resolution_level: str
    matched_id: str
    valuation_id: str
    matched_corridor_ids: tuple[str, ...]
    raw_public_cost: MonetaryInterval
    normalized_unclipped: float
    normalized_clipped: float
    contains_assumptions: bool
    evidence_grades: tuple[str, ...]
    source_ids: tuple[str, ...]

    @property
    def reward(self) -> float:
        return self.normalized_clipped

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["raw_public_cost"] = self.raw_public_cost.to_dict()
        payload["matched_corridor_ids"] = list(self.matched_corridor_ids)
        payload["evidence_grades"] = list(self.evidence_grades)
        payload["source_ids"] = list(self.source_ids)
        payload["reward"] = self.reward
        return payload


class MapEconomicReward:
    """Evaluate a VND ledger and a separately scaled/clipped PPO reward."""

    def __init__(self, profile: MapEconomicProfile) -> None:
        self.profile = profile

    def evaluate_trip_delay_delta(
        self,
        *,
        delay_delta_seconds: float,
        reliability_delta_seconds: float = 0.0,
        context: TripEconomicContext,
        persons_per_trip: float | None = None,
    ) -> EconomicRewardBreakdown:
        """Evaluate signed incremental delay.

        Positive deltas are a public cost and therefore a negative reward.
        Negative deltas represent saved delay and therefore a positive reward.
        """

        if not math.isfinite(delay_delta_seconds):
            raise ValueError("delay_delta_seconds must be finite")
        if not math.isfinite(reliability_delta_seconds):
            raise ValueError("reliability_delta_seconds must be finite")
        if persons_per_trip is not None and (
            not math.isfinite(persons_per_trip) or persons_per_trip <= 0
        ):
            raise ValueError("persons_per_trip override must be finite and > 0")

        resolved = resolve_trip_valuation(self.profile, context)
        raw_cost = _monetize_delay(
            resolved,
            delay_delta_seconds=delay_delta_seconds,
            reliability_delta_seconds=reliability_delta_seconds,
            persons_per_trip=persons_per_trip,
            price_year=self.profile.metadata.price_year,
        )
        scale = self.profile.reward_policy.normalization_vnd_per_step.estimate
        normalized = -raw_cost.estimate / scale
        clipped = min(
            self.profile.reward_policy.clip_max,
            max(self.profile.reward_policy.clip_min, normalized),
        )
        valuation = resolved.valuation
        records = (
            valuation.value_of_time,
            valuation.reliability_value,
            valuation.persons_per_trip,
            valuation.essential_service_multiplier,
            valuation.economic_flow_multiplier,
        )
        return EconomicRewardBreakdown(
            trip_id=context.trip_id,
            delay_delta_seconds=delay_delta_seconds,
            reliability_delta_seconds=reliability_delta_seconds,
            resolution_level=resolved.resolution_level,
            matched_id=resolved.matched_id,
            valuation_id=valuation.valuation_id,
            matched_corridor_ids=resolved.matched_corridor_ids,
            raw_public_cost=raw_cost,
            normalized_unclipped=normalized,
            normalized_clipped=clipped,
            contains_assumptions=any(record.is_assumption for record in records),
            evidence_grades=tuple(sorted({record.evidence_grade for record in records})),
            source_ids=tuple(sorted({item for record in records for item in record.source_ids})),
        )


def build_map_economic_reward(profile: MapEconomicProfile) -> MapEconomicReward:
    return MapEconomicReward(profile)


def _monetize_delay(
    resolved: ResolvedValuation,
    *,
    delay_delta_seconds: float,
    reliability_delta_seconds: float,
    persons_per_trip: float | None,
    price_year: int,
) -> MonetaryInterval:
    valuation = resolved.valuation
    if persons_per_trip is None:
        occupancy = valuation.persons_per_trip
        occupancy_values = (occupancy.estimate, occupancy.lower, occupancy.upper)
    else:
        occupancy_values = (persons_per_trip, persons_per_trip, persons_per_trip)

    common = (
        occupancy_values[0]
        * valuation.essential_service_multiplier.estimate
        * valuation.economic_flow_multiplier.estimate,
        occupancy_values[1]
        * valuation.essential_service_multiplier.lower
        * valuation.economic_flow_multiplier.lower,
        occupancy_values[2]
        * valuation.essential_service_multiplier.upper
        * valuation.economic_flow_multiplier.upper,
    )
    delay_rate = (
        common[0] * valuation.value_of_time.estimate,
        common[1] * valuation.value_of_time.lower,
        common[2] * valuation.value_of_time.upper,
    )
    reliability_rate = (
        common[0] * valuation.reliability_value.estimate,
        common[1] * valuation.reliability_value.lower,
        common[2] * valuation.reliability_value.upper,
    )
    delay_interval = _signed_component(delay_delta_seconds, delay_rate)
    reliability_interval = _signed_component(reliability_delta_seconds, reliability_rate)
    return MonetaryInterval(
        estimate=delay_interval[0] + reliability_interval[0],
        lower=delay_interval[1] + reliability_interval[1],
        upper=delay_interval[2] + reliability_interval[2],
        unit="VND",
        price_year=price_year,
    )


def _signed_component(
    seconds: float, rate: tuple[float, float, float]
) -> tuple[float, float, float]:
    estimate = seconds / 3600.0 * rate[0]
    bounds = (seconds / 3600.0 * rate[1], seconds / 3600.0 * rate[2])
    return estimate, min(bounds), max(bounds)
