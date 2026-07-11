"""Canonical vehicle geometry artifacts shared by SUMO, sensors, and renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.domain import DistrictSpec, VehicleType

VEHICLE_GEOMETRY_CATALOG_SCHEMA_VERSION = "vehicle_geometry_catalog.v1"
FRONT_BUMPER_REFERENCE_POINT = "front_bumper_center"


def vehicle_geometry_profile(vehicle_type: VehicleType) -> dict[str, Any]:
    """Return the physical profile without renderer-specific mesh data."""

    return {
        "vehicle_type": vehicle_type.vehicle_type_id,
        "length_m": vehicle_type.length_m,
        "width_m": vehicle_type.width_m,
        "height_m": vehicle_type.height_m,
        "ground_clearance_m": vehicle_type.ground_clearance_m,
        "reference_point": FRONT_BUMPER_REFERENCE_POINT,
        "v_class": vehicle_type.v_class,
        "dynamics": {
            "max_speed_kph": vehicle_type.max_speed_kph,
            "accel_mps2": vehicle_type.accel_mps2,
            "decel_mps2": vehicle_type.decel_mps2,
            "emergency_decel_mps2": vehicle_type.emergency_decel_mps2,
            "apparent_decel_mps2": vehicle_type.apparent_decel_mps2,
            "min_gap_m": vehicle_type.min_gap_m,
            "tau_seconds": vehicle_type.tau_seconds,
            "action_step_length_seconds": vehicle_type.action_step_length_seconds,
        },
        "lateral_behavior": {
            "max_speed_lat_mps": vehicle_type.max_speed_lat_mps,
            "min_gap_lat_m": vehicle_type.min_gap_lat_m,
            "lat_alignment": vehicle_type.lat_alignment,
            "lc_sublane": vehicle_type.lc_sublane,
            "lc_pushy": vehicle_type.lc_pushy,
        },
    }


def vehicle_geometry_catalog(spec: DistrictSpec) -> dict[str, Any]:
    return {
        "schema_version": VEHICLE_GEOMETRY_CATALOG_SCHEMA_VERSION,
        "district_id": spec.metadata.district_id,
        "coordinate_system": "sumo_xy_meters_z_up",
        "reference_point": FRONT_BUMPER_REFERENCE_POINT,
        "vehicle_types": {
            vehicle_type_id: vehicle_geometry_profile(vehicle_type)
            for vehicle_type_id, vehicle_type in sorted(spec.vehicle_types.items())
        },
    }


def write_vehicle_geometry_catalog(spec: DistrictSpec, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            vehicle_geometry_catalog(spec),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
