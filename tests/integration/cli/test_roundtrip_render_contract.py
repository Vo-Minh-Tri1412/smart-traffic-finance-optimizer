import json
from pathlib import Path
from types import SimpleNamespace

from scripts.smoke.district7_roundtrip_smoke import _validate_render_inputs, build_parser


def test_roundtrip_validates_contract_without_rendering(tmp_path: Path) -> None:
    net = tmp_path / "net.xml"
    net.write_text("<net/>", encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({
        "schema_version": "vehicle_trace.v2", "time_seconds": 0,
        "timestep": 0, "vehicles": [],
    }) + "\n", encoding="utf-8")
    args = dict(trace_path=trace, net_path=net, overlay_path=tmp_path / "overlay.json",
                output_root=tmp_path / "contract",
                net_index=SimpleNamespace(bounds_min=(0, 0), bounds_max=(10, 10)),
                max_frames=10)
    result = _validate_render_inputs(**args)
    assert result["status"] == "ok"
    assert result["render_executed"] is False
    assert result["summary"]["loaded_frame_count"] == 1
    trace.write_text("{}\n", encoding="utf-8")
    result = _validate_render_inputs(**args)
    assert result["status"] == "failed"
    assert result["render_executed"] is False


def test_roundtrip_help_describes_contract_only() -> None:
    assert "no rendering" in build_parser().format_help()
