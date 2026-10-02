import pytest

from scripts.render.benchmark_city_level import (
    _benchmark_completeness,
    _frame_time_gate,
    _parse_fps_chart_csv,
)


def _write_chart(path, *, row_count, frame_ms, gpu_ms, columns=None):
    header = columns or [
        "Time (sec)",
        "Frame (ms)",
        "GT (ms)",
        "RT (ms)",
        "GPU (ms)",
        "DynRes",
        "Context",
    ]
    rows = [",".join(header)]
    step_seconds = frame_ms / 1000.0
    for index in range(row_count):
        values = [
            f"{index * step_seconds:.3f}",
            str(frame_ms),
            "8",
            "12",
            str(gpu_ms),
            "100",
            "0",
        ]
        rows.append(",".join(values[: len(header)]))
    path.write_text("\n".join(rows), encoding="utf-8")


def test_fps_chart_parser_uses_per_frame_rows_and_nearest_rank_percentiles(tmp_path):
    chart = tmp_path / "District7-FPS-Windows.csv"
    chart.write_text(
        "\n".join(
            [
                "Percentile,Frame (ms), GT (ms), RT (ms), GPU (ms),DynRes,Context",
                "25,10,3,5,0.4,100,0",
                "50,30,5,7,0.5,100,0",
                "75,40,6,8,0.6,100,0",
                "Time (sec),Frame (ms), GT (ms), RT (ms), GPU (ms),DynRes,Context",
                "0.00,10,3,5,0.4,100,0",
                "0.03,20,4,6,0.0,100,0",
                "0.06,30,5,7,0.5,100,0",
                "0.09,40,6,8,0.6,100,0",
                "0.12,100,9,10,1.0,100,0",
            ]
        ),
        encoding="utf-8",
    )

    report = _parse_fps_chart_csv(chart)

    assert report["sample_count"] == 5
    assert report["invalid_row_count"] == 0
    assert report["percentile_method"] == "nearest_rank"
    assert report["series_ms"]["frame"]["p95"] == 100.0
    assert report["series_ms"]["game_thread"]["p95"] == 9.0
    assert report["series_ms"]["render_thread"]["p95"] == 10.0
    assert report["gpu_sample_count_nonzero"] == 4
    assert report["gpu_sample_count_zero"] == 1
    assert report["series_ms"]["gpu"]["p95"] == 1.0


def test_zero_gpu_samples_fail_the_d3d12_frame_time_gate(tmp_path):
    chart = tmp_path / "zero-gpu-FPS-Windows.csv"
    _write_chart(chart, row_count=1803, frame_ms=33, gpu_ms=0)
    report = _parse_fps_chart_csv(chart)

    gate = _frame_time_gate(report, {"rhi": "D3D12"}, [1920, 1080], 60.0)

    assert report["gpu_sample_count_nonzero"] == 0
    assert report["series_ms"]["gpu"] is None
    assert not gate["passed"]
    assert "gpu_sample_coverage_at_least_95_percent" in gate["failure_reasons"]


def test_fps_chart_missing_required_timing_column_is_rejected(tmp_path):
    chart = tmp_path / "missing-gpu-FPS-Windows.csv"
    _write_chart(
        chart,
        row_count=1,
        frame_ms=20,
        gpu_ms=1,
        columns=["Time (sec)", "Frame (ms)", "GT (ms)", "RT (ms)"],
    )

    with pytest.raises(ValueError, match="missing columns"):
        _parse_fps_chart_csv(chart)


def test_invalid_frame_rows_fail_even_when_remaining_sample_is_large(tmp_path):
    chart = tmp_path / "invalid-row-FPS-Windows.csv"
    _write_chart(chart, row_count=1803, frame_ms=33, gpu_ms=20)
    chart.write_text(
        chart.read_text(encoding="utf-8") + "\nbroken,row\n",
        encoding="utf-8",
    )
    report = _parse_fps_chart_csv(chart)

    gate = _frame_time_gate(report, {"rhi": "D3D12"}, [1920, 1080], 60.0)

    assert report["sample_count"] == 1803
    assert report["invalid_row_count"] == 1
    assert not gate["checks"]["no_invalid_csv_rows"]
    assert not gate["passed"]


def test_short_csv_time_span_cannot_pass_with_long_callback_wall_time(tmp_path):
    chart = tmp_path / "short-FPS-Windows.csv"
    _write_chart(chart, row_count=100, frame_ms=20, gpu_ms=1)
    report = _parse_fps_chart_csv(chart)

    gate = _frame_time_gate(report, {"rhi": "D3D12"}, [1920, 1080], 60.0)

    assert report["csv_time_span_seconds"] < 59.0
    assert not gate["checks"]["fps_chart_time_span_at_least_59_seconds"]
    assert not gate["passed"]


def test_sparse_rows_cannot_pass_with_long_callback_wall_time(tmp_path):
    chart = tmp_path / "sparse-FPS-Windows.csv"
    _write_chart(chart, row_count=10, frame_ms=6000, gpu_ms=20)
    report = _parse_fps_chart_csv(chart)

    gate = _frame_time_gate(report, {"rhi": "D3D12"}, [1920, 1080], 60.0)

    assert report["csv_time_span_seconds"] == 54.0
    assert report["sample_count"] == 10
    assert not gate["checks"]["at_least_1500_frame_samples"]
    assert not gate["checks"]["fps_chart_time_span_at_least_59_seconds"]
    assert not gate["passed"]


def test_missing_visible_count_keeps_full_acceptance_incomplete():
    completeness = _benchmark_completeness(
        True,
        visible_count_available=False,
        gpu_memory_available=True,
        preset_recorded=True,
    )

    assert not completeness["complete"]
    assert completeness["failure_reasons"] == ["visible_count_available"]
