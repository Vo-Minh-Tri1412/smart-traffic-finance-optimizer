from __future__ import annotations

from scripts.render.prepare_city_placements import _inside, _representative_point


def test_concave_zone_uses_an_interior_visual_site() -> None:
    polygon = (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 2.0),
        (2.0, 2.0),
        (2.0, 10.0),
        (0.0, 10.0),
    )
    outside_centroid = (3.2, 3.2)
    assert not _inside(outside_centroid, polygon)

    site = _representative_point(polygon, outside_centroid, minimum_clearance=0.5)

    assert site is not None
    point, clearance = site
    assert _inside(point, polygon)
    assert clearance >= 0.5


def test_narrow_zone_does_not_receive_an_oversized_site() -> None:
    polygon = ((0.0, 0.0), (20.0, 0.0), (20.0, 1.0), (0.0, 1.0))

    assert _representative_point(polygon, (10.0, 0.5), minimum_clearance=2.0) is None
