"""Actual retained descriptor regression; missing DVC inputs are explicit skips, never fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.cli import main
from ai_quantum_hvtc.simulation.maps import load_semantic_overlay, load_sumo_net_index
from ai_quantum_hvtc.simulation.maps.snapshot import (
    verify_project_snapshot,
    write_project_snapshot,
)
from ai_quantum_hvtc.simulation.maps.source import load_sumo_project, sha256_file

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "simulation_projects/map_intake/district7.project.json"


@pytest.fixture(scope="module")
def retained_project():
    data = json.loads(PROJECT.read_text(encoding="utf-8"))
    net = PROJECT.parent / data["source"]["net_path"]
    if not net.is_file():
        pytest.skip("retained SUMO net unavailable; restore its DVC data to run this integration")
    return load_sumo_project(PROJECT)


def test_retained_descriptor_preserves_all_entities_and_source_bytes(retained_project) -> None:
    project = retained_project
    before = {path: sha256_file(path) for path in (project.source.net_path, project.overlay_path)}
    index = load_sumo_net_index(project.source.net_path)
    overlay = load_semantic_overlay(project.overlay_path, index)
    source = json.loads(project.overlay_path.read_text(encoding="utf-8"))
    assert overlay.schema_version == "roi_semantic_overlay.v2"
    assert overlay.raw == source
    assert len(overlay.zones) == 2588
    assert sum(zone.demand_enabled for zone in overlay.zones.values()) == 1354
    assert len({zone.source_element_id for zone in overlay.zones.values()}) == 340
    assert all(not zone.anchor_edges for zone in overlay.zones.values())
    assert not overlay.demand_flows
    for row in source["zones"]:
        zone = overlay.zones[row["id"]]
        assert zone.raw == row
        assert zone.geometry == row["geometry"]
        assert zone.source_tags == row["source_tags"]
    assert (index.edge_count, index.lane_count, index.junction_count) == (29001, 32013, 13073)
    assert {path: sha256_file(path) for path in before} == before


def test_retained_cli_reports_missing_demand(retained_project, capsys) -> None:
    assert main(["validate-sumo-net", "--project", str(PROJECT)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["overlay_status"] == "ok"
    assert report["overlay_schema_version"] == "roi_semantic_overlay.v2"
    assert report["overlay_zone_count"] == report["overlay_unanchored_zone_count"] == 2588
    assert report["demand_status"] == "missing"
    assert report["demand_flow_count"] == 0


def test_retained_snapshot_binds_actual_tls_programs_and_movements(
    retained_project,
    tmp_path: Path,
) -> None:
    output = tmp_path / "snapshot.json"
    snapshot = write_project_snapshot(PROJECT, output)
    assert verify_project_snapshot(output, PROJECT) == snapshot
    inventory = snapshot["tls_inventory"]
    assert inventory["tls_count"] == inventory["program_count"] == 169
    assert inventory["controlled_connection_count"] == 1008
    assert inventory["lane_index_ambiguities"]
    assert (
        sum(
            child["tag"] == "phase"
            for signal in inventory["signals"]
            for program in signal["programs"]
            for child in program["source"]["children"]
        )
        == 649
    )
    assert all(signal["control_review_status"] == "pending" for signal in inventory["signals"])
