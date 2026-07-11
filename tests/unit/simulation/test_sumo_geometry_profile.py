from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.engines.sumo.exporter import export_sumo_project
from ai_quantum_hvtc.simulation.engines.sumo.parser import parse_sumo_result
from ai_quantum_hvtc.simulation.engines.sumo.profiles import GEOMETRY_SENSOR_SUMO_PROFILE
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_geometry_sensor_profile_writes_canonical_vehicle_artifacts(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
        work_dir=tmp_path,
        simulation_profile=GEOMETRY_SENSOR_SUMO_PROFILE,
    )

    routes = paths.routes.read_text(encoding="utf-8")
    config = paths.config.read_text(encoding="utf-8")
    catalog = json.loads(paths.vehicle_geometry_catalog.read_text(encoding="utf-8"))

    assert 'height="' in routes
    assert 'actionStepLength="1.000"' in routes
    assert 'maxSpeedLat="' in routes
    assert '<step-length value="0.2"' in config
    assert "location,posLat,speedLat,acceleration" in config
    assert catalog["schema_version"] == "vehicle_geometry_catalog.v1"
    assert catalog["reference_point"] == "front_bumper_center"
    assert catalog["vehicle_types"]["PRIVATE_CAR"]["height_m"] > 0
    assert paths.simulation_profile.profile_id == "geometry_sensor"
    assert "--lateral-resolution" in paths.simulation_profile.command_args()


def test_sumo_fcd_parser_enriches_vehicle_trace_v2_with_physical_geometry(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
        work_dir=tmp_path,
    )
    paths.fcd.write_text(
        """<fcd-export>
  <timestep time="1.0">
    <vehicle id="FLOW_PRIVATE_CAR.0" type="PRIVATE_CAR" x="10" y="20" angle="90"
      speed="3" lane="road_0" posLat="0.4" speedLat="0.2" acceleration="1.3" />
  </timestep>
</fcd-export>
""",
        encoding="utf-8",
    )

    result = parse_sumo_result(
        paths=paths,
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
    )
    frame = result.vehicle_trace_frames[0]
    vehicle = frame["vehicles"][0]

    assert frame["schema_version"] == "vehicle_trace.v2"
    assert vehicle["reference_point"] == "front_bumper_center"
    assert vehicle["height_m"] > 0
    assert vehicle["pos_lat_m"] == 0.4
    assert vehicle["lateral_speed_mps"] == 0.2
    assert vehicle["acceleration_mps2"] == 1.3
    assert vehicle["elevation_source"] == "flat_assumption"


def test_sumo_fcd_parser_samples_elevation_from_a_3d_lane_shape(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
        work_dir=tmp_path,
    )
    paths.net.write_text(
        """<net>
  <edge id="road"><lane id="road_0" shape="0,0,1 20,0,5" /></edge>
</net>
""",
        encoding="utf-8",
    )
    paths.fcd.write_text(
        """<fcd-export>
  <timestep time="1.0">
    <vehicle id="car.0" type="PRIVATE_CAR" x="10" y="0" angle="90" speed="3" lane="road_0" />
  </timestep>
</fcd-export>
""",
        encoding="utf-8",
    )

    result = parse_sumo_result(
        paths=paths,
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
    )
    vehicle = result.vehicle_trace_frames[0]["vehicles"][0]

    assert vehicle["elevation_m"] == 3.0
    assert vehicle["elevation_source"] == "lane_shape_3d"


def test_sumo_parser_rejects_unknown_vehicle_type_for_vehicle_trace_v2(tmp_path: Path) -> None:
    spec = load_district_spec(SPEC_PATH)
    paths = export_sumo_project(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=17,
        work_dir=tmp_path,
    )
    paths.fcd.write_text(
        """<fcd-export>
  <timestep time="1.0">
    <vehicle id="unknown.0" type="UNKNOWN" x="0" y="0" angle="0" speed="0" lane="road_0" />
  </timestep>
</fcd-export>
""",
        encoding="utf-8",
    )

    with pytest.raises(SumoRuntimeError, match="canonical vehicle type"):
        parse_sumo_result(
            paths=paths,
            spec=spec,
            scenario_id="normal_weekday",
            controller_id="fixed_time",
            seed=17,
        )
