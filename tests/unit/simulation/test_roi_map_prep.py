from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ai_quantum_hvtc.simulation.maps.roi import (
    OsmPoint,
    RoiConfig,
    RoiPolygon,
    classify_road_tags,
    classify_zone_tags,
    prepare_roi,
    read_osm_roi,
    write_roi_artifacts,
)


def test_roi_polygon_selects_osm_features_and_infers_micro_zones(tmp_path: Path) -> None:
    osm = _write_tiny_osm(tmp_path)
    net = _write_tiny_net(tmp_path)
    config = RoiConfig(
        roi_id="tiny_roi",
        name="Tiny ROI",
        polygon=_tiny_polygon(),
        osm_path=osm,
        source_net_path=net,
    )

    result = prepare_roi(config)

    zone_types = {zone.zone_type for zone in result.micro_zones}
    assert {"residential", "education", "industrial", "market_retail", "neutral"}.issubset(
        zone_types
    )
    assert len(result.micro_zones) >= 4
    assert any(group.zone_type == "residential" for group in result.zone_groups)
    assert all(zone.anchor_edges for zone in result.micro_zones if zone.zone_type != "neutral")
    assert all(
        zone.geometry["type"] == "polygon"
        for zone in result.micro_zones
        if zone.source_element_kind == "node"
    )


def test_road_classifier_flags_small_roads_inside_zone(tmp_path: Path) -> None:
    osm = _write_tiny_osm(tmp_path)
    net = _write_tiny_net(tmp_path)
    config = RoiConfig(
        roi_id="tiny_roi",
        name="Tiny ROI",
        polygon=_tiny_polygon(),
        osm_path=osm,
        source_net_path=net,
    )

    result = prepare_roi(config)

    roads_by_id = {road.road_id: road for road in result.roads}
    assert roads_by_id["200"].classification == "keep_simulation"
    assert roads_by_id["201"].classification == "zone_internal_service"
    assert roads_by_id["201"].review_required is True
    assert roads_by_id["202"].classification == "pedestrian_only"


def test_roi_artifact_writer_outputs_overlay_review_preview_and_qa(tmp_path: Path) -> None:
    osm = _write_tiny_osm(tmp_path)
    net = _write_tiny_net(tmp_path)
    config = RoiConfig(
        roi_id="tiny_roi",
        name="Tiny ROI",
        polygon=_tiny_polygon(),
        osm_path=osm,
        source_net_path=net,
    )

    result = prepare_roi(config)
    paths = write_roi_artifacts(result, tmp_path / "out")

    overlay = json.loads(paths.semantic_overlay.read_text(encoding="utf-8"))
    review = json.loads(paths.road_review.read_text(encoding="utf-8"))
    preview = json.loads(paths.godot_preview.read_text(encoding="utf-8"))
    qa = json.loads(paths.qa_json.read_text(encoding="utf-8"))

    assert overlay["schema_version"] == "roi_semantic_overlay.v1"
    assert len(overlay["zones"]) >= 4
    neutral_zones = [zone for zone in overlay["zones"] if zone["type"] == "neutral"]
    assert len(neutral_zones) == 1
    assert neutral_zones[0]["demand_enabled"] is False
    assert neutral_zones[0]["traffic_role"] == "background_no_demand"
    assert all(
        zone["geometry"]["type"] == "polygon"
        for zone in overlay["zones"]
        if zone["source_element_kind"] == "node"
    )
    assert review["summary"]["zone_internal_service"] == 1
    assert preview["geometry_source"]["source_of_truth"] == "source_sumo_net"
    assert qa["counts"]["micro_zones"] >= 4
    assert paths.qa_markdown.read_text(encoding="utf-8").startswith("# ROI prep QA")


def test_prepare_roi_can_clip_sumo_net_with_geo_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    osm = _write_tiny_osm(tmp_path)
    net = _write_tiny_net(tmp_path)
    config = RoiConfig(
        roi_id="tiny_roi",
        name="Tiny ROI",
        polygon=_tiny_polygon(),
        osm_path=osm,
        source_net_path=net,
    )
    commands: list[list[str]] = []

    def fake_resolve_sumo_binary(_binary_name: str) -> str:
        return "netconvert"

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, capture_output, text
        commands.append(command)
        output_path = Path(command[command.index("--output-file") + 1])
        output_path.write_text("<net />\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "ai_quantum_hvtc.simulation.maps.roi.resolve_sumo_binary",
        fake_resolve_sumo_binary,
    )
    monkeypatch.setattr("ai_quantum_hvtc.simulation.maps.roi.subprocess.run", fake_run)

    result = prepare_roi(config, clip_sumo_net=True, output_root=tmp_path / "out")

    assert result.prepared_net_path is not None
    assert result.prepared_net_path.name == "tiny_roi.prepared.net.xml"
    assert commands
    command = commands[0]
    assert "-s" in command
    assert "--keep-edges.in-geo-boundary" in command
    assert "-0.01,-0.01 0.12,-0.01 0.12,0.12 -0.01,0.12" in command
    assert "--keep-edges.components" in command


