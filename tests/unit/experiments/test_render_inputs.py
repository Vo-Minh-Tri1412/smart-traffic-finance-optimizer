from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_quantum_hvtc.experiments.render_inputs import write_render_inputs
from ai_quantum_hvtc.simulation.maps.source import SumoNetSource, SumoProjectDescriptor

NET = """<net>
  <edge id="E1"><lane id="E1_0" index="0" shape="1,2 3,4"/></edge>
  <junction id="J1" type="traffic_light" x="0" y="1"/>
</net>"""


def _project(tmp_path: Path) -> SumoProjectDescriptor:
    net = tmp_path / "map.net.xml"
    net.write_text(NET, encoding="utf-8")
    overlay = tmp_path / "overlay.json"
    overlay.write_text('{"schema_version":"roi_semantic_overlay.v2"}', encoding="utf-8")
    demand = tmp_path / "demand.json"
    demand.write_text("{}", encoding="utf-8")
    return SumoProjectDescriptor(
        project_id="project",
        name="Project",
        version="v1",
        source=SumoNetSource(net_path=net, source_id="map"),
        overlay_path=overlay,
        demand_config_path=demand,
    )


def test_writes_render_manifests_from_real_net_and_run_trace(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "vehicle_trace.jsonl").write_text(
        '{"schema_version":"vehicle_trace.v2"}\n',
        encoding="utf-8",
    )
    run = {"experiment_id": "experiment-1", "run_id": "run-1"}

    write_render_inputs(directory=run_dir, run=run, project=project)

    geometry = json.loads((run_dir / "geometry_manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "render_run_manifest.json").read_text(encoding="utf-8"))
    assert geometry["experiment_id"] == manifest["experiment_id"] == run["experiment_id"]
    assert geometry["run_id"] == manifest["run_id"] == run["run_id"]
    assert geometry["geometry_source"] == "sumo_net_xml"
    assert geometry["coordinate_system"] == "sumo_xy_meters"
    assert geometry["net_xml"] == str(project.source.net_path.resolve())
    assert geometry["bounds"] == {"min_x": 0.0, "min_y": 1.0, "max_x": 3.0, "max_y": 4.0}
    assert geometry["local_origin"] == {"x": 0.0, "y": 1.0}
    assert manifest["vehicle_trace"] == "vehicle_trace.jsonl"
    assert manifest["semantic_overlay"] == str(project.overlay_path.resolve())
    assert manifest["traffic_light_trace"] == ""
    assert manifest["event_trace"] == ""
    assert manifest["renderer"] == "unreal"
    assert manifest["render_executed"] is False


def test_render_manifests_are_exclusive(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "vehicle_trace.jsonl").write_text("{}\n", encoding="utf-8")
    write_render_inputs(
        directory=run_dir,
        run={"experiment_id": "exp", "run_id": "run"},
        project=project,
    )
    geometry_before = (run_dir / "geometry_manifest.json").read_bytes()

    with pytest.raises(FileExistsError):
        write_render_inputs(
            directory=run_dir,
            run={"experiment_id": "other", "run_id": "other"},
            project=project,
        )

    assert (run_dir / "geometry_manifest.json").read_bytes() == geometry_before


def test_render_inputs_require_vehicle_trace(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="vehicle trace"):
        write_render_inputs(
            directory=run_dir,
            run={"experiment_id": "exp", "run_id": "run"},
            project=_project(tmp_path),
        )
