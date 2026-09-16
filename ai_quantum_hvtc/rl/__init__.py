"""RL contracts and reward-profile scaffolding for SUMO-RL training."""

from __future__ import annotations

from .contracts import ActionSpaceContract, ObservationSpaceContract
from .map_economic_reward import (
    SignalEconomicStep,
    SumoMapEconomicReward,
    build_sumo_map_economic_reward,
)
from .reward_profiles import (
    HardConstraint,
    RewardProfile,
    RewardProfileError,
    RoutePriorityWeight,
    TimeWindowWeight,
    build_sumo_rl_reward,
    load_reward_profile,
    training_blockers,
    validate_reward_profile_against_spec,
)

__all__ = [
    "ActionSpaceContract",
    "HardConstraint",
    "ObservationSpaceContract",
    "RewardProfile",
    "RewardProfileError",
    "RoutePriorityWeight",
    "SignalEconomicStep",
    "SumoMapEconomicReward",
    "TimeWindowWeight",
    "build_sumo_map_economic_reward",
    "build_sumo_rl_reward",
    "load_reward_profile",
    "training_blockers",
    "validate_reward_profile_against_spec",
]
