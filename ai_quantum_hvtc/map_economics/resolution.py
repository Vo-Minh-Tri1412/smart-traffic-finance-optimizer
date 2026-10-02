"""Deterministic map-aware valuation resolution and coverage auditing."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import (
    CorridorEconomicNode,
    CoverageReport,
    EconomicValuation,
    MapEconomicProfile,
    MapEconomicProfileError,
    OdPairEconomicNode,
)


@dataclass(frozen=True)
class TripEconomicContext:
    """Selectors for one observed trip or incremental delay record."""

    trip_id: str = ""
    od_pair_id: str = ""
    origin_building_id: str = ""
    destination_building_id: str = ""
    origin_zone_id: str = ""
    destination_zone_id: str = ""
    route_edge_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedValuation:
    valuation: EconomicValuation
    resolution_level: str
    matched_id: str
    matched_corridor_ids: tuple[str, ...] = ()

    @property
    def is_source_backed(self) -> bool:
        return self.valuation.is_source_backed


def resolve_trip_valuation(
    profile: MapEconomicProfile,
    context: TripEconomicContext,
) -> ResolvedValuation:
    """Resolve OD -> building -> zone -> corridor -> global, in that order."""

    if context.od_pair_id:
        pair = profile.od_pairs.get(context.od_pair_id)
        if pair is not None:
            return ResolvedValuation(
                valuation=profile.valuations[pair.valuation_id],
                resolution_level="od_pair",
                matched_id=pair.od_pair_id,
                matched_corridor_ids=pair.corridor_ids,
            )

    matching_pairs = [
        pair for pair in profile.od_pairs.values() if _od_pair_matches(profile, pair, context)
    ]
    if matching_pairs:
        pair = max(matching_pairs, key=lambda item: (_od_specificity(item), item.od_pair_id))
        return ResolvedValuation(
            valuation=profile.valuations[pair.valuation_id],
            resolution_level="od_pair",
            matched_id=pair.od_pair_id,
            matched_corridor_ids=pair.corridor_ids,
        )

    for building_id in (context.destination_building_id, context.origin_building_id):
        building = profile.buildings.get(building_id)
        if building is not None and building.valuation_id:
            return ResolvedValuation(
                valuation=profile.valuations[building.valuation_id],
                resolution_level="building",
                matched_id=building.building_id,
            )

    origin_zone_id = context.origin_zone_id or _building_zone(profile, context.origin_building_id)
    destination_zone_id = context.destination_zone_id or _building_zone(
        profile, context.destination_building_id
    )
    for zone_id in (destination_zone_id, origin_zone_id):
        zone = profile.zones.get(zone_id)
        if zone is not None and zone.valuation_id:
            return ResolvedValuation(
                valuation=profile.valuations[zone.valuation_id],
                resolution_level="zone",
                matched_id=zone.zone_id,
            )

    corridor = _best_corridor(profile, context.route_edge_ids)
    if corridor is not None:
        return ResolvedValuation(
            valuation=profile.valuations[corridor.valuation_id],
            resolution_level="corridor",
            matched_id=corridor.corridor_id,
            matched_corridor_ids=(corridor.corridor_id,),
        )

    global_valuation = profile.valuations.get(profile.global_valuation_id)
    if global_valuation is None:
        raise MapEconomicProfileError("profile has no resolvable global valuation")
    return ResolvedValuation(
        valuation=global_valuation,
        resolution_level="global",
        matched_id=profile.global_valuation_id,
    )


def audit_profile_coverage(
    profile: MapEconomicProfile,
    *,
    demand_weights_by_od_pair: dict[str, float] | None = None,
    demand_weights_are_reviewed: bool = False,
) -> CoverageReport:
    """Audit structural and economic calibration coverage independently."""

    eligible = [building for building in profile.buildings.values() if building.demand_enabled]
    exact = sum(building.mapping_method == "exact_anchor" for building in eligible)
    derived = sum(building.mapping_method == "derived_nearest_edge" for building in eligible)
    unmapped_edges = sum(
        building.mapping_method == "unmapped" or not building.edge_ids for building in eligible
    )
    denominator = len(eligible)
    structural_ratio = _ratio(exact + derived, denominator)

    resolution_counts = {
        "od_pair": 0,
        "building": 0,
        "zone": 0,
        "corridor": 0,
        "global": 0,
        "unmapped": 0,
    }
    source_backed = 0
    for building in eligible:
        try:
            resolved = resolve_trip_valuation(
                profile,
                TripEconomicContext(destination_building_id=building.building_id),
            )
        except MapEconomicProfileError:
            resolution_counts["unmapped"] += 1
            continue
        resolution_counts[resolved.resolution_level] += 1
        if resolved.is_source_backed:
            source_backed += 1

    non_global = denominator - resolution_counts["global"] - resolution_counts["unmapped"]
    non_global_ratio = _ratio(non_global, denominator)
    source_backed_ratio = _ratio(source_backed, denominator)

    if demand_weights_by_od_pair is None:
        weighted_pairs = [
            pair
            for pair in profile.od_pairs.values()
            if pair.annual_trips is not None and pair.annual_trips.estimate > 0
        ]
        weights = {
            pair.od_pair_id: pair.annual_trips.estimate
            for pair in weighted_pairs
            if pair.annual_trips is not None
        }
        weights_reviewed = bool(weighted_pairs) and all(
            pair.annual_trips is not None
            and not pair.annual_trips.is_assumption
            and pair.annual_trips.evidence_grade in {"A", "B", "C"}
            for pair in weighted_pairs
        )
    else:
        weights = demand_weights_by_od_pair
        weights_reviewed = demand_weights_are_reviewed
    if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise MapEconomicProfileError("demand weights must be finite and non-negative")
    positive_weights = {
        pair_id: float(weight) for pair_id, weight in weights.items() if float(weight) > 0
    }
    demand_weight_total = sum(positive_weights.values())
    if demand_weight_total > 0:
        demand_non_global_weight = 0.0
        demand_source_backed_weight = 0.0
        for pair_id, weight in positive_weights.items():
            # Unmapped observed demand remains in the denominator with zero coverage.
            if pair_id not in profile.od_pairs:
                continue
            resolved = resolve_trip_valuation(profile, TripEconomicContext(od_pair_id=pair_id))
            if resolved.resolution_level != "global":
                demand_non_global_weight += weight
            if resolved.is_source_backed:
                demand_source_backed_weight += weight
        demand_status = "available_reviewed" if weights_reviewed else "assumption_only"
        demand_non_global_ratio: float | None = demand_non_global_weight / demand_weight_total
        demand_source_backed_ratio: float | None = demand_source_backed_weight / demand_weight_total
    else:
        demand_status = "unavailable"
        demand_weight_total = 0.0
        demand_non_global_ratio = None
        demand_source_backed_ratio = None

    reasons: list[str] = []
    policy = profile.coverage_policy
    if structural_ratio < policy.minimum_structural_edge_mapping_ratio:
        reasons.append(
            "structural edge mapping coverage is below the configured production threshold"
        )
    if non_global_ratio < policy.minimum_non_global_valuation_ratio:
        reasons.append(
            "non-global economic valuation coverage is below the configured production threshold"
        )
    if source_backed_ratio < policy.minimum_source_backed_valuation_ratio:
        reasons.append(
            "source-backed economic calibration coverage is below "
            "the configured production threshold"
        )
    if policy.require_demand_weighted_coverage and demand_status != "available_reviewed":
        reasons.append(
            "reviewed demand-weighted coverage is unavailable; assumption-only weights do not pass"
        )
    if (
        demand_non_global_ratio is not None
        and demand_non_global_ratio < policy.minimum_demand_weighted_non_global_ratio
    ):
        reasons.append("demand-weighted non-global coverage is below the production threshold")
    if (
        demand_source_backed_ratio is not None
        and demand_source_backed_ratio < policy.minimum_demand_weighted_source_backed_ratio
    ):
        reasons.append("demand-weighted source-backed coverage is below the production threshold")
    if profile.metadata.status != "approved":
        reasons.append("profile status is not approved")
    if profile.metadata.map_scope_status == "unverified_boundary":
        reasons.append("map boundary is unverified; District 7-specific claims are blocked")

    return CoverageReport(
        total_prepared_entities=len(profile.buildings),
        demand_eligible_entities=denominator,
        excluded_background_entities=len(profile.buildings) - denominator,
        exact_edge_mapping_count=exact,
        derived_edge_mapping_count=derived,
        unmapped_edge_count=unmapped_edges,
        structural_edge_mapping_ratio=round(structural_ratio, 6),
        od_pair_resolution_count=resolution_counts["od_pair"],
        building_resolution_count=resolution_counts["building"],
        zone_resolution_count=resolution_counts["zone"],
        corridor_resolution_count=resolution_counts["corridor"],
        global_resolution_count=resolution_counts["global"],
        economic_unmapped_count=resolution_counts["unmapped"],
        non_global_valuation_ratio=round(non_global_ratio, 6),
        source_backed_valuation_ratio=round(source_backed_ratio, 6),
        demand_weighted_coverage_status=demand_status,
        demand_weight_total=(round(demand_weight_total, 6) if demand_weight_total else None),
        demand_weighted_non_global_ratio=(
            None if demand_non_global_ratio is None else round(demand_non_global_ratio, 6)
        ),
        demand_weighted_source_backed_ratio=(
            None if demand_source_backed_ratio is None else round(demand_source_backed_ratio, 6)
        ),
        production_gate_passed=not reasons,
        production_gate_reasons=tuple(reasons),
    )


def assert_production_ready(profile: MapEconomicProfile) -> None:
    report = audit_profile_coverage(profile)
    if not report.production_gate_passed:
        raise MapEconomicProfileError(
            "map-economic production gate failed: " + "; ".join(report.production_gate_reasons)
        )


def _building_zone(profile: MapEconomicProfile, building_id: str) -> str:
    building = profile.buildings.get(building_id)
    return "" if building is None else building.zone_id


def _best_corridor(
    profile: MapEconomicProfile, route_edge_ids: tuple[str, ...]
) -> CorridorEconomicNode | None:
    route_edges = set(route_edge_ids)
    if not route_edges:
        return None
    candidates = []
    for corridor in profile.corridors.values():
        if not corridor.valuation_id:
            continue
        overlap = len(route_edges.intersection(corridor.edge_ids))
        if overlap:
            candidates.append((overlap / len(route_edges), overlap, corridor.corridor_id, corridor))
    return max(candidates)[-1] if candidates else None


def _od_pair_matches(
    profile: MapEconomicProfile,
    pair: OdPairEconomicNode,
    context: TripEconomicContext,
) -> bool:
    origin_zone = context.origin_zone_id or _building_zone(profile, context.origin_building_id)
    destination_zone = context.destination_zone_id or _building_zone(
        profile, context.destination_building_id
    )
    checks = (
        (pair.origin_building_id, context.origin_building_id),
        (pair.destination_building_id, context.destination_building_id),
        (pair.origin_zone_id, origin_zone),
        (pair.destination_zone_id, destination_zone),
    )
    if any(expected and expected != actual for expected, actual in checks):
        return False
    route_edges = set(context.route_edge_ids)
    # A declared route is an ordered full route, not a set of intersecting roads.
    # Corridor selectors provide the separate partial-route exposure mechanism.
    if pair.route_edge_ids and pair.route_edge_ids != context.route_edge_ids:
        return False
    if pair.corridor_ids:
        context_corridors: set[str] = set()
        for edge_id in route_edges:
            edge = profile.edges.get(edge_id)
            if edge is not None:
                context_corridors.update(edge.corridor_ids)
        if not context_corridors.intersection(pair.corridor_ids):
            return False
    return True


def _od_specificity(pair: OdPairEconomicNode) -> int:
    return (
        100 * bool(pair.origin_building_id)
        + 100 * bool(pair.destination_building_id)
        + 10 * bool(pair.origin_zone_id)
        + 10 * bool(pair.destination_zone_id)
        + bool(pair.route_edge_ids)
        + bool(pair.corridor_ids)
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
