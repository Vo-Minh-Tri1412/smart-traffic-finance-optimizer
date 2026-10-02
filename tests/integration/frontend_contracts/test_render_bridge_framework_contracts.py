from pathlib import Path

from ai_quantum_hvtc.simulation.traces.versions import RENDER_BRIDGE_SCHEMA_VERSIONS

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_render_bridge_architecture_docs_exist() -> None:
    for name in (
        "SUMO_RENDER_BRIDGE_FRAMEWORK.md",
        "RENDER_BRIDGE_CONTRACTS.md",
        "UNREAL_ASSET_PIPELINE.md",
    ):
        assert (PROJECT_ROOT / "docs" / "02_ARCHITECTURE" / name).is_file()


def test_render_bridge_schema_versions_are_declared_in_python_and_unreal() -> None:
    header = (
        PROJECT_ROOT / "render_unreal/Plugins/TrafficRenderBridge/Source/"
        "TrafficRenderRuntime/Public/TrafficRenderSchemas.h"
    ).read_text(encoding="utf-8")
    assert len(RENDER_BRIDGE_SCHEMA_VERSIONS) == 8
    for version in RENDER_BRIDGE_SCHEMA_VERSIONS.values():
        assert version in header
