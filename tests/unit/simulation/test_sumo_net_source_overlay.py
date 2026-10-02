from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.maps import (
    generate_sumo_demand,
    load_semantic_overlay,
    load_sumo_net_index,
)
from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError


def test_sumo_net_index_reads_edges_lanes_junction_shapes(tmp_path: Path) -> None:
    net = _write_tiny_net(tmp_path)

    index = load_sumo_net_index(net)

    assert index.edge_ids == frozenset({"E1"})
    assert index.lane_ids == frozenset({"E1_0"})
    assert index.junction_ids == frozenset({"J1", "J2"})
    assert index.traffic_light_ids == frozenset({"J1"})
    assert index.lane_to_edge["E1_0"] == "E1"
    assert index.first_lane_for_edge("E1") == "E1_0"
    assert index.bounds_min == (-1.0, -1.0)
    assert index.bounds_max == (10.0, 1.0)


def test_semantic_overlay_rejects_unknown_sumo_references(tmp_path: Path) -> None:
    net = _write_tiny_net(tmp_path)
    overlay = tmp_path / "overlay.json"
    overlay.write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "bad_overlay",
                "name": "Bad overlay",
                "zones": [
                    {
                        "id": "Z1",
                        "name": "Zone 1",
                        "type": "residential",
                        "anchor_edges": ["MISSING"],
                    }
                ],
                "investment_candidates": [],
                "demand_flows": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SumoMapSourceError, match="unknown SUMO edge_id"):
        load_semantic_overlay(overlay, load_sumo_net_index(net))


