from __future__ import annotations

import pytest

pytest.importorskip("osmium")
pytest.importorskip("pyproj")
pytest.importorskip("shapely")

from shapely import STRtree  # noqa: E402
from shapely.geometry import Point, box  # noqa: E402

from scripts.maps import extract_building_footprints_geofabrik as footprints  # noqa: E402


def test_net_roi_uses_orig_boundary_and_projected_margin(tmp_path) -> None:
    net_path = tmp_path / "retained.net.xml"
    net_path.write_text(
        '<net><location netOffset="-684921.90,-1182571.50" '
        'origBoundary="106.690981,10.692829,106.788488,10.779370" '
        'projParameter="+proj=utm +zone=48 +ellps=WGS84 +datum=WGS84 +units=m +no_defs" />'
        "</net>",
        encoding="utf-8",
    )

    context = footprints._load_net_context(net_path, margin_m=500)

    min_x, min_y, max_x, max_y = context.net_boundary_xy.bounds
    roi_min_x, roi_min_y, roi_max_x, roi_max_y = context.search_roi_xy.bounds
    assert roi_min_x == pytest.approx(min_x - 500, abs=0.02)
    assert roi_min_y == pytest.approx(min_y - 500, abs=0.02)
    assert roi_max_x == pytest.approx(max_x + 500, abs=0.02)
    assert roi_max_y == pytest.approx(max_y + 500, abs=0.02)
    assert context.search_roi_xy.covers(context.net_boundary_xy)
    assert context.search_bbox_wgs84[0] < context.original_bounds[0]
    assert context.search_bbox_wgs84[2] > context.original_bounds[2]

    center = Point(
        (context.original_bounds[0] + context.original_bounds[2]) / 2,
        (context.original_bounds[1] + context.original_bounds[3]) / 2,
    )
    projected_center = context.project_geometry(center)
    assert 4_000 < projected_center.x < 7_000
    assert 3_000 < projected_center.y < 6_500


def test_boundary_qa_distinguishes_crossing_contained_and_margin_only() -> None:
    retained_boundary = box(0, 0, 10, 10)

    contained = footprints._summarize_geometry_against_boundary(box(2, 2, 8, 8), retained_boundary)
    crossing = footprints._summarize_geometry_against_boundary(box(8, 2, 12, 8), retained_boundary)
    margin_only = footprints._summarize_geometry_against_boundary(
        box(11, 2, 12, 8), retained_boundary
    )

    assert contained["fully_within_retained_net_boundary"]
    assert not contained["crosses_or_extends_outside_retained_net_boundary"]
    assert crossing["intersects_retained_net_boundary"]
    assert crossing["crosses_or_extends_outside_retained_net_boundary"]
    assert not margin_only["intersects_retained_net_boundary"]


def test_road_qa_flags_lane_and_junction_overlaps_separately() -> None:
    lane_corridors = [box(0, 0, 1, 1)]
    junction_envelopes = [box(3, 3, 4, 4)]
    lane_tree = STRtree(lane_corridors)
    junction_tree = STRtree(junction_envelopes)

    lane_overlap = footprints._road_qa(
        box(0.5, 0.5, 1.5, 1.5),
        lane_tree,
        lane_corridors,
        junction_tree,
        junction_envelopes,
    )
    junction_overlap = footprints._road_qa(
        box(3.5, 3.5, 4.5, 4.5),
        lane_tree,
        lane_corridors,
        junction_tree,
        junction_envelopes,
    )

    assert lane_overlap["lane_corridor_overlap"]
    assert lane_overlap["lane_corridor_overlap_area_m2"] > 0
    assert not lane_overlap["junction_envelope_overlap"]
    assert not junction_overlap["lane_corridor_overlap"]
    assert junction_overlap["junction_envelope_overlap"]
    assert junction_overlap["junction_envelope_overlap_area_m2"] > 0
