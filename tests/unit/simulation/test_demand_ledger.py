from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ai_quantum_hvtc.simulation.engines.sumo.config import resolve_sumo_binary
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError
from ai_quantum_hvtc.simulation.maps import demand as demand_module
from ai_quantum_hvtc.simulation.maps.overlay import load_semantic_overlay
from ai_quantum_hvtc.simulation.maps.source import (
    SumoMapSourceError,
    load_sumo_net_index,
)

NET = """<net>
  <edge id="E1"><lane id="E1_0" index="0" shape="0,0 10,0"/></edge>
  <edge id="E2"><lane id="E2_0" index="0" shape="10,0 20,0"/></edge>
  <edge id="E3"><lane id="E3_0" index="0" shape="20,0 30,0"/></edge>
</net>"""


def _inputs(tmp_path: Path):
    net_path = tmp_path / "tiny.net.xml"
    net_path.write_text(NET, encoding="utf-8")
    overlay_path = tmp_path / "overlay.json"
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "overlay_fixture",
                "name": "Explicit synthetic fixture",
                "zones": [
                    {
                        "id": "origin_zone",
                        "name": "Origin",
                        "type": "residential",
                        "anchor_edges": ["E1", "E2"],
                    },
                    {
                        "id": "destination_zone",
                        "name": "Destination",
                        "type": "commercial",
                        "anchor_edges": ["E3"],
                    },
                ],
                "demand_flows": [
                    {
                        "id": "commute",
                        "origin_zone": "origin_zone",
                        "destination_zone": "destination_zone",
                        "trip_purpose": "commute",
                        "begin": 12,
                        "end": 20,
                        "volume": 4,
                        "vehicle_mix": {"PRIVATE_CAR": 0.5, "MOTORBIKE": 0.5},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    net_index = load_sumo_net_index(net_path)
    return net_path, net_index, load_semantic_overlay(overlay_path, net_index)


def _patch_router(monkeypatch: pytest.MonkeyPatch, route_xml: str | None) -> None:
    def fake_run_duarouter(*, routes_path: Path, **_: object) -> None:
        if route_xml is not None:
            routes_path.write_text(route_xml, encoding="utf-8")

    monkeypatch.setattr(demand_module, "_run_duarouter", fake_run_duarouter)


def _generate(tmp_path: Path, net_path: Path, net_index, overlay, work_name: str):
    return demand_module.generate_sumo_demand(
        overlay=overlay,
        net_index=net_index,
        net_path=net_path,
        scenario_id="normal",
        work_dir=tmp_path / work_name,
        seed=73,
    )


def test_ledger_reconciles_exact_vehicle_ids_and_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    net_path, net_index, overlay = _inputs(tmp_path)
    _patch_router(
        monkeypatch,
        """<routes>
  <vehicle id="commute_PRIVATE_CAR.1" depart="16.000">
    <route edges="E1 E3"/>
  </vehicle>
  <vehicle id="commute_MOTORBIKE.0" depart="12.000">
    <route edges="E1 E3"/>
  </vehicle>
</routes>""",
    )

    first = _generate(tmp_path, net_path, net_index, overlay, "first")
    second = _generate(tmp_path, net_path, net_index, overlay, "second")

    assert first.intended_demand_ledger is not None
    assert second.intended_demand_ledger is not None
    assert first.intended_demand_ledger.read_bytes() == second.intended_demand_ledger.read_bytes()
    assert first.trips.read_bytes() == second.trips.read_bytes()
    assert first.qa_json.read_bytes() == second.qa_json.read_bytes()

    ledger = json.loads(first.intended_demand_ledger.read_text(encoding="utf-8"))
    by_id = {row["trip_id"]: row for row in ledger["trips"]}
    assert ledger["schema_version"] == "intended_demand_ledger.v1"
    assert ledger["count_unit"] == "requested_vehicle_trip"
    assert ledger["seed"] == 73
    assert ledger["overlay_id"] == "overlay_fixture"
    assert ledger["demand_basis"] == "assumption_based_synthetic"
    assert ledger["calibrated_field_demand"] is False
    assert set(by_id) == {
        "commute_MOTORBIKE.0",
        "commute_MOTORBIKE.1",
        "commute_PRIVATE_CAR.0",
        "commute_PRIVATE_CAR.1",
    }
    assert by_id["commute_MOTORBIKE.0"] == {
        "trip_id": "commute_MOTORBIKE.0",
        "source_flow_id": "commute",
        "trip_purpose": "commute",
        "vehicle_type_id": "MOTORBIKE",
        "vehicle_class": "motorcycle",
        "intended_departure_seconds": 12.0,
        "origin_zone_id": "origin_zone",
        "destination_zone_id": "destination_zone",
        "origin_edge_id": "E1",
        "destination_edge_id": "E3",
        "route_status": "routed",
        "failure_reason": None,
        "failure_reason_source": None,
    }
    assert by_id["commute_MOTORBIKE.1"]["origin_edge_id"] == "E2"
    assert by_id["commute_MOTORBIKE.1"]["route_status"] == "not_routed"
    assert by_id["commute_MOTORBIKE.1"]["failure_reason"] == "unknown"
    assert by_id["commute_PRIVATE_CAR.0"]["route_status"] == "not_routed"
    assert by_id["commute_PRIVATE_CAR.1"]["route_status"] == "routed"

    qa = json.loads(first.qa_json.read_text(encoding="utf-8"))
    assert qa["attempted_trips"] == 4
    assert qa["routed_trips"] == 2
    assert qa["not_routed_trips"] == qa["failed_trips"] == 2
    assert qa["count_unit"] == "requested_vehicle_trip"
    assert qa["calibrated_field_demand"] is False
    assert qa["evidence_scope"] == "synthetic_assumption_not_calibrated_field_demand"
    assert "not calibrated field demand" in qa["caveat"]


def test_empty_valid_route_output_marks_every_trip_not_routed_with_unknown_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    net_path, net_index, overlay = _inputs(tmp_path)
    _patch_router(monkeypatch, "<routes />")

    result = _generate(tmp_path, net_path, net_index, overlay, "empty-routes")

    assert result.attempted_trips == 4
    assert result.routed_trips == 0
    assert result.failed_trips == 4
    ledger = json.loads(result.intended_demand_ledger.read_text(encoding="utf-8"))
    assert ledger["reconciliation_status"] == "reconciled"
    assert all(row["route_status"] == "not_routed" for row in ledger["trips"])
    assert all(row["failure_reason"] == "unknown" for row in ledger["trips"])


def _assert_unavailable_ledger(work_dir: Path) -> None:
    ledger_path = work_dir / "normal.intended_demand_ledger.json"
    qa_path = work_dir / "normal.demand_qa.json"
    assert ledger_path.is_file()
    assert qa_path.is_file()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    assert ledger["reconciliation_status"] == "unavailable"
    assert len(ledger["trips"]) == 4
    assert all(row["route_status"] == "routing_unverified" for row in ledger["trips"])
    assert all(row["failure_reason"] is None for row in ledger["trips"])
    assert qa["route_reconciliation_status"] == "unavailable"
    assert qa["attempted_trips"] == 4
    assert qa["routed_trips"] is None
    assert qa["not_routed_trips"] is None
    assert qa["failed_trips"] is None


@pytest.mark.parametrize(
    ("route_xml", "message"),
    [
        ("", "malformed duarouter route output"),
        ('<routes><vehicle id="commute_MOTORBIKE.0">', "malformed duarouter route output"),
        (
            '<routes><vehicle id="commute_MOTORBIKE.0"/></routes>',
            "no usable inline route",
        ),
        (
            '<routes><vehicle id="commute_MOTORBIKE.0"><route edges="  "/></vehicle></routes>',
            "no usable inline route",
        ),
        ("<routes><vehicle /></routes>", "empty or whitespace-padded id"),
        ('<routes><vehicle id="  "/></routes>', "empty or whitespace-padded id"),
        (
            '<routes><vehicle id="commute_MOTORBIKE.0"><route edges="E1"/>'
            '</vehicle><vehicle id="commute_MOTORBIKE.0"><route edges="E1"/>'
            "</vehicle></routes>",
            "duplicate vehicle id",
        ),
        (
            '<routes><vehicle id="unexpected"><route edges="E1"/></vehicle></routes>',
            "absent from intended-demand ledger",
        ),
        ("<route-files />", "expected 'routes'"),
    ],
)
def test_malformed_or_unmatched_route_identities_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_xml: str,
    message: str,
) -> None:
    net_path, net_index, overlay = _inputs(tmp_path)
    _patch_router(monkeypatch, route_xml)

    with pytest.raises(SumoMapSourceError, match=message):
        _generate(tmp_path, net_path, net_index, overlay, "bad-routes")

    _assert_unavailable_ledger(tmp_path / "bad-routes")


def test_missing_route_output_fails_closed_instead_of_counting_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    net_path, net_index, overlay = _inputs(tmp_path)
    _patch_router(monkeypatch, None)

    with pytest.raises(SumoMapSourceError, match="route output not found"):
        _generate(tmp_path, net_path, net_index, overlay, "missing-routes")

    _assert_unavailable_ledger(tmp_path / "missing-routes")


def test_pending_ledger_is_persisted_before_router_startup_and_survives_router_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    net_path, net_index, overlay = _inputs(tmp_path)
    work_dir = tmp_path / "router-crash"

    def crashing_router(*, routes_path: Path, **_: object) -> None:
        assert not routes_path.exists()
        ledger = json.loads(
            (work_dir / "normal.intended_demand_ledger.json").read_text(encoding="utf-8")
        )
        qa = json.loads((work_dir / "normal.demand_qa.json").read_text(encoding="utf-8"))
        assert ledger["reconciliation_status"] == "pending"
        assert len(ledger["trips"]) == 4
        assert all(row["route_status"] == "routing_unverified" for row in ledger["trips"])
        assert qa["route_reconciliation_status"] == "pending"
        assert qa["routed_trips"] is None
        raise SumoRuntimeError("duarouter failed before producing route output")

    monkeypatch.setattr(demand_module, "_run_duarouter", crashing_router)

    with pytest.raises(SumoRuntimeError, match="before producing route output"):
        _generate(tmp_path, net_path, net_index, overlay, "router-crash")

    _assert_unavailable_ledger(work_dir)


def test_real_duarouter_preserves_trip_identity_for_reconciliation_plumbing(
    tmp_path: Path,
) -> None:
    """Verify SUMO trip-to-vehicle ID plumbing only; this is not traffic evidence."""
    duarouter = resolve_sumo_binary("duarouter")
    if duarouter is None:
        pytest.skip("duarouter is not installed")

    fixture_dir = (
        Path(__file__).resolve().parents[3]
        / "simulation_projects"
        / "map_intake"
        / "02_prepared_sources"
        / "district7_osm_seed_20260702"
    )
    net_path = fixture_dir / "district7_seed.net.xml"
    sample_trips_path = fixture_dir / "district7_random.trips.xml"
    if not net_path.is_file() or not sample_trips_path.is_file():
        pytest.skip("prepared District 7 SUMO network fixture is unavailable")

    sample_trip = next(
        element
        for event, element in ET.iterparse(sample_trips_path, events=("end",))
        if element.tag.rsplit("}", 1)[-1] == "trip"
    )
    trip_id = "task100_duarouter_identity_probe"
    trip = ET.Element(
        "trip",
        {
            "id": trip_id,
            "depart": "0.0",
            "from": sample_trip.attrib["from"],
            "to": sample_trip.attrib["to"],
            "departLane": "best",
        },
    )
    trips_path = tmp_path / "identity_probe.trips.xml"
    routes_path = tmp_path / "identity_probe.rou.xml"
    _write_xml_for_test(ET.Element("routes"), trips_path, trip)

    demand_module._run_duarouter(
        duarouter_binary=duarouter,
        net_path=net_path,
        trips_path=trips_path,
        routes_path=routes_path,
        seed=73,
    )

    real_output_vehicle = next(
        element
        for event, element in ET.iterparse(routes_path, events=("end",))
        if element.tag.rsplit("}", 1)[-1] == "vehicle"
    )
    real_output_route = next(
        element
        for element in real_output_vehicle.iter()
        if element.tag.rsplit("}", 1)[-1] == "route"
    )
    assert real_output_route.attrib["edges"].split()
    assert demand_module._route_vehicle_ids(routes_path) == {trip_id}


def _write_xml_for_test(root: ET.Element, path: Path, child: ET.Element) -> None:
    root.append(child)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
