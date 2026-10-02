from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from ai_quantum_hvtc.simulation.engines.sumo.exporter import SumoExportPaths
from ai_quantum_hvtc.simulation.engines.sumo.parser import (
    parse_existing_sumo_net_result,
    parse_sumo_result,
)
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_sumo_parsers_leave_unavailable_bus_and_route_metrics_unknown(tmp_path: Path) -> None:
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(
        '<tripinfos><tripinfo id="bus.0" vType="BUS" waitingTime="12" arrival="60" /></tripinfos>',
        encoding="utf-8",
    )
    edge_data = tmp_path / "edge_data.xml"
    edge_data.write_text(
        '<meandata><interval begin="0" end="60"><edge id="E1" waitingTime="3" '
        'halting="1" sampledSeconds="30" /></interval></meandata>',
        encoding="utf-8",
    )
    paths = cast(
        SumoExportPaths,
        SimpleNamespace(
            tripinfo=tripinfo,
            edge_data=edge_data,
            fcd=tmp_path / "missing-fcd.xml",
            controller_log=tmp_path / "missing-controller-log.jsonl",
        ),
    )
    spec = load_district_spec(SPEC_PATH)

    spec_result = parse_sumo_result(
        paths=paths,
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )
    existing_net_result = parse_existing_sumo_net_result(
        paths=paths,
        district_id="existing_net",
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        seed=42,
    )

    for result in (spec_result, existing_net_result):
        assert result.bus_passenger_delay_seconds is None
        assert result.reroute_count is None
        assert result.failed_route_count is None
        assert result.to_dict()["bus_passenger_delay_seconds"] is None
        assert result.to_dict()["reroute_count"] is None
        assert result.to_dict()["failed_route_count"] is None
        assert all(
            metric.bus_passenger_delay_seconds is None for metric in result.intersections.values()
        )
    assert existing_net_result.intersections["E1"].bus_passenger_delay_seconds is None


def test_sumo_parsers_only_sum_complete_tripinfo_reroute_counts(
    tmp_path: Path,
) -> None:
    cases = (
        (
            '<tripinfos><tripinfo id="a" rerouteNo="2" />'
            '<tripinfo id="b" rerouteNo="1" /></tripinfos>',
            3,
        ),
        (
            '<tripinfos><tripinfo id="a" rerouteNo="2" /><tripinfo id="b" /></tripinfos>',
            None,
        ),
        ('<tripinfos><tripinfo id="a" rerouteNo="invalid" /></tripinfos>', None),
        ('<tripinfos><tripinfo id="a" rerouteNo="-1" /></tripinfos>', None),
        ("<tripinfos />", None),
    )

    for index, (tripinfo_xml, expected_count) in enumerate(cases):
        case_dir = tmp_path / str(index)
        case_dir.mkdir()
        results = _parse_sumo_results(case_dir, tripinfo_xml)
        assert [result.reroute_count for result in results] == [
            expected_count,
            expected_count,
        ]


def _parse_sumo_results(tmp_path: Path, tripinfo_xml: str):
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(tripinfo_xml, encoding="utf-8")
    paths = cast(
        SumoExportPaths,
        SimpleNamespace(
            tripinfo=tripinfo,
            edge_data=tmp_path / "missing-edge-data.xml",
            fcd=tmp_path / "missing-fcd.xml",
            controller_log=tmp_path / "missing-controller-log.jsonl",
        ),
    )
    spec = load_district_spec(SPEC_PATH)
    return (
        parse_sumo_result(
            paths=paths,
            spec=spec,
            scenario_id="normal_weekday",
            controller_id="fixed_time",
            seed=42,
        ),
        parse_existing_sumo_net_result(
            paths=paths,
            district_id="existing_net",
            scenario_id="normal_weekday",
            controller_id="fixed_time",
            seed=42,
        ),
    )
