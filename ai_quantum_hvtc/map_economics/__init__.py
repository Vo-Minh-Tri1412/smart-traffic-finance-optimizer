"""Map-specific economic profile, coverage, and incremental reward API."""

from .materialize import coverage_payload, materialize_map_economic_profile
from .models import (
    MAP_ECONOMIC_PROFILE_SCHEMA_VERSION,
    CoverageReport,
    MapEconomicProfile,
    MapEconomicProfileError,
    ValueRecord,
)
from .profile import (
    load_map_economic_profile,
    map_economic_profile_from_mapping,
    save_map_economic_profile,
    validate_map_economic_profile,
)
from .resolution import (
    ResolvedValuation,
    TripEconomicContext,
    assert_production_ready,
    audit_profile_coverage,
    resolve_trip_valuation,
)
from .reward import (
    EconomicRewardBreakdown,
    MapEconomicReward,
    MonetaryInterval,
    build_map_economic_reward,
)

__all__ = [
    "MAP_ECONOMIC_PROFILE_SCHEMA_VERSION",
    "CoverageReport",
    "EconomicRewardBreakdown",
    "MapEconomicProfile",
    "MapEconomicProfileError",
    "MapEconomicReward",
    "MonetaryInterval",
    "ResolvedValuation",
    "TripEconomicContext",
    "ValueRecord",
    "assert_production_ready",
    "audit_profile_coverage",
    "build_map_economic_reward",
    "coverage_payload",
    "load_map_economic_profile",
    "map_economic_profile_from_mapping",
    "materialize_map_economic_profile",
    "resolve_trip_valuation",
    "save_map_economic_profile",
    "validate_map_economic_profile",
]
