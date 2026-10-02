from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.maps.snapshot import (
    build_project_snapshot,
    load_tls_inventory,
    verify_project_snapshot,
    write_project_snapshot,
)
from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError

NET = """<net>
  <edge id="E1"><lane id="E1_0" index="0" shape="0,0 1,0"/></edge>
  <edge id="E2"><lane id="E2_0" index="0" shape="1,0 2,0"/></edge>
  <edge id=":J_0" function="internal"><lane id=":J_0_0" index="0"/></edge>
  <tlLogic id="TLS" type="static" programID="0" offset="0">
    <phase duration="10" state="G"/><phase duration="3" state="y"/>
    <phase duration="2" state="r"/><param key="provenance" value="test"/>
  </tlLogic>
  <junction id="J" type="traffic_light" x="1" y="0"/>
  <connection from="E1" to="E2" fromLane="0" toLane="0" via=":J_0_0"
              tl="TLS" linkIndex="0" dir="s" state="O"/>
</net>"""


def _project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "map.net.xml").write_text(NET, encoding="utf-8")
    (root / "overlay.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "overlay",
                "name": "Test",
                "zones": [
                    {"id": "Z", "name": "Zone", "type": "residential", "anchor_edges": ["E1"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "demand.json").write_text('{"status": "missing"}', encoding="utf-8")
    descriptor = root / "project.json"
    descriptor.write_text(
        json.dumps(
            {
                "id": "project",
                "name": "Test",
                "version": "v1",
                "source": {"net_path": "map.net.xml"},
                "semantic_overlay_path": "overlay.json",
                "demand_config_path": "demand.json",
            }
        ),
        encoding="utf-8",
    )
    return descriptor


def test_snapshot_preserves_tls_ids_programs_movements_and_source_parameters(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "inputs")
    first = build_project_snapshot(project)
    assert build_project_snapshot(project) == first
    inventory = first["tls_inventory"]
    assert inventory["tls_count"] == inventory["program_count"] == 1
    signal = inventory["signals"][0]
    assert signal["tls_id"] == "TLS"
    assert signal["same_id_junction"] is None  # A TLS ID is not necessarily a junction ID.
    assert signal["control_review_status"] == "pending"
    assert signal["movements"][0]["from_lane_id"] == "E1_0"
    assert signal["movements"][0]["via"] == ":J_0_0"
    source = signal["programs"][0]["source"]
    assert source["children"][-1]["attributes"] == {"key": "provenance", "value": "test"}
    assert first["scope"] == "map_input_snapshot_only"


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ('linkIndex="0"', 'linkIndex="1"', "width"),
        ('linkIndex="0"', 'linkIndex="-1"', "invalid link"),
        ('via=":J_0_0"', 'via="missing"', "via lane"),
        ('fromLane="0"', 'fromLane="9"', "invalid controlled"),
        ('duration="10"', 'duration="nan"', "duration"),
        ('duration="10"', 'duration="0"', "duration"),
        ('state="y"', 'state="yy"', "inconsistent"),
        ('tl="TLS"', 'tl="other"', "mismatch"),
    ],
)
def test_inventory_rejects_unusable_control_mapping(
    tmp_path: Path,
    old: str,
    new: str,
    error: str,
) -> None:
    net = tmp_path / "net.xml"
    net.write_text(NET.replace(old, new), encoding="utf-8")
    with pytest.raises(SumoMapSourceError, match=error):
        load_tls_inventory(net)


def test_repeated_internal_index_is_reported_without_rewriting_lane_identity(
    tmp_path: Path,
) -> None:
    net = tmp_path / "net.xml"
    net.write_text(
        NET.replace(
            '<lane id=":J_0_0" index="0"/>',
            '<lane id=":J_0_0" index="0"/><lane id=":J_0_1" index="0"/>',
        ),
        encoding="utf-8",
    )
    before = net.read_bytes()
    inventory = load_tls_inventory(net)
    assert inventory["lane_index_ambiguities"] == [
        {"edge_id": ":J_0", "index": "0", "lane_ids": [":J_0_0", ":J_0_1"]},
    ]
    assert net.read_bytes() == before


def test_ambiguous_controlled_lane_index_is_rejected(tmp_path: Path) -> None:
    net = tmp_path / "net.xml"
    net.write_text(
        NET.replace(
            '<lane id="E1_0" index="0" shape="0,0 1,0"/>',
            '<lane id="E1_0" index="0"/><lane id="E1_1" index="0"/>',
        ),
        encoding="utf-8",
    )
    with pytest.raises(SumoMapSourceError, match="ambiguous controlled"):
        load_tls_inventory(net)


def test_existing_snapshot_is_never_overwritten(tmp_path: Path) -> None:
    project = _project(tmp_path / "inputs")
    target = tmp_path / "snapshot.json"
    write_project_snapshot(project, target)
    before = target.read_bytes()
    with pytest.raises(FileExistsError, match="refusing overwrite"):
        write_project_snapshot(project, target)
    assert target.read_bytes() == before


@pytest.mark.parametrize("filename", ["project.json", "map.net.xml", "overlay.json", "demand.json"])
def test_input_byte_changes_invalidate_snapshot(tmp_path: Path, filename: str) -> None:
    project = _project(tmp_path / "inputs")
    snapshot = tmp_path / "snapshot.json"
    write_project_snapshot(project, snapshot)
    source = project.parent / filename
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(SumoMapSourceError, match="input mismatch"):
        verify_project_snapshot(snapshot, project)


def test_snapshot_corruption_is_detected(tmp_path: Path) -> None:
    project = _project(tmp_path / "inputs")
    snapshot = tmp_path / "snapshot.json"
    payload = write_project_snapshot(project, snapshot)
    payload["tls_inventory"]["signals"][0]["control_review_status"] = "approved"
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SumoMapSourceError, match="content checksum"):
        verify_project_snapshot(snapshot, project)


def test_snapshot_allows_explicit_rebinding_to_byte_identical_checkout(tmp_path: Path) -> None:
    project = _project(tmp_path / "inputs")
    snapshot = tmp_path / "snapshot.json"
    original = write_project_snapshot(project, snapshot)
    shutil.copytree(project.parent, tmp_path / "relocated")
    assert verify_project_snapshot(snapshot, tmp_path / "relocated/project.json") == original
