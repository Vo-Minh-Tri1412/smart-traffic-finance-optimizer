from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.maps import load_semantic_overlay, load_sumo_net_index
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
