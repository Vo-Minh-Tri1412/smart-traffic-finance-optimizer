from __future__ import annotations

import json
from pathlib import Path

from ai_quantum_hvtc.map_economics import materialize_map_economic_profile


def test_materializer_marks_nearest_edge_as_derived(tmp_path: Path) -> None:
    net = tmp_path / "map.net.xml"
    net.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<net>
  <location netOffset="0,0" convBoundary="0,0,100,100" origBoundary="0,0,1,1" projParameter="!"/>
  <edge id="EDGE_1" from="J0" to="J1" priority="1" type="highway.residential">
    <lane id="EDGE_1_0" index="0" speed="10" length="100" shape="0,0 100,0"/>
  </edge>
  <junction id="J0" type="dead_end" x="0" y="0" incLanes="" intLanes="" shape="0,0"/>
  <junction id="J1" type="dead_end" x="100" y="0" incLanes="EDGE_1_0" intLanes="" shape="100,0"/>
</net>
""",
        encoding="utf-8",
    )
    overlay = tmp_path / "overlay.json"
    overlay.write_text(
        json.dumps(
            {
                "schema_version": "roi_semantic_overlay.v2",
                "id": "overlay",
                "name": "overlay",
                "coordinate_system": "sumo_xy",
                "caveats": [],
                "zones": [
                    {
                        "id": "ENTITY_1",
                        "name": "Prepared polygon",
                        "type": "residential",
                        "subtype": "buildable_polygon",
                        "centroid": [25, 10],
                        "anchor_edges": [],
                        "zone_group_id": "ZG_RESIDENTIAL",
                        "demand_enabled": True,
                        "source_tags": {"building": "residential"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.json"
    demand.write_text("{}", encoding="utf-8")
    project = tmp_path / "project.json"
    project.write_text(
        json.dumps(
            {
                "id": "test_map",
                "name": "test",
                "version": "v1",
                "source": {"id": "net", "kind": "sumo_net_xml", "net_path": net.name},
                "semantic_overlay_path": overlay.name,
                "demand_config_path": demand.name,
            }
        ),
        encoding="utf-8",
    )

    profile = materialize_map_economic_profile(
        project_path=project,
        assumptions_path=Path(
            "configs/economics/district7_map_economic_assumptions.v1.example.json"
        ),
    )

    entity = profile.buildings["ENTITY_1"]
    assert entity.entity_kind == "buildable_polygon"
    assert entity.mapping_method == "derived_nearest_edge"
    assert entity.edge_ids == ("EDGE_1",)
    assert entity.nearest_edge_distance_m == 10.0
    assert profile.coverage is not None
    assert profile.coverage.demand_weighted_coverage_status == "unavailable"
    assert not profile.coverage.production_gate_passed
