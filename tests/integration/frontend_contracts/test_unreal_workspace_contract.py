"""Guard the renderer retirement without claiming planned UE features exist."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_only_active_renderer_workspace_remains() -> None:
    assert not (ROOT / "render").exists()
    assert (ROOT / "render_unreal" / "TrafficRender.uproject").is_file()
    assert (ROOT / "render_assets" / "vehicles" / "sedan.glb").is_file()
    assert not list((ROOT / "render_assets").rglob("*.import"))


def test_retired_engine_entrypoints_are_not_active() -> None:
    assert not list((ROOT / "scripts" / "render").glob("godot_*.py"))
    assert not list((ROOT / "docs" / "02_ARCHITECTURE").glob("GODOT_*.md"))


def test_delivery_plan_is_indexed_and_explicitly_planned() -> None:
    docs = ROOT / "docs"
    index = (docs / "README.md").read_text(encoding="utf-8")
    assert "SYSTEM_DELIVERY_PLAN.md" in index
    assert "UNREAL_ASSET_PIPELINE.md" in index
    plan = (docs / "02_ARCHITECTURE" / "SYSTEM_DELIVERY_PLAN.md").read_text(encoding="utf-8")
    assert "M0 đang triển khai; M1–M6 chưa nghiệm thu" in plan
    for milestone in range(7):
        assert f"### M{milestone}" in plan
