from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_quantum_hvtc.dashboard.app import create_app
from ai_quantum_hvtc.dashboard.config import DashboardConfig
from ai_quantum_hvtc.dashboard.routers.runs import _metrics_summary
from ai_quantum_hvtc.dashboard.store import RunStore
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def test_dashboard_keeps_unknown_sumo_metrics_null_in_api_and_trace(tmp_path: Path) -> None:
    absent_summary = _metrics_summary({})
    assert absent_summary.bus_passenger_delay_seconds is None
    assert absent_summary.reroute_count is None
    assert absent_summary.failed_route_count is None

    spec = load_district_spec(SPEC_PATH)
    store = RunStore(tmp_path / "runs")
    for controller_id, waiting in (("fixed_time", 100.0), ("rule_based", 70.0)):
        result = SimulationResult(
            scenario_id="normal_weekday",
            controller_id=controller_id,
            engine_id="sumo",
            seed=42,
            total_vehicles=10,
            throughput=9,
            total_waiting_time_seconds=waiting,
            average_waiting_time_seconds=waiting / 10,
            max_queue_vehicles=3.0,
            average_queue_vehicles=2.0,
            stopped_vehicles=4,
            emergency_delay_seconds=0.0,
            bus_passenger_delay_seconds=None,
            truck_delay_seconds=0.0,
            reroute_count=None,
            failed_route_count=None,
            intersections={
                "I03": IntersectionMetric(
                    intersection_id="I03",
                    bus_passenger_delay_seconds=None,
                )
            },
        )
        store.save_run(
            result=result,
            spec=spec,
            district_id=spec.metadata.district_id,
            run_id=f"{controller_id}-unknown-metrics",
        )

    config = DashboardConfig(
        spec_path=SPEC_PATH,
        runs_dir=tmp_path / "runs",
        frontend_dist=tmp_path / "missing-frontend",
        seed_demo_runs=False,
    )
    with TestClient(create_app(config)) as client:
        listing = client.get("/api/runs")
        assert listing.status_code == 200
        runs = listing.json()["runs"]
        assert len(runs) == 2
        assert all(run["metrics"]["bus_passenger_delay_seconds"] is None for run in runs)
        assert all(run["metrics"]["reroute_count"] is None for run in runs)
        assert all(run["metrics"]["failed_route_count"] is None for run in runs)

        detail = client.get("/api/runs/fixed_time-unknown-metrics")
        assert detail.status_code == 200
        assert detail.json()["intersections"]["I03"]["bus_passenger_delay_seconds"] is None

        compare = client.get(
            "/api/compare",
            params={"scenario_id": "normal_weekday", "engine_id": "sumo"},
        )
        assert compare.status_code == 200
        compare_rows = compare.json()["rows"]
        assert all(row["bus_passenger_delay_seconds"] is None for row in compare_rows)
        assert all(
            row["bus_passenger_delay_saved_vs_fixed_seconds"] is None for row in compare_rows
        )

        finance = client.post(
            "/api/finance/optimize",
            json={
                "budget_vnd": 2_000_000,
                "algorithm": "greedy",
                "scenario_id": "normal_weekday",
                "controller_id": "rule_based",
                "engine_id": "sumo",
            },
        )
        assert finance.status_code == 422
        assert finance.json()["detail"] == (
            "Cannot score candidates; required metrics are unavailable: "
            "bus_passenger_delay_seconds, reroute_count, failed_route_count"
        )

        trace = client.get(
            "/api/runs/fixed_time-unknown-metrics/trace",
            params={"limit": 100},
        )
        assert trace.status_code == 200
        assert all(
            event["type"] != "failed_routes_observed"
            for frame in trace.json()["frames"]
            for event in frame["events"]
        )
