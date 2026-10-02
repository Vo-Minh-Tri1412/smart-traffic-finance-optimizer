"""Versioned data model for map-specific economic value and reward inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MAP_ECONOMIC_PROFILE_SCHEMA_VERSION = "map_economic_profile.v1"

EVIDENCE_GRADES = frozenset({"A", "B", "C", "D", "U"})
VALUE_UNITS = frozenset(
    {
        "VND",
        "VND/person_hour",
        "persons/trip",
        "ratio",
        "seconds/trip",
        "trips/year",
        "hours/year",
        "person_hours/year",
    }
)


class MapEconomicProfileError(ValueError):
    """Raised when a map-economic profile violates its schema or references."""


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    title: str
    source_type: str
    publisher: str = ""
    uri: str = ""
    publication_date: str = ""
    accessed_at: str = ""
    geographic_scope: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ValueRecord:
    """An estimate with interval, units, provenance, and assumption status."""

    estimate: float
    lower: float
    upper: float
    unit: str
    evidence_grade: str
    source_ids: tuple[str, ...]
    is_assumption: bool
    price_year: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "unit": self.unit,
            "price_year": self.price_year,
            "evidence_grade": self.evidence_grade,
            "source_ids": list(self.source_ids),
            "is_assumption": self.is_assumption,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EconomicValuation:
    valuation_id: str
    value_of_time: ValueRecord
    reliability_value: ValueRecord
    persons_per_trip: ValueRecord
    essential_service_multiplier: ValueRecord
    economic_flow_multiplier: ValueRecord
    description: str = ""

    @property
    def is_source_backed(self) -> bool:
        records = (
            self.value_of_time,
            self.reliability_value,
            self.persons_per_trip,
            self.essential_service_multiplier,
            self.economic_flow_multiplier,
        )
        return all(
            not record.is_assumption
            and record.evidence_grade in {"A", "B", "C"}
            and bool(record.source_ids)
            for record in records
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valuation_id": self.valuation_id,
            "description": self.description,
            "value_of_time": self.value_of_time.to_dict(),
            "reliability_value": self.reliability_value.to_dict(),
            "persons_per_trip": self.persons_per_trip.to_dict(),
            "essential_service_multiplier": self.essential_service_multiplier.to_dict(),
            "economic_flow_multiplier": self.economic_flow_multiplier.to_dict(),
        }


@dataclass(frozen=True)
class BuildingEconomicNode:
    building_id: str
    name: str
    entity_kind: str
    zone_id: str
    edge_ids: tuple[str, ...]
    mapping_method: str
    nearest_edge_distance_m: float | None
    demand_enabled: bool
    source_element_id: str = ""
    confidence: float | None = None
    valuation_id: str = ""
    source_tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_id": self.building_id,
            "name": self.name,
            "entity_kind": self.entity_kind,
            "zone_id": self.zone_id,
            "edge_ids": list(self.edge_ids),
            "mapping_method": self.mapping_method,
            "nearest_edge_distance_m": self.nearest_edge_distance_m,
            "demand_enabled": self.demand_enabled,
            "source_element_id": self.source_element_id,
            "confidence": self.confidence,
            "valuation_id": self.valuation_id,
            "source_tags": dict(sorted(self.source_tags.items())),
        }


@dataclass(frozen=True)
class ZoneEconomicNode:
    zone_id: str
    name: str
    zone_type: str
    building_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    valuation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "building_ids": list(self.building_ids),
            "edge_ids": list(self.edge_ids),
            "valuation_id": self.valuation_id,
        }


@dataclass(frozen=True)
class EdgeEconomicNode:
    edge_id: str
    zone_ids: tuple[str, ...] = ()
    building_ids: tuple[str, ...] = ()
    corridor_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "zone_ids": list(self.zone_ids),
            "building_ids": list(self.building_ids),
            "corridor_ids": list(self.corridor_ids),
        }


@dataclass(frozen=True)
class CorridorEconomicNode:
    corridor_id: str
    name: str
    edge_ids: tuple[str, ...]
    zone_ids: tuple[str, ...] = ()
    valuation_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "corridor_id": self.corridor_id,
            "name": self.name,
            "edge_ids": list(self.edge_ids),
            "zone_ids": list(self.zone_ids),
            "valuation_id": self.valuation_id,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class OdPairEconomicNode:
    od_pair_id: str
    valuation_id: str
    origin_building_id: str = ""
    destination_building_id: str = ""
    origin_zone_id: str = ""
    destination_zone_id: str = ""
    route_edge_ids: tuple[str, ...] = ()
    corridor_ids: tuple[str, ...] = ()
    annual_trips: ValueRecord | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "od_pair_id": self.od_pair_id,
            "valuation_id": self.valuation_id,
            "origin_building_id": self.origin_building_id,
            "destination_building_id": self.destination_building_id,
            "origin_zone_id": self.origin_zone_id,
            "destination_zone_id": self.destination_zone_id,
            "route_edge_ids": list(self.route_edge_ids),
            "corridor_ids": list(self.corridor_ids),
            "annual_trips": None if self.annual_trips is None else self.annual_trips.to_dict(),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CandidateOdImpact:
    od_pair_id: str
    route_exposure_fraction: ValueRecord | None = None
    delay_reduction_seconds_per_trip: ValueRecord | None = None
    annual_trips: ValueRecord | None = None
    persons_per_trip: ValueRecord | None = None
    annual_person_delay_saved_hours: ValueRecord | None = None
    annual_economic_benefit_vnd: ValueRecord | None = None
    derivation_method: str = "explicit_od_impact"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "od_pair_id": self.od_pair_id,
            "derivation_method": self.derivation_method,
            "notes": self.notes,
        }
        for name in (
            "route_exposure_fraction",
            "delay_reduction_seconds_per_trip",
            "annual_trips",
            "persons_per_trip",
            "annual_person_delay_saved_hours",
            "annual_economic_benefit_vnd",
        ):
            value = getattr(self, name)
            payload[name] = None if value is None else value.to_dict()
        return payload


@dataclass(frozen=True)
class InvestmentCandidateEconomicNode:
    candidate_id: str
    name: str
    capital_cost_vnd: ValueRecord
    annual_operating_cost_vnd: ValueRecord
    junction_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    corridor_ids: tuple[str, ...] = ()
    od_impacts: tuple[CandidateOdImpact, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "junction_ids": list(self.junction_ids),
            "edge_ids": list(self.edge_ids),
            "corridor_ids": list(self.corridor_ids),
            "capital_cost_vnd": self.capital_cost_vnd.to_dict(),
            "annual_operating_cost_vnd": self.annual_operating_cost_vnd.to_dict(),
            "od_impacts": [impact.to_dict() for impact in self.od_impacts],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RewardPolicy:
    normalization_vnd_per_step: ValueRecord
    clip_min: float
    clip_max: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization_vnd_per_step": self.normalization_vnd_per_step.to_dict(),
            "clip_min": self.clip_min,
            "clip_max": self.clip_max,
        }


@dataclass(frozen=True)
class CoveragePolicy:
    minimum_structural_edge_mapping_ratio: float
    minimum_non_global_valuation_ratio: float
    minimum_source_backed_valuation_ratio: float
    require_demand_weighted_coverage: bool
    minimum_demand_weighted_non_global_ratio: float
    minimum_demand_weighted_source_backed_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageReport:
    total_prepared_entities: int
    demand_eligible_entities: int
    excluded_background_entities: int
    exact_edge_mapping_count: int
    derived_edge_mapping_count: int
    unmapped_edge_count: int
    structural_edge_mapping_ratio: float
    od_pair_resolution_count: int
    building_resolution_count: int
    zone_resolution_count: int
    corridor_resolution_count: int
    global_resolution_count: int
    economic_unmapped_count: int
    non_global_valuation_ratio: float
    source_backed_valuation_ratio: float
    demand_weighted_coverage_status: str
    demand_weight_total: float | None
    demand_weighted_non_global_ratio: float | None
    demand_weighted_source_backed_ratio: float | None
    production_gate_passed: bool
    production_gate_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["production_gate_reasons"] = list(self.production_gate_reasons)
        return payload


@dataclass(frozen=True)
class MapEconomicMetadata:
    profile_id: str
    status: str
    map_project_id: str
    currency: str
    price_year: int
    generated_at: str
    map_scope_status: str
    source_net_sha256: str
    semantic_overlay_sha256: str
    caveats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "map_project_id": self.map_project_id,
            "currency": self.currency,
            "price_year": self.price_year,
            "generated_at": self.generated_at,
            "map_scope_status": self.map_scope_status,
            "source_net_sha256": self.source_net_sha256,
            "semantic_overlay_sha256": self.semantic_overlay_sha256,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class MapEconomicProfile:
    metadata: MapEconomicMetadata
    sources: dict[str, EvidenceSource]
    valuations: dict[str, EconomicValuation]
    global_valuation_id: str
    buildings: dict[str, BuildingEconomicNode]
    zones: dict[str, ZoneEconomicNode]
    edges: dict[str, EdgeEconomicNode]
    corridors: dict[str, CorridorEconomicNode]
    od_pairs: dict[str, OdPairEconomicNode]
    investment_candidates: dict[str, InvestmentCandidateEconomicNode]
    reward_policy: RewardPolicy
    coverage_policy: CoveragePolicy
    coverage: CoverageReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MAP_ECONOMIC_PROFILE_SCHEMA_VERSION,
            "metadata": self.metadata.to_dict(),
            "sources": [self.sources[key].__dict__ for key in sorted(self.sources)],
            "valuations": [self.valuations[key].to_dict() for key in sorted(self.valuations)],
            "global_valuation_id": self.global_valuation_id,
            "buildings": [self.buildings[key].to_dict() for key in sorted(self.buildings)],
            "zones": [self.zones[key].to_dict() for key in sorted(self.zones)],
            "edges": [self.edges[key].to_dict() for key in sorted(self.edges)],
            "corridors": [self.corridors[key].to_dict() for key in sorted(self.corridors)],
            "od_pairs": [self.od_pairs[key].to_dict() for key in sorted(self.od_pairs)],
            "investment_candidates": [
                self.investment_candidates[key].to_dict()
                for key in sorted(self.investment_candidates)
            ],
            "reward_policy": self.reward_policy.to_dict(),
            "coverage_policy": self.coverage_policy.to_dict(),
            "coverage": None if self.coverage is None else self.coverage.to_dict(),
        }