def test_tag_taxonomy_and_road_classification_are_stable() -> None:
    assert classify_zone_tags({"amenity": "bus_station"}) == ("transport_hub", "bus_station", 0.78)
    assert classify_zone_tags({"industrial": "port"}) == ("port_logistics", "port", 0.88)
    assert classify_zone_tags({"landuse": "retail"}) == ("market_retail", "retail", 0.82)
    assert classify_zone_tags({"building": "apartments"}) == ("residential", "apartments", 0.72)
    assert classify_zone_tags({"amenity": "parking"}) == ("transport_hub", "parking", 0.78)
    assert classify_zone_tags({"building": "warehouse"}) == ("industrial", "warehouse", 0.76)
    assert classify_road_tags(tags={"highway": "primary"}, inside_zone=True)[0] == "keep_simulation"
    assert (
        classify_road_tags(tags={"highway": "service"}, inside_zone=True)[0]
        == "zone_internal_service"
    )
    assert (
        classify_road_tags(tags={"highway": "footway"}, inside_zone=False)[0] == "pedestrian_only"
    )


def test_roi_without_sumo_net_warns_about_missing_zone_access(tmp_path: Path) -> None:
    osm = _write_tiny_osm(tmp_path)
    config = RoiConfig(
        roi_id="tiny_roi",
        name="Tiny ROI",
        polygon=_tiny_polygon(),
        osm_path=osm,
    )

    result = prepare_roi(config)

    assert any("manual access-road review" in warning for warning in result.warnings)
    assert any(zone.manual_review_required for zone in result.micro_zones)


def test_read_osm_roi_keeps_only_polygon_content(tmp_path: Path) -> None:
    osm = _write_tiny_osm(tmp_path)

    nodes, ways = read_osm_roi(osm, _tiny_polygon())

    assert "1" in nodes
    assert "999" not in nodes
    assert {way.way_id for way in ways} >= {"100", "200", "201"}
    assert "9999" not in {way.way_id for way in ways}


def _tiny_polygon() -> RoiPolygon:
    return RoiPolygon(
        points=(
            OsmPoint(lon=-0.01, lat=-0.01),
            OsmPoint(lon=0.12, lat=-0.01),
            OsmPoint(lon=0.12, lat=0.12),
            OsmPoint(lon=-0.01, lat=0.12),
        )
    )


def _write_tiny_osm(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.osm"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="0.00" lon="0.00" />
  <node id="2" lat="0.00" lon="0.06" />
  <node id="3" lat="0.06" lon="0.06" />
  <node id="4" lat="0.06" lon="0.00" />
  <node id="5" lat="0.05" lon="-0.01" />
  <node id="6" lat="0.05" lon="0.11" />
  <node id="7" lat="0.03" lon="0.01" />
  <node id="8" lat="0.03" lon="0.05" />
  <node id="9" lat="0.01" lon="0.02" />
  <node id="10" lat="0.01" lon="0.04" />
  <node id="11" lat="0.08" lon="0.07" />
  <node id="12" lat="0.08" lon="0.11" />
  <node id="13" lat="0.11" lon="0.11" />
  <node id="14" lat="0.11" lon="0.07" />
  <node id="20" lat="0.09" lon="0.02">
    <tag k="amenity" v="school" />
    <tag k="name" v="Tiny School" />
  </node>
  <node id="21" lat="0.09" lon="0.03">
    <tag k="amenity" v="marketplace" />
    <tag k="name" v="Tiny Market" />
  </node>
  <node id="999" lat="1.00" lon="1.00" />
  <way id="100">
    <nd ref="1" /><nd ref="2" /><nd ref="3" /><nd ref="4" /><nd ref="1" />
    <tag k="landuse" v="residential" />
    <tag k="name" v="Residential Block" />
  </way>
  <way id="101">
    <nd ref="11" /><nd ref="12" /><nd ref="13" /><nd ref="14" /><nd ref="11" />
    <tag k="landuse" v="industrial" />
    <tag k="name" v="Industrial Block" />
  </way>
  <way id="200">
    <nd ref="5" /><nd ref="6" />
    <tag k="highway" v="primary" />
    <tag k="name" v="Main Road" />
  </way>
  <way id="201">
    <nd ref="7" /><nd ref="8" />
    <tag k="highway" v="service" />
    <tag k="name" v="Internal Alley" />
  </way>
  <way id="202">
    <nd ref="9" /><nd ref="10" />
    <tag k="highway" v="footway" />
  </way>
  <way id="9999">
    <nd ref="999" />
    <tag k="landuse" v="commercial" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    return path


def _write_tiny_net(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.net.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<net>
  <edge id="200#0" from="J1" to="J2">
    <lane id="200#0_0" index="0" speed="13.9" length="100.0" shape="0.0,0.0 100.0,0.0"/>
  </edge>
  <edge id="-200#1" from="J2" to="J1">
    <lane id="-200#1_0" index="0" speed="13.9" length="100.0" shape="100.0,0.0 0.0,0.0"/>
  </edge>
  <edge id="201#0" from="J3" to="J4">
    <lane id="201#0_0" index="0" speed="8.0" length="20.0" shape="10.0,10.0 20.0,10.0"/>
  </edge>
  <junction id="J1" type="traffic_light" x="0.0" y="0.0"/>
  <junction id="J2" type="priority" x="100.0" y="0.0"/>
  <junction id="J3" type="priority" x="10.0" y="10.0"/>
  <junction id="J4" type="priority" x="20.0" y="10.0"/>
</net>
""",
        encoding="utf-8",
    )
    return path
