from __future__ import annotations

import pytest

from scripts.render.prepare_urban_environment import roof_geometry


def test_roof_preserves_concave_outline_and_courtyard() -> None:
    pytest.importorskip("shapely", reason="Optional urban source-preparation dependency")
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    footprint = Polygon(
        [(0, 0), (8, 0), (8, 8), (5, 8), (5, 5), (0, 5)],
        holes=[[(1, 1), (3, 1), (3, 3), (1, 3)]],
    )
    triangles = [Polygon(t) for t in roof_geometry(footprint)]
    assert len(triangles) > 2
    assert all(footprint.covers(triangle) for triangle in triangles)
    assert unary_union(triangles).symmetric_difference(footprint).area == pytest.approx(0)
