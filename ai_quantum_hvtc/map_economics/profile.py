"""Load, validate, and serialize ``map_economic_profile.v1`` artifacts."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .models import (
    EVIDENCE_GRADES,
    MAP_ECONOMIC_PROFILE_SCHEMA_VERSION,
    VALUE_UNITS,
    BuildingEconomicNode,
    CandidateOdImpact,
    CorridorEconomicNode,
    CoveragePolicy,
    CoverageReport,
    EconomicValuation,
    EdgeEconomicNode,
    EvidenceSource,
    InvestmentCandidateEconomicNode,
    MapEconomicMetadata,
    MapEconomicProfile,
    MapEconomicProfileError,
    OdPairEconomicNode,
    RewardPolicy,
    ValueRecord,
    ZoneEconomicNode,
)


def load_map_economic_profile(path: Path | str) -> MapEconomicProfile:
    profile_path = Path(path)
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MapEconomicProfileError(f"{profile_path}: cannot read profile: {exc}") from exc
    if not isinstance(data, dict):
        raise MapEconomicProfileError(f"{profile_path}: root value must be an object")
    return map_economic_profile_from_mapping(data, source=str(profile_path))


def map_economic_profile_from_mapping(
    data: Mapping[str, Any], *, source: str = "<mapping>"
) -> MapEconomicProfile:
    schema_version = _required_str(data, "schema_version", source)
    if schema_version != MAP_ECONOMIC_PROFILE_SCHEMA_VERSION:
        raise MapEconomicProfileError(
            f"{source}: unsupported schema_version {schema_version!r}; "
            f"expected {MAP_ECONOMIC_PROFILE_SCHEMA_VERSION!r}"
        )

    metadata = _parse_metadata(_required_object(data, "metadata", source), source)
    sources = _indexed(
        _required_array(data, "sources", source),
        "source_id",
        lambda item: _parse_source(item, source),
        source,
    )
    valuations = _indexed(
        _required_array(data, "valuations", source),
        "valuation_id",
        lambda item: _parse_valuation(item, source),
        source,
    )
    buildings = _indexed(
        _array(data, "buildings", source),
        "building_id",
        lambda item: _parse_building(item, source),
        source,
    )
    zones = _indexed(
        _array(data, "zones", source),
        "zone_id",
        lambda item: _parse_zone(item, source),
        source,
    )
    edges = _indexed(
        _array(data, "edges", source),
        "edge_id",
        lambda item: _parse_edge(item, source),
        source,
    )
    corridors = _indexed(
        _array(data, "corridors", source),
        "corridor_id",
        lambda item: _parse_corridor(item, source),
        source,
    )
    od_pairs = _indexed(
        _array(data, "od_pairs", source),
        "od_pair_id",
        lambda item: _parse_od_pair(item, source),
        source,
    )
    candidates = _indexed(
        _array(data, "investment_candidates", source),
        "candidate_id",
        lambda item: _parse_candidate(item, source),
        source,
    )
    profile = MapEconomicProfile(
        metadata=metadata,
        sources=sources,
        valuations=valuations,
        global_valuation_id=_required_str(data, "global_valuation_id", source),
        buildings=buildings,
        zones=zones,
        edges=edges,
        corridors=corridors,
        od_pairs=od_pairs,
        investment_candidates=candidates,
        reward_policy=_parse_reward_policy(_required_object(data, "reward_policy", source), source),
        coverage_policy=_parse_coverage_policy(
            _required_object(data, "coverage_policy", source), source
        ),
        coverage=_parse_coverage(data.get("coverage"), source),
    )
    errors = validate_map_economic_profile(profile)
    if errors:
        joined = "\n- ".join(errors)
        raise MapEconomicProfileError(f"{source}: invalid map-economic profile:\n- {joined}")
    return profile


def save_map_economic_profile(profile: MapEconomicProfile, path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def validate_map_economic_profile(profile: MapEconomicProfile) -> list[str]:
    errors: list[str] = []
    if profile.metadata.currency != "VND":
        errors.append("metadata.currency must be VND")
    if profile.metadata.price_year < 1900:
        errors.append("metadata.price_year must be an explicit four-digit price year")
    if profile.metadata.status not in {"draft", "reviewed", "approved"}:
        errors.append("metadata.status must be draft, reviewed, or approved")
    if profile.metadata.map_scope_status not in {
        "unverified_boundary",
        "reviewed_roi",
        "verified_district",
    }:
        errors.append("metadata.map_scope_status is not supported")
    if not profile.sources:
        errors.append("sources must contain at least one provenance record")
    if profile.global_valuation_id not in profile.valuations:
        errors.append(
            f"global_valuation_id references unknown valuation: {profile.global_valuation_id}"
        )

    for valuation in profile.valuations.values():
        records = {
            "value_of_time": (valuation.value_of_time, "VND/person_hour"),
            "reliability_value": (valuation.reliability_value, "VND/person_hour"),
            "persons_per_trip": (valuation.persons_per_trip, "persons/trip"),
            "essential_service_multiplier": (valuation.essential_service_multiplier, "ratio"),
            "economic_flow_multiplier": (valuation.economic_flow_multiplier, "ratio"),
        }
        for name, (record, expected_unit) in records.items():
            errors.extend(
                _validate_value_record(
                    record,
                    f"valuations.{valuation.valuation_id}.{name}",
                    profile,
                    expected_unit=expected_unit,
                )
            )
        if valuation.persons_per_trip.lower <= 0:
            errors.append(f"valuations.{valuation.valuation_id}.persons_per_trip must be > 0")
        if valuation.essential_service_multiplier.lower <= 0:
            errors.append(
                f"valuations.{valuation.valuation_id}.essential_service_multiplier must be > 0"
            )
        if valuation.economic_flow_multiplier.lower <= 0:
            errors.append(
                f"valuations.{valuation.valuation_id}.economic_flow_multiplier must be > 0"
            )

    for building in profile.buildings.values():
        if building.zone_id and building.zone_id not in profile.zones:
            errors.append(
                f"buildings.{building.building_id} references unknown zone {building.zone_id}"
            )
        errors.extend(_unknown_refs("edge", building.edge_ids, profile.edges, building.building_id))
        if building.valuation_id and building.valuation_id not in profile.valuations:
            errors.append(
                f"buildings.{building.building_id} references unknown valuation "
                f"{building.valuation_id}"
            )
        if building.mapping_method not in {"exact_anchor", "derived_nearest_edge", "unmapped"}:
            errors.append(f"buildings.{building.building_id} has invalid mapping_method")
        if building.mapping_method == "unmapped" and building.edge_ids:
            errors.append(f"buildings.{building.building_id} is unmapped but has edge_ids")
        if building.mapping_method != "unmapped" and not building.edge_ids:
            errors.append(f"buildings.{building.building_id} is mapped but has no edge_ids")
        if building.confidence is not None and not 0 <= building.confidence <= 1:
            errors.append(f"buildings.{building.building_id}.confidence must be within [0, 1]")
        if building.nearest_edge_distance_m is not None and building.nearest_edge_distance_m < 0:
            errors.append(f"buildings.{building.building_id} has negative edge distance")

    for zone in profile.zones.values():
        errors.extend(_unknown_refs("building", zone.building_ids, profile.buildings, zone.zone_id))
        errors.extend(_unknown_refs("edge", zone.edge_ids, profile.edges, zone.zone_id))
        if zone.valuation_id and zone.valuation_id not in profile.valuations:
            errors.append(f"zones.{zone.zone_id} references unknown valuation {zone.valuation_id}")

    for edge in profile.edges.values():
        errors.extend(_unknown_refs("zone", edge.zone_ids, profile.zones, edge.edge_id))
        errors.extend(_unknown_refs("building", edge.building_ids, profile.buildings, edge.edge_id))
        errors.extend(_unknown_refs("corridor", edge.corridor_ids, profile.corridors, edge.edge_id))

    for corridor in profile.corridors.values():
        errors.extend(_unknown_refs("edge", corridor.edge_ids, profile.edges, corridor.corridor_id))
        errors.extend(_unknown_refs("zone", corridor.zone_ids, profile.zones, corridor.corridor_id))
        if corridor.valuation_id and corridor.valuation_id not in profile.valuations:
            errors.append(
                f"corridors.{corridor.corridor_id} references unknown valuation "
                f"{corridor.valuation_id}"
            )

    for pair in profile.od_pairs.values():
        if pair.valuation_id not in profile.valuations:
            errors.append(f"od_pairs.{pair.od_pair_id} references unknown valuation")
        errors.extend(
            _unknown_optional_ref(
                "building", pair.origin_building_id, profile.buildings, pair.od_pair_id
            )
        )
        errors.extend(
            _unknown_optional_ref(
                "building", pair.destination_building_id, profile.buildings, pair.od_pair_id
            )
        )
        errors.extend(
            _unknown_optional_ref("zone", pair.origin_zone_id, profile.zones, pair.od_pair_id)
        )
        errors.extend(
            _unknown_optional_ref("zone", pair.destination_zone_id, profile.zones, pair.od_pair_id)
        )
        errors.extend(_unknown_refs("edge", pair.route_edge_ids, profile.edges, pair.od_pair_id))
        errors.extend(
            _unknown_refs("corridor", pair.corridor_ids, profile.corridors, pair.od_pair_id)
        )
        if not any(
            (
                pair.origin_building_id,
                pair.destination_building_id,
                pair.origin_zone_id,
                pair.destination_zone_id,
                pair.route_edge_ids,
                pair.corridor_ids,
            )
        ):
            errors.append(f"od_pairs.{pair.od_pair_id} has no map selector")
        if pair.annual_trips is not None:
            errors.extend(
                _validate_value_record(
                    pair.annual_trips,
                    f"od_pairs.{pair.od_pair_id}.annual_trips",
                    profile,
                    expected_unit="trips/year",
                )
            )

    for candidate in profile.investment_candidates.values():
        errors.extend(
            _validate_value_record(
                candidate.capital_cost_vnd,
                f"investment_candidates.{candidate.candidate_id}.capital_cost_vnd",
                profile,
                expected_unit="VND",
            )
        )
        errors.extend(
            _validate_value_record(
                candidate.annual_operating_cost_vnd,
                f"investment_candidates.{candidate.candidate_id}.annual_operating_cost_vnd",
                profile,
                expected_unit="VND",
            )
        )
        errors.extend(
            _unknown_refs("edge", candidate.edge_ids, profile.edges, candidate.candidate_id)
        )
        errors.extend(
            _unknown_refs(
                "corridor", candidate.corridor_ids, profile.corridors, candidate.candidate_id
            )
        )
        for impact in candidate.od_impacts:
            errors.extend(_validate_candidate_impact(candidate.candidate_id, impact, profile))

    errors.extend(
        _validate_value_record(
            profile.reward_policy.normalization_vnd_per_step,
            "reward_policy.normalization_vnd_per_step",
            profile,
            expected_unit="VND",
        )
    )
    if profile.reward_policy.normalization_vnd_per_step.lower <= 0:
        errors.append("reward_policy.normalization_vnd_per_step must be > 0")
    if profile.reward_policy.clip_min >= profile.reward_policy.clip_max:
        errors.append("reward_policy.clip_min must be less than clip_max")
    for field_name, value in profile.coverage_policy.to_dict().items():
        if isinstance(value, bool):
            continue
        if not 0 <= float(value) <= 1:
            errors.append(f"coverage_policy.{field_name} must be within [0, 1]")
    return errors


def _validate_candidate_impact(
    candidate_id: str, impact: CandidateOdImpact, profile: MapEconomicProfile
) -> list[str]:
    prefix = f"investment_candidates.{candidate_id}.od_impacts.{impact.od_pair_id}"
    errors: list[str] = []
    if impact.od_pair_id not in profile.od_pairs:
        errors.append(f"{prefix} references unknown od_pair_id")
    fields = {
        "route_exposure_fraction": (impact.route_exposure_fraction, "ratio"),
        "delay_reduction_seconds_per_trip": (
            impact.delay_reduction_seconds_per_trip,
            "seconds/trip",
        ),
        "annual_trips": (impact.annual_trips, "trips/year"),
        "persons_per_trip": (impact.persons_per_trip, "persons/trip"),
        "annual_person_delay_saved_hours": (
            impact.annual_person_delay_saved_hours,
            "person_hours/year",
        ),
        "annual_economic_benefit_vnd": (impact.annual_economic_benefit_vnd, "VND"),
    }
    for name, (record, unit) in fields.items():
        if record is not None:
            errors.extend(
                _validate_value_record(
                    record,
                    f"{prefix}.{name}",
                    profile,
                    unit,
                    allow_signed=name
                    in {
                        "delay_reduction_seconds_per_trip",
                        "annual_person_delay_saved_hours",
                        "annual_economic_benefit_vnd",
                    },
                )
            )
    representations = sum(
        value is not None
        for value in (
            impact.delay_reduction_seconds_per_trip,
            impact.annual_person_delay_saved_hours,
            impact.annual_economic_benefit_vnd,
        )
    )
    if representations > 1:
        errors.append(
            f"{prefix} must use one marginal benefit representation, not overlapping totals"
        )
    if impact.route_exposure_fraction is not None and impact.route_exposure_fraction.upper > 1:
        errors.append(f"{prefix}.route_exposure_fraction must be within [0, 1]")
    has_annual = (
        impact.annual_person_delay_saved_hours is not None
        or impact.annual_economic_benefit_vnd is not None
    )
    if impact.delay_reduction_seconds_per_trip is None and not has_annual:
        errors.append(f"{prefix} must provide a delay or annual benefit estimate")
    if (
        impact.delay_reduction_seconds_per_trip is not None
        and not has_annual
        and (impact.annual_trips is None or impact.persons_per_trip is None)
    ):
        errors.append(
            f"{prefix} needs annual_trips and persons_per_trip to annualize per-trip delay"
        )
    if impact.derivation_method not in {"explicit_od_impact", "derived_route_overlap"}:
        errors.append(f"{prefix}.derivation_method is not supported")
    return errors


def _validate_value_record(
    record: ValueRecord,
    name: str,
    profile: MapEconomicProfile,
    expected_unit: str | None = None,
    *,
    allow_signed: bool = False,
) -> list[str]:
    errors: list[str] = []
    if record.unit not in VALUE_UNITS:
        errors.append(f"{name}.unit {record.unit!r} is unsupported")
    if expected_unit is not None and record.unit != expected_unit:
        errors.append(f"{name}.unit must be {expected_unit}")
    if record.evidence_grade not in EVIDENCE_GRADES:
        errors.append(f"{name}.evidence_grade is unsupported")
    if record.lower > record.estimate or record.estimate > record.upper:
        errors.append(f"{name} must satisfy lower <= estimate <= upper")
    if record.lower < 0 and not allow_signed:
        errors.append(f"{name}.lower must be non-negative")
    if not record.source_ids:
        errors.append(f"{name}.source_ids must not be empty")
    for source_id in record.source_ids:
        if source_id not in profile.sources:
            errors.append(f"{name} references unknown source_id {source_id}")
    if record.unit.startswith("VND"):
        if record.price_year != profile.metadata.price_year:
            errors.append(
                f"{name}.price_year must match metadata.price_year ({profile.metadata.price_year})"
            )
    elif record.price_year is not None:
        errors.append(f"{name}.price_year is only allowed for monetary units")
    if record.is_assumption and record.evidence_grade not in {"D", "U"}:
        errors.append(f"{name}: assumptions must use evidence grade D or U")
    if not record.is_assumption and record.evidence_grade in {"D", "U"}:
        errors.append(f"{name}: grade D or U must be marked as an assumption")
    if not all(math.isfinite(value) for value in (record.lower, record.estimate, record.upper)):
        errors.append(f"{name}: values must be finite")
    return errors


def _parse_metadata(data: Mapping[str, Any], source: str) -> MapEconomicMetadata:
    return MapEconomicMetadata(
        profile_id=_required_str(data, "profile_id", source),
        status=_required_str(data, "status", source),
        map_project_id=_required_str(data, "map_project_id", source),
        currency=_required_str(data, "currency", source),
        price_year=_required_int(data, "price_year", source),
        generated_at=_required_str(data, "generated_at", source),
        map_scope_status=_required_str(data, "map_scope_status", source),
        source_net_sha256=_required_str(data, "source_net_sha256", source),
        semantic_overlay_sha256=_required_str(data, "semantic_overlay_sha256", source),
        caveats=_strings(data.get("caveats", []), f"{source}.metadata.caveats"),
    )


def _parse_source(data: Mapping[str, Any], source: str) -> EvidenceSource:
    return EvidenceSource(
        source_id=_required_str(data, "source_id", source),
        title=_required_str(data, "title", source),
        source_type=_required_str(data, "source_type", source),
        publisher=str(data.get("publisher", "")),
        uri=str(data.get("uri", "")),
        publication_date=str(data.get("publication_date", "")),
        accessed_at=str(data.get("accessed_at", "")),
        geographic_scope=str(data.get("geographic_scope", "")),
        notes=str(data.get("notes", "")),
    )


def _parse_value(data: Mapping[str, Any], source: str) -> ValueRecord:
    is_assumption = data.get("is_assumption")
    if not isinstance(is_assumption, bool):
        raise MapEconomicProfileError(f"{source}: is_assumption must be a boolean")
    price_year = data.get("price_year")
    return ValueRecord(
        estimate=_required_float(data, "estimate", source),
        lower=_required_float(data, "lower", source),
        upper=_required_float(data, "upper", source),
        unit=_required_str(data, "unit", source),
        price_year=None if price_year is None else _required_int(data, "price_year", source),
        evidence_grade=_required_str(data, "evidence_grade", source),
        source_ids=_strings(data.get("source_ids", []), f"{source}.source_ids"),
        is_assumption=is_assumption,
        notes=str(data.get("notes", "")),
    )


def _parse_valuation(data: Mapping[str, Any], source: str) -> EconomicValuation:
    valuation_id = _required_str(data, "valuation_id", source)
    prefix = f"{source}.valuations.{valuation_id}"
    return EconomicValuation(
        valuation_id=valuation_id,
        description=str(data.get("description", "")),
        value_of_time=_parse_value(_required_object(data, "value_of_time", prefix), prefix),
        reliability_value=_parse_value(_required_object(data, "reliability_value", prefix), prefix),
        persons_per_trip=_parse_value(_required_object(data, "persons_per_trip", prefix), prefix),
        essential_service_multiplier=_parse_value(
            _required_object(data, "essential_service_multiplier", prefix), prefix
        ),
        economic_flow_multiplier=_parse_value(
            _required_object(data, "economic_flow_multiplier", prefix), prefix
        ),
    )


def _parse_building(data: Mapping[str, Any], source: str) -> BuildingEconomicNode:
    distance = data.get("nearest_edge_distance_m")
    confidence = data.get("confidence")
    source_tags = data.get("source_tags", {})
    if not isinstance(source_tags, dict):
        raise MapEconomicProfileError(f"{source}: source_tags must be an object")
    return BuildingEconomicNode(
        building_id=_required_str(data, "building_id", source),
        name=str(data.get("name", "")),
        entity_kind=_required_str(data, "entity_kind", source),
        zone_id=str(data.get("zone_id", "")),
        edge_ids=_strings(data.get("edge_ids", []), source),
        mapping_method=_required_str(data, "mapping_method", source),
        nearest_edge_distance_m=_optional_float(distance, f"{source}.nearest_edge_distance_m"),
        demand_enabled=_required_bool(data, "demand_enabled", source),
        source_element_id=str(data.get("source_element_id", "")),
        confidence=_optional_float(confidence, f"{source}.confidence"),
        valuation_id=str(data.get("valuation_id", "")),
        source_tags={str(key): str(value) for key, value in source_tags.items()},
    )


def _parse_zone(data: Mapping[str, Any], source: str) -> ZoneEconomicNode:
    return ZoneEconomicNode(
        zone_id=_required_str(data, "zone_id", source),
        name=str(data.get("name", "")),
        zone_type=_required_str(data, "zone_type", source),
        building_ids=_strings(data.get("building_ids", []), source),
        edge_ids=_strings(data.get("edge_ids", []), source),
        valuation_id=str(data.get("valuation_id", "")),
    )


def _parse_edge(data: Mapping[str, Any], source: str) -> EdgeEconomicNode:
    return EdgeEconomicNode(
        edge_id=_required_str(data, "edge_id", source),
        zone_ids=_strings(data.get("zone_ids", []), source),
        building_ids=_strings(data.get("building_ids", []), source),
        corridor_ids=_strings(data.get("corridor_ids", []), source),
    )


def _parse_corridor(data: Mapping[str, Any], source: str) -> CorridorEconomicNode:
    return CorridorEconomicNode(
        corridor_id=_required_str(data, "corridor_id", source),
        name=str(data.get("name", "")),
        edge_ids=_strings(data.get("edge_ids", []), source),
        zone_ids=_strings(data.get("zone_ids", []), source),
        valuation_id=str(data.get("valuation_id", "")),
        notes=str(data.get("notes", "")),
    )


def _parse_od_pair(data: Mapping[str, Any], source: str) -> OdPairEconomicNode:
    annual_trips = data.get("annual_trips")
    return OdPairEconomicNode(
        od_pair_id=_required_str(data, "od_pair_id", source),
        valuation_id=_required_str(data, "valuation_id", source),
        origin_building_id=str(data.get("origin_building_id", "")),
        destination_building_id=str(data.get("destination_building_id", "")),
        origin_zone_id=str(data.get("origin_zone_id", "")),
        destination_zone_id=str(data.get("destination_zone_id", "")),
        route_edge_ids=_strings(data.get("route_edge_ids", []), source),
        corridor_ids=_strings(data.get("corridor_ids", []), source),
        annual_trips=(
            None
            if annual_trips is None
            else _parse_value(_as_object(annual_trips, f"{source}.annual_trips"), source)
        ),
        notes=str(data.get("notes", "")),
    )


def _parse_candidate_impact(data: Mapping[str, Any], source: str) -> CandidateOdImpact:
    def optional_value(name: str) -> ValueRecord | None:
        value = data.get(name)
        if value is None:
            return None
        return _parse_value(_as_object(value, f"{source}.{name}"), f"{source}.{name}")

    return CandidateOdImpact(
        od_pair_id=_required_str(data, "od_pair_id", source),
        route_exposure_fraction=optional_value("route_exposure_fraction"),
        delay_reduction_seconds_per_trip=optional_value("delay_reduction_seconds_per_trip"),
        annual_trips=optional_value("annual_trips"),
        persons_per_trip=optional_value("persons_per_trip"),
        annual_person_delay_saved_hours=optional_value("annual_person_delay_saved_hours"),
        annual_economic_benefit_vnd=optional_value("annual_economic_benefit_vnd"),
        derivation_method=str(data.get("derivation_method", "explicit_od_impact")),
        notes=str(data.get("notes", "")),
    )


def _parse_candidate(data: Mapping[str, Any], source: str) -> InvestmentCandidateEconomicNode:
    candidate_id = _required_str(data, "candidate_id", source)
    prefix = f"{source}.investment_candidates.{candidate_id}"
    return InvestmentCandidateEconomicNode(
        candidate_id=candidate_id,
        name=str(data.get("name", candidate_id)),
        junction_ids=_strings(data.get("junction_ids", []), prefix),
        edge_ids=_strings(data.get("edge_ids", []), prefix),
        corridor_ids=_strings(data.get("corridor_ids", []), prefix),
        capital_cost_vnd=_parse_value(_required_object(data, "capital_cost_vnd", prefix), prefix),
        annual_operating_cost_vnd=_parse_value(
            _required_object(data, "annual_operating_cost_vnd", prefix), prefix
        ),
        od_impacts=tuple(
            _parse_candidate_impact(item, prefix) for item in _array(data, "od_impacts", prefix)
        ),
        notes=str(data.get("notes", "")),
    )


def _parse_reward_policy(data: Mapping[str, Any], source: str) -> RewardPolicy:
    return RewardPolicy(
        normalization_vnd_per_step=_parse_value(
            _required_object(data, "normalization_vnd_per_step", source), source
        ),
        clip_min=_required_float(data, "clip_min", source),
        clip_max=_required_float(data, "clip_max", source),
    )


def _parse_coverage_policy(data: Mapping[str, Any], source: str) -> CoveragePolicy:
    return CoveragePolicy(
        minimum_structural_edge_mapping_ratio=_required_float(
            data, "minimum_structural_edge_mapping_ratio", source
        ),
        minimum_non_global_valuation_ratio=_required_float(
            data, "minimum_non_global_valuation_ratio", source
        ),
        minimum_source_backed_valuation_ratio=_required_float(
            data, "minimum_source_backed_valuation_ratio", source
        ),
        require_demand_weighted_coverage=_required_bool(
            data, "require_demand_weighted_coverage", source
        ),
        minimum_demand_weighted_non_global_ratio=_required_float(
            data, "minimum_demand_weighted_non_global_ratio", source
        ),
        minimum_demand_weighted_source_backed_ratio=_required_float(
            data, "minimum_demand_weighted_source_backed_ratio", source
        ),
    )


def _parse_coverage(value: Any, source: str) -> CoverageReport | None:
    if value is None:
        return None
    data = _as_object(value, f"{source}.coverage")
    return CoverageReport(
        total_prepared_entities=_required_int(data, "total_prepared_entities", source),
        demand_eligible_entities=_required_int(data, "demand_eligible_entities", source),
        excluded_background_entities=_required_int(data, "excluded_background_entities", source),
        exact_edge_mapping_count=_required_int(data, "exact_edge_mapping_count", source),
        derived_edge_mapping_count=_required_int(data, "derived_edge_mapping_count", source),
        unmapped_edge_count=_required_int(data, "unmapped_edge_count", source),
        structural_edge_mapping_ratio=_required_float(
            data, "structural_edge_mapping_ratio", source
        ),
        od_pair_resolution_count=_required_int(data, "od_pair_resolution_count", source),
        building_resolution_count=_required_int(data, "building_resolution_count", source),
        zone_resolution_count=_required_int(data, "zone_resolution_count", source),
        corridor_resolution_count=_required_int(data, "corridor_resolution_count", source),
        global_resolution_count=_required_int(data, "global_resolution_count", source),
        economic_unmapped_count=_required_int(data, "economic_unmapped_count", source),
        non_global_valuation_ratio=_required_float(data, "non_global_valuation_ratio", source),
        source_backed_valuation_ratio=_required_float(
            data, "source_backed_valuation_ratio", source
        ),
        demand_weighted_coverage_status=_required_str(
            data, "demand_weighted_coverage_status", source
        ),
        demand_weight_total=_optional_float(data.get("demand_weight_total"), source),
        demand_weighted_non_global_ratio=_optional_float(
            data.get("demand_weighted_non_global_ratio"), source
        ),
        demand_weighted_source_backed_ratio=_optional_float(
            data.get("demand_weighted_source_backed_ratio"), source
        ),
        production_gate_passed=_required_bool(data, "production_gate_passed", source),
        production_gate_reasons=_strings(data.get("production_gate_reasons", []), source),
    )


def _indexed[T](
    rows: list[Mapping[str, Any]],
    key: str,
    parser: Callable[[Mapping[str, Any]], T],
    source: str,
) -> dict[str, T]:
    result: dict[str, T] = {}
    for row in rows:
        item_id = _required_str(row, key, source)
        if item_id in result:
            raise MapEconomicProfileError(f"{source}: duplicate {key} {item_id}")
        result[item_id] = parser(row)
    return result


def _unknown_refs(
    kind: str, values: tuple[str, ...], known: Mapping[str, object], owner: str
) -> list[str]:
    return [f"{owner} references unknown {kind} {value}" for value in values if value not in known]


def _unknown_optional_ref(
    kind: str, value: str, known: Mapping[str, object], owner: str
) -> list[str]:
    return [] if not value or value in known else [f"{owner} references unknown {kind} {value}"]


def _required_object(data: Mapping[str, Any], key: str, source: str) -> Mapping[str, Any]:
    if key not in data:
        raise MapEconomicProfileError(f"{source}: missing object {key}")
    return _as_object(data[key], f"{source}.{key}")


def _as_object(value: Any, source: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MapEconomicProfileError(f"{source}: expected an object")
    return value


def _required_array(data: Mapping[str, Any], key: str, source: str) -> list[Mapping[str, Any]]:
    if key not in data:
        raise MapEconomicProfileError(f"{source}: missing array {key}")
    return _array(data, key, source)


def _array(data: Mapping[str, Any], key: str, source: str) -> list[Mapping[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise MapEconomicProfileError(f"{source}.{key}: expected an array")
    rows: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise MapEconomicProfileError(f"{source}.{key}[{index}]: expected an object")
        rows.append(item)
    return rows


def _required_str(data: Mapping[str, Any], key: str, source: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MapEconomicProfileError(f"{source}: {key} must be a non-empty string")
    return value


def _required_float(data: Mapping[str, Any], key: str, source: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MapEconomicProfileError(f"{source}: {key} must be numeric")
    if not math.isfinite(value):
        raise MapEconomicProfileError(f"{source}: {key} must be finite")
    return float(value)


def _required_int(data: Mapping[str, Any], key: str, source: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MapEconomicProfileError(f"{source}: {key} must be an integer")
    return value


def _required_bool(data: Mapping[str, Any], key: str, source: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise MapEconomicProfileError(f"{source}: {key} must be a boolean")
    return value


def _optional_float(value: Any, source: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MapEconomicProfileError(f"{source}: expected a number or null")
    if not math.isfinite(value):
        raise MapEconomicProfileError(f"{source}: expected a finite number or null")
    return float(value)


def _strings(value: Any, source: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MapEconomicProfileError(f"{source}: expected an array of strings")
    return tuple(value)