def _write_tiny_net(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.net.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<net>
  <edge id="E1" from="J1" to="J2">
    <lane id="E1_0" index="0" speed="13.9" length="10.0" width="3.2" shape="0.0,0.0 10.0,0.0"/>
  </edge>
  <junction
    id="J1"
    type="traffic_light"
    x="0.0"
    y="0.0"
    shape="-1.0,-1.0 1.0,-1.0 1.0,1.0 -1.0,1.0"
  />
  <junction id="J2" type="priority" x="10.0" y="0.0"/>
</net>
""",
        encoding="utf-8",
    )
    return path


def _polygon_overlay() -> dict:
    return {
        "schema_version": "roi_semantic_overlay.v2",
        "id": "polygons",
        "name": "Prepared polygons",
        "coordinate_system": "sumo_xy",
        "caveats": ["Unreviewed synthetic inventory"],
        "zones": [{
            "id": "part_1", "name": "Facility part", "type": "residential",
            "source_element_id": "way/123", "source_element_kind": "buildable_geometry",
            "source_tags": {"building": "yes"}, "demand_enabled": True,
            "geometry": {"type": "polygon", "coordinate_system": "sumo_xy",
                         "coordinates": [[0, 0], [1, 0], [1, 1], [0, 0]]},
            "centroid": [0.7, 0.3], "anchor_edges": [], "anchor_junctions": [],
            "manual_review_required": True, "confidence": 0.5,
        }],
    }


def _load_payload(tmp_path: Path, data: dict):
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_semantic_overlay(path, load_sumo_net_index(_write_tiny_net(tmp_path)))


def test_polygon_overlay_keeps_provenance_and_unresolved_access(tmp_path: Path) -> None:
    data = _polygon_overlay()
    overlay = _load_payload(tmp_path, data)
    zone = overlay.zones["part_1"]
    assert overlay.schema_version == "roi_semantic_overlay.v2"
    assert overlay.raw == data
    assert zone.raw == data["zones"][0]
    assert zone.geometry == data["zones"][0]["geometry"]
    assert zone.source_element_id == "way/123"
    assert zone.source_tags == {"building": "yes"}
    assert zone.demand_enabled is True
    assert zone.anchor_edges == ()
    assert not overlay.demand_flows


@pytest.mark.parametrize(("field", "value", "message"), [
    ("id", "", "non-empty string"),
    ("source_element_id", None, "non-empty string"),
    ("source_tags", [], "string mapping"),
    ("demand_enabled", "false", "boolean"),
    ("centroid", [float("nan"), 0], "finite"),
    ("anchor_edges", ["missing"], "unknown SUMO edge"),
    ("anchor_edges", [3], "array of strings"),
    ("anchor_junctions", ["missing"], "unknown SUMO junction"),
])
def test_polygon_overlay_rejects_invalid_semantics(
    tmp_path: Path, field: str, value: object, message: str,
) -> None:
    data = _polygon_overlay()
    data["zones"][0][field] = value
    with pytest.raises(SumoMapSourceError, match=message):
        _load_payload(tmp_path, data)


@pytest.mark.parametrize("coordinates", [
    [[0, 0], [1, 1]], [[0, 0], [1, 1], [2, 2]],
    [[0, 0], [float("inf"), 0], [1, 1]], [[0, 0, 0], [1, 0], [1, 1]],
])
def test_polygon_overlay_rejects_invalid_geometry(tmp_path: Path, coordinates: list) -> None:
    data = _polygon_overlay()
    data["zones"][0]["geometry"]["coordinates"] = coordinates
    with pytest.raises(SumoMapSourceError):
        _load_payload(tmp_path, data)


@pytest.mark.parametrize("location", ["root", "geometry"])
def test_polygon_overlay_rejects_coordinate_reinterpretation(tmp_path: Path, location: str) -> None:
    data = _polygon_overlay()
    target = data if location == "root" else data["zones"][0]["geometry"]
    target["coordinate_system"] = "wgs84"
    with pytest.raises(SumoMapSourceError, match="coordinate_system"):
        _load_payload(tmp_path, data)


@pytest.mark.parametrize("schema", ["semantic_overlay.v2", "roi_semantic_overlay.v99"])
def test_overlay_rejects_unsupported_schema(tmp_path: Path, schema: str) -> None:
    data = _polygon_overlay()
    data["schema_version"] = schema
    with pytest.raises(SumoMapSourceError, match="unsupported"):
        _load_payload(tmp_path, data)


def _flow() -> dict:
    return {"id": "commute", "origin_zone": "part_1", "destination_zone": "part_1",
            "begin": 0, "end": 60, "volume": 1, "vehicle_mix": {"PRIVATE_CAR": 1}}


@pytest.mark.parametrize(("collection", "message"), [
    ("zones", "duplicate zone"), ("investment_candidates", "duplicate candidate"),
    ("demand_flows", "duplicate flow"),
])
def test_overlay_rejects_duplicate_ids(tmp_path: Path, collection: str, message: str) -> None:
    data = _polygon_overlay()
    data["zones"][0]["anchor_edges"] = ["E1"]
    if collection == "investment_candidates":
        data[collection] = [{"id": "candidate", "junction_id": "J1"}]
    if collection == "demand_flows":
        data[collection] = [_flow()]
    data[collection].append(data[collection][0].copy())
    with pytest.raises(SumoMapSourceError, match=message):
        _load_payload(tmp_path, data)


@pytest.mark.parametrize(("enabled", "anchors", "message"), [
    (False, ["E1"], "demand disabled"), (True, [], "no anchor edges"),
])
def test_flow_cannot_use_background_or_unanchored_polygon(
    tmp_path: Path, enabled: bool, anchors: list, message: str,
) -> None:
    data = _polygon_overlay()
    data["zones"][0].update(demand_enabled=enabled, anchor_edges=anchors)
    data["demand_flows"] = [_flow()]
    with pytest.raises(SumoMapSourceError, match=message):
        _load_payload(tmp_path, data)


@pytest.mark.parametrize("empty_kind", ["missing", "zero_volume", "zero_scenario"])
def test_empty_demand_fails_before_outputs_or_routing(tmp_path: Path, empty_kind: str) -> None:
    data = _polygon_overlay()
    if empty_kind != "missing":
        data["zones"][0]["anchor_edges"] = ["E1"]
        data["demand_flows"] = [_flow()]
        if empty_kind == "zero_volume":
            data["demand_flows"][0]["volume"] = 0
        else:
            data["demand_flows"][0]["scenario_multipliers"] = {"normal": 0}
    overlay = _load_payload(tmp_path, data)
    net = tmp_path / "tiny.net.xml"
    with pytest.raises(SumoMapSourceError, match="no demand_flows|no trips requested"):
        generate_sumo_demand(
            overlay=overlay, net_index=load_sumo_net_index(net), net_path=net,
            scenario_id="normal", work_dir=tmp_path / "output",
            duarouter_binary="must_not_be_invoked",
        )
    assert not (tmp_path / "output").exists()


def test_legacy_anchored_flow_still_loads(tmp_path: Path) -> None:
    data = {"schema_version": "semantic_overlay.v1", "id": "legacy", "name": "Legacy",
            "zones": [{"id": "part_1", "name": "Zone", "type": "residential",
                       "anchor_edges": ["E1"]}], "demand_flows": [_flow()]}
    overlay = _load_payload(tmp_path, data)
    assert overlay.zones["part_1"].anchor_edges == ("E1",)
    assert overlay.demand_flows["commute"].volume == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1])
def test_flow_rejects_invalid_mix_and_multiplier(tmp_path: Path, value: float) -> None:
    for field in ("vehicle_mix", "scenario_multipliers"):
        data = _polygon_overlay()
        data["zones"][0]["anchor_edges"] = ["E1"]
        flow = _flow()
        flow[field] = {"PRIVATE_CAR": value}
        data["demand_flows"] = [flow]
        with pytest.raises(SumoMapSourceError, match="finite and non-negative"):
            _load_payload(tmp_path, data)
