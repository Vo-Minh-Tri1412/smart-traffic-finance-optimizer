from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render.unreal_contract_smoke import run


def _write_run(tmp_path: Path, *, schema: str = "vehicle_trace.v2") -> Path:
    geometry = tmp_path / "geometry.json"
    geometry.write_text(
        json.dumps(
            {
                "schema_version": "geometry_manifest.v1",
                "geometry_source": "sumo_net_xml",
                "net_xml": "network.net.xml",
                "coordinate_system": "sumo_xy_meters",
                "bounds": {"min_x": 100.0, "min_y": 200.0, "max_x": 300.0, "max_y": 400.0},
                "local_origin": {"x": 100.0, "y": 200.0},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "network.net.xml").write_text("<net />", encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        json.dumps(
            {
                "schema_version": schema,
                "timestep": 0,
                "time_seconds": 0.0,
                "vehicles": [
                    {
                        "vehicle_id": "v1",
                        "vehicle_type": "car",
                        "x": 110.0,
                        "y": 220.0,
                        "speed": 5.0,
                        "angle": 0.0,
                        "length_m": 4.0,
                        "width_m": 2.0,
                        "height_m": 1.5,
                        "ground_clearance_m": 0.1,
                        "elevation_m": 0.0,
                        "reference_point": "front_bumper_center",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "render_run_manifest.v1",
                "run_id": "unreal-test",
                "geometry_manifest": geometry.name,
                "vehicle_trace": trace.name,
                "renderer": "unreal",
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_unreal_smoke_preserves_front_bumper_center_formula(tmp_path: Path) -> None:
    report = run(_write_run(tmp_path), None, None)
    assert report["success"] is True
    assert report["front_bumper_center_sample_m"] == {"x": 110.0, "y": 218.0}
    assert report["local_origin_meters"] == {"x": 100.0, "y": 200.0}


def test_unreal_smoke_rejects_legacy_trace_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported vehicle trace schema"):
        run(_write_run(tmp_path, schema="simulation_trace_frame.v1"), None, None)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "100", True])
def test_unreal_smoke_rejects_nonfinite_or_coerced_coordinates(
    tmp_path: Path, value: object
) -> None:
    manifest = _write_run(tmp_path)
    trace = tmp_path / "trace.jsonl"
    frame = json.loads(trace.read_text(encoding="utf-8"))
    frame["vehicles"][0]["x"] = value
    trace.write_text(json.dumps(frame), encoding="utf-8")
    with pytest.raises(ValueError, match="finite number"):
        run(manifest, None, None)


def test_unreal_smoke_rejects_duplicate_vehicle_ids(tmp_path: Path) -> None:
    manifest = _write_run(tmp_path)
    trace = tmp_path / "trace.jsonl"
    frame = json.loads(trace.read_text(encoding="utf-8"))
    frame["vehicles"].append(frame["vehicles"][0].copy())
    trace.write_text(json.dumps(frame), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate vehicle_id"):
        run(manifest, None, None)


def test_unreal_smoke_requires_network_geometry(tmp_path: Path) -> None:
    manifest = _write_run(tmp_path)
    geometry = tmp_path / "geometry.json"
    payload = json.loads(geometry.read_text(encoding="utf-8"))
    payload["net_xml"] = "missing.net.xml"
    geometry.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="net_xml file does not exist"):
        run(manifest, None, None)
