"""Measure gameplay frame times from UE's FPS chart, with an optional proxy.

The default gameplay mode starts an in-process New Editor Window PIE session,
sets its view target to the saved city camera, warms up for 20 seconds, then
captures 60 seconds using StartFPSChart/StopFPSChart. The optional ``proxy``
mode retains the older Editor + SceneCapture/Slate-tick diagnostic; it is never
an acceptance measurement.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import unreal
except ImportError:  # Allows unit-testing the pure FPS-chart parser outside the Editor.
    unreal = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
DEFAULT_LEVEL_ASSET = "/Game/City/District7_Styled/District7_Styled"
DEFAULT_CAMERA_LABEL = "Retained City Hero Corner"
DEFAULT_GAMEPLAY_REPORT_PATH = (
    ROOT / "artifacts" / "tmp" / "city_pipeline" / "city_gameplay_benchmark.json"
)
DEFAULT_PROXY_REPORT_PATH = (
    ROOT / "artifacts" / "tmp" / "city_pipeline" / "styled_city_benchmark.json"
)
DEFAULT_COMMAND_LOG_PATH = PROJECT_ROOT / "Saved" / "Logs" / "TrafficRender.log"
WIDTH = 1920
HEIGHT = 1080
WARMUP_SECONDS = 20.0
SAMPLE_SECONDS = 60.0
TIMEOUT_SECONDS = 600.0
PLAY_START_TIMEOUT_SECONDS = 30.0
CHART_WRITE_TIMEOUT_SECONDS = 10.0
ACCEPTANCE_FRAME_P95_MS = 33.3
ROAD_ACTOR_CLASS = "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
VISUAL_ACTOR_CLASS = "/Script/TrafficRenderRuntime.TrafficCityVisualActor"
SCALABILITY_CVARS = (
    "sg.ViewDistanceQuality",
    "sg.AntiAliasingQuality",
    "sg.ShadowQuality",
    "sg.GlobalIlluminationQuality",
    "sg.ReflectionQuality",
    "sg.PostProcessQuality",
    "sg.TextureQuality",
    "sg.EffectsQuality",
    "sg.FoliageQuality",
    "sg.ShadingQuality",
)


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default.resolve()
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


def _level_asset_path(value: str) -> str:
    path = value.strip().rstrip("/")
    if not path.startswith("/Game/") or path.endswith(".umap"):
        raise ValueError("AIQ_CITY_LEVEL_PATH must be a /Game package path without .umap")
    return path


def _percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot compute percentiles without samples")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _sample_gpu_memory() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "error": str(exc)}
    if result.returncode != 0:
        return {
            "available": False,
            "error": result.stderr.strip() or f"nvidia-smi exited {result.returncode}",
        }

    devices: list[dict[str, Any]] = []
    for row in result.stdout.splitlines():
        fields = [field.strip() for field in row.split(",")]
        if len(fields) != 4:
            continue
        try:
            devices.append(
                {
                    "index": int(fields[0]),
                    "name": fields[1],
                    "memory_used_mib": int(fields[2]),
                    "memory_total_mib": int(fields[3]),
                }
            )
        except ValueError:
            continue
    if not devices:
        return {"available": False, "error": "nvidia-smi returned no parseable GPU rows"}
    return {"available": True, "devices": devices}


def _read_actor_summary(actor: Any) -> dict[str, Any] | None:
    try:
        raw = actor.get_build_summary_json()
        parsed = json.loads(raw) if isinstance(raw, str) else None
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _scene_counts(actors: list[Any]) -> dict[str, Any]:
    road_actors = [
        actor for actor in actors if actor.get_class().get_path_name() == ROAD_ACTOR_CLASS
    ]
    visual_actors = [
        actor for actor in actors if actor.get_class().get_path_name() == VISUAL_ACTOR_CLASS
    ]

    road_summaries = [summary for actor in road_actors if (summary := _read_actor_summary(actor))]
    rendered_tile_count: int | None = None
    rendered_segment_count: int | None = None
    if road_summaries:
        tile_values = [summary.get("rendered_tile_count") for summary in road_summaries]
        if all(isinstance(value, (int, float)) for value in tile_values):
            rendered_tile_count = sum(int(value) for value in tile_values)
        segment_values = [summary.get("rendered_segment_count") for summary in road_summaries]
        if all(isinstance(value, (int, float)) for value in segment_values):
            rendered_segment_count = sum(int(value) for value in segment_values)

    visual_summaries = [
        summary for actor in visual_actors if (summary := _read_actor_summary(actor))
    ]
    summary_instance_total: int | None = None
    if visual_summaries:
        component_totals: list[int] = []
        for summary in visual_summaries:
            building_count = summary.get("rendered_building_count")
            landscape_count = summary.get("rendered_landscape_count")
            if not isinstance(building_count, (int, float)) or not isinstance(
                landscape_count, (int, float)
            ):
                break
            component_totals.append(int(building_count) + int(landscape_count))
        if len(component_totals) == len(visual_summaries):
            summary_instance_total = sum(component_totals)

    hism_component_count = 0
    hism_instance_total = 0
    hism_instance_count_available = True
    try:
        hism_class = unreal.HierarchicalInstancedStaticMeshComponent
        for actor in visual_actors:
            components = actor.get_components_by_class(hism_class)
            hism_component_count += len(components)
            for component in components:
                try:
                    hism_instance_total += int(component.get_instance_count())
                except Exception:
                    hism_instance_count_available = False
    except Exception:
        hism_instance_count_available = False

    if hism_instance_count_available and hism_component_count:
        visual_instance_count = hism_instance_total
        visual_instance_count_source = "HierarchicalInstancedStaticMeshComponent.get_instance_count"
    elif summary_instance_total is not None:
        visual_instance_count = summary_instance_total
        visual_instance_count_source = "TrafficCityVisualActor build summary"
    else:
        visual_instance_count = None
        visual_instance_count_source = None

    return {
        "road_geometry_actor_count": len(road_actors),
        "rendered_road_tile_count": rendered_tile_count,
        "rendered_road_segment_count": rendered_segment_count,
        "road_tile_count_source": (
            "TrafficSumoGeometryActor build summary" if rendered_tile_count is not None else None
        ),
        "visual_actor_count": len(visual_actors),
        "hism_component_count": hism_component_count if hism_component_count else None,
        "hism_visual_instance_count": visual_instance_count,
        "hism_visual_instance_count_source": visual_instance_count_source,
        "visual_build_summaries": visual_summaries,
    }


def _renderer_from_command_log(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"command_log_path": str(path), "rhi": "unverified"}
    try:
        log_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result["evidence"] = f"command log unavailable: {exc}"
        return result
    if "CITY_BENCHMARK_START" not in log_text:
        result["evidence"] = "command log does not contain this benchmark session marker"
        return result
    for marker, rhi in (
        ("LogD3D12RHI:", "D3D12"),
        ("LogVulkanRHI:", "Vulkan"),
        ("LogD3D11RHI:", "D3D11"),
    ):
        if marker in log_text:
            result["rhi"] = rhi
            result["evidence"] = f"{marker} entry present in Unreal command log"
            return result
    result["evidence"] = "no recognized RHI marker in Unreal command log"
    return result


def _fps_chart_csv_root() -> Path:
    return PROJECT_ROOT / "Saved" / "Profiling" / "FPSChartStats"


def _fps_chart_csv_paths() -> set[Path]:
    root = _fps_chart_csv_root()
    if not root.is_dir():
        return set()
    return {path.resolve() for path in root.rglob("*-FPS-Windows.csv") if path.is_file()}


def _parse_fps_chart_csv(path: Path) -> dict[str, Any]:
    """Read the per-frame section written by UE 5.8 StopFPSChart."""
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as csv_file:
        rows = list(csv.reader(csv_file))

    frame_header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row and row[0].strip().casefold() == "time (sec)"
        ),
        None,
    )
    if frame_header_index is None:
        raise ValueError(f"FPS chart has no per-frame section: {path}")

    header = [column.strip().casefold() for column in rows[frame_header_index]]
    required_columns = {
        "time (sec)": "time_seconds",
        "frame (ms)": "frame_ms",
        "gt (ms)": "game_thread_ms",
        "rt (ms)": "render_thread_ms",
        "gpu (ms)": "gpu_ms",
    }
    indices = {name: header.index(name) for name in required_columns if name in header}
    missing = set(required_columns) - indices.keys()
    if missing:
        raise ValueError(f"FPS chart is missing columns {sorted(missing)}: {path}")

    samples: list[dict[str, float]] = []
    invalid_row_count = 0
    for row in rows[frame_header_index + 1 :]:
        if not row or not any(cell.strip() for cell in row):
            continue
        try:
            sample = {key: float(row[indices[column]]) for column, key in required_columns.items()}
        except (IndexError, ValueError):
            invalid_row_count += 1
            continue
        if not all(math.isfinite(value) for value in sample.values()):
            invalid_row_count += 1
            continue
        if sample["time_seconds"] < 0 or sample["frame_ms"] <= 0:
            invalid_row_count += 1
            continue
        if any(sample[key] < 0 for key in ("game_thread_ms", "render_thread_ms", "gpu_ms")):
            invalid_row_count += 1
            continue
        samples.append(sample)

    if not samples:
        raise ValueError(f"FPS chart contains no valid per-frame timing rows: {path}")
    gpu_nonzero = [sample["gpu_ms"] for sample in samples if sample["gpu_ms"] > 0]
    chart_times = [sample["time_seconds"] for sample in samples]
    timing: dict[str, Any] = {
        "sample_count": len(samples),
        "invalid_row_count": invalid_row_count,
        "csv_time_span_seconds": round(max(chart_times) - min(chart_times), 3),
        "sampled_frame_delta_sum_seconds": round(
            sum(sample["frame_ms"] for sample in samples) / 1000.0, 3
        ),
        "percentile_method": "nearest_rank",
        "series_ms": {},
    }
    for key, label in (
        ("frame_ms", "frame"),
        ("game_thread_ms", "game_thread"),
        ("render_thread_ms", "render_thread"),
    ):
        values = [sample[key] for sample in samples]
        timing["series_ms"][label] = _timing_summary(values)

    timing["gpu_sample_count_nonzero"] = len(gpu_nonzero)
    timing["gpu_sample_count_zero"] = len(samples) - len(gpu_nonzero)
    timing["series_ms"]["gpu"] = _timing_summary(gpu_nonzero) if gpu_nonzero else None
    return timing


def _timing_summary(values: list[float]) -> dict[str, float]:
    return {
        key: round(_percentile_nearest_rank(values, percentile), 3)
        for key, percentile in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))
    } | {"max": round(max(values), 3)}


def _viewport_size_px(world: Any) -> list[int] | None:
    try:
        size = unreal.WidgetLayoutLibrary.get_viewport_size(world)
        width = int(round(float(size.x)))
        height = int(round(float(size.y)))
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return [width, height]


def _preset_summary() -> dict[str, Any]:
    quality_values: dict[str, int | None] = {}
    for name in SCALABILITY_CVARS:
        try:
            quality_values[name] = int(unreal.SystemLibrary.get_console_variable_int_value(name))
        except Exception:
            quality_values[name] = None
    try:
        screen_percentage = float(
            unreal.SystemLibrary.get_console_variable_float_value("r.ScreenPercentage")
        )
    except Exception:
        screen_percentage = None
    try:
        dynamic_resolution_mode = int(
            unreal.SystemLibrary.get_console_variable_int_value("r.DynamicRes.OperationMode")
        )
    except Exception:
        dynamic_resolution_mode = None
    return {
        "label": os.environ.get("AIQ_CITY_BENCHMARK_PRESET", "project_current").strip(),
        "scalability_cvars": quality_values,
        "screen_percentage": screen_percentage,
        "dynamic_resolution_operation_mode": dynamic_resolution_mode,
        "fps_chart_exclude_idle_time": int(
            unreal.SystemLibrary.get_console_variable_int_value("t.FPSChart.ExcludeIdleTime")
        ),
    }


def _find_new_fps_chart_csv(paths_before: set[Path]) -> Path | None:
    new_paths = sorted(_fps_chart_csv_paths() - paths_before, key=lambda item: item.stat().st_mtime)
    return new_paths[-1] if new_paths else None


def _frame_time_gate(
    timing: dict[str, Any],
    renderer: dict[str, Any],
    resolution_px: list[int] | None,
    sample_actual_seconds: float,
) -> dict[str, Any]:
    gpu_sample_coverage = timing["gpu_sample_count_nonzero"] / timing["sample_count"]
    frame_p95 = timing["series_ms"]["frame"]["p95"]
    checks = {
        "d3d12_rhi": renderer["rhi"] == "D3D12",
        "no_invalid_csv_rows": timing["invalid_row_count"] == 0,
        "gpu_sample_coverage_at_least_95_percent": gpu_sample_coverage >= 0.95,
        "viewport_1920x1080": resolution_px == [WIDTH, HEIGHT],
        "captured_wall_time_at_least_59_seconds": sample_actual_seconds >= SAMPLE_SECONDS - 1.0,
        "fps_chart_time_span_at_least_59_seconds": (
            timing["csv_time_span_seconds"] >= SAMPLE_SECONDS - 1.0
        ),
        "sampled_frame_delta_sum_at_least_59_seconds": (
            timing["sampled_frame_delta_sum_seconds"] >= SAMPLE_SECONDS - 1.0
        ),
        "at_least_1500_frame_samples": timing["sample_count"] >= 1500,
        "frame_p95_ms_at_most_33_3": frame_p95 <= ACCEPTANCE_FRAME_P95_MS,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "failure_reasons": [name for name, passed in checks.items() if not passed],
        "gpu_sample_coverage": round(gpu_sample_coverage, 4),
    }


def _benchmark_completeness(
    frame_time_passed: bool,
    *,
    visible_count_available: bool,
    gpu_memory_available: bool,
    preset_recorded: bool,
) -> dict[str, Any]:
    checks = {
        "visible_count_available": visible_count_available,
        "gpu_memory_available": gpu_memory_available,
        "render_preset_recorded": preset_recorded,
    }
    return {
        "checks": checks,
        "complete": frame_time_passed and all(checks.values()),
        "failure_reasons": [name for name, passed in checks.items() if not passed],
    }


def _write_report_new(path: Path, report: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")


def _run_gameplay_benchmark(
    *,
    level_asset: str,
    level_file: Path,
    camera_label: str,
    levels: Any,
    editor: Any,
    actor_subsystem: Any,
    report_path: Path,
    command_log_path: Path,
    scene_counts: dict[str, Any],
) -> None:
    run_started = time.monotonic()
    vram_before = _sample_gpu_memory()
    state: dict[str, Any] = {
        "phase": "waiting_for_play_world",
        "done": False,
        "play_request_started": run_started,
        "warmup_started": None,
        "sample_started": None,
        "sample_deadline": None,
        "chart_stopped_at": None,
        "csv_wait_deadline": None,
        "csv_paths_before": set(),
        "game_world": None,
        "resolution_px": None,
        "preset": None,
        "timing": None,
    }
    tick_handle: Any = None
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    unreal.log(
        "CITY_BENCHMARK_START "
        f"mode=gameplay level={level_asset} camera={camera_label!r} "
        f"warmup_s={WARMUP_SECONDS:.0f} sample_s={SAMPLE_SECONDS:.0f}"
    )
    unreal.log(
        "CITY_BENCHMARK_GAMEPLAY_WAITING_FOR_PLAY "
        "Use in-process New Editor Window (PIE); Standalone separate-process is not controlled."
    )

    def stop_play_session() -> None:
        try:
            levels.editor_request_end_play()
        except Exception as exc:
            unreal.log_warning(f"CITY_BENCHMARK play-session cleanup warning: {exc}")

    def finish(error: str | None = None) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(tick_handle)
        except Exception as exc:
            unreal.log_warning(f"CITY_BENCHMARK callback cleanup warning: {exc}")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        if error:
            stop_play_session()
            unreal.log_error("CITY_BENCHMARK_FAILED " + error)
            return

        fps_chart_path = state.get("fps_chart_path")
        try:
            if not isinstance(fps_chart_path, Path):
                raise ValueError("FPS chart CSV was not found after StopFPSChart")
            timing = _parse_fps_chart_csv(fps_chart_path)
        except Exception as exc:
            unreal.log_error(f"CITY_BENCHMARK_FAILED FPS chart parse failed: {exc!r}")
            return

        sample_started = float(state["sample_started"])
        sample_deadline = float(state["sample_deadline"])
        chart_stopped_at = float(state["chart_stopped_at"])
        sample_actual_seconds = round(chart_stopped_at - sample_started, 3)
        frame_p95 = timing["series_ms"]["frame"]["p95"]
        renderer = _renderer_from_command_log(command_log_path)
        actual_1080p = state["resolution_px"] == [WIDTH, HEIGHT]
        frame_time_gate = _frame_time_gate(
            timing, renderer, state["resolution_px"], sample_actual_seconds
        )
        frame_time_passed = frame_time_gate["passed"]
        vram_after = _sample_gpu_memory()
        visible_count_available = False
        gpu_memory_available = bool(vram_before.get("available") and vram_after.get("available"))
        preset_cvars = (state["preset"] or {}).get("scalability_cvars", {})
        preset_recorded = any(value is not None for value in preset_cvars.values())
        completeness = _benchmark_completeness(
            frame_time_passed,
            visible_count_available=visible_count_available,
            gpu_memory_available=gpu_memory_available,
            preset_recorded=preset_recorded,
        )
        benchmark_complete = completeness["complete"]
        report = {
            "schema_version": "city_gameplay_fps_chart_benchmark.v1",
            "status": "completed",
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "level_asset": level_asset,
            "level_file": str(level_file),
            "camera_actor_label": camera_label,
            "play_mode": (
                "In-process New Editor Window PIE; separate-process Standalone Game is not "
                "controlled by the Editor Python callback"
            ),
            "capture": {
                "renderer": renderer,
                "kind": "game viewport",
                "resolution_px": state["resolution_px"],
                "expected_resolution_px": [WIDTH, HEIGHT],
                "resolution_verified": state["resolution_px"] is not None,
                "resolution_matches_acceptance": actual_1080p,
                "scene_capture_used": False,
                "render_preset": state["preset"],
            },
            "timing": {
                "metric_name": "ue_fps_chart_per_frame_frame_gt_rt_gpu",
                "metric_scope": (
                    "Per-frame Frame/GT/RT/GPU values written by UE 5.8 StopFPSChart "
                    "from the in-process PIE game world. Frame is UE's FPS-chart frame "
                    "delta, not Slate post-tick time."
                ),
                "not_editor_scene_capture_proxy": True,
                "warmup_target_seconds": WARMUP_SECONDS,
                "warmup_actual_seconds": round(sample_started - float(state["warmup_started"]), 3),
                "sample_target_seconds": SAMPLE_SECONDS,
                "sample_actual_seconds": sample_actual_seconds,
                "sample_finish_callback_lateness_seconds": round(
                    max(0.0, chart_stopped_at - sample_deadline), 3
                ),
                "fps_chart_csv_path": str(fps_chart_path),
                **timing,
            },
            "acceptance": {
                "frame_p95_target_ms": ACCEPTANCE_FRAME_P95_MS,
                "frame_time_gate": frame_time_gate,
                "benchmark_completeness": completeness,
                "passed": benchmark_complete,
            },
            "scene_counts": scene_counts,
            "visible_count": {
                "value": None,
                "source": None,
                "limitation": (
                    "The available Python API does not expose per-frame frustum-visible "
                    "primitive or instance counts. Scene/HISM totals are recorded separately."
                ),
            },
            "gpu_memory_nvidia_smi": {
                "before_warmup": vram_before,
                "after_sample": vram_after,
                "limitation": (
                    "nvidia-smi memory usage includes other GPU clients and is not "
                    "per-process VRAM unless the command reports process data."
                ),
            },
            "claim": (
                "UE FPS chart per-frame gameplay-world data. It is an acceptance pass only "
                "when the recorded viewport, D3D12/GPU samples, sample duration and P95 "
                "checks all pass."
            ),
            "no_map_or_asset_save_performed": True,
        }
        try:
            _write_report_new(report_path, report)
        except Exception as exc:
            unreal.log_error(f"CITY_BENCHMARK_FAILED report write failed: {exc!r}")
            return
        unreal.log(
            "CITY_BENCHMARK_GAMEPLAY_COMPLETE "
            + json.dumps(
                {
                    "report_path": str(report_path),
                    "fps_chart_csv_path": str(fps_chart_path),
                    "sample_count": timing["sample_count"],
                    "csv_time_span_seconds": timing["csv_time_span_seconds"],
                    "frame_p95_ms": frame_p95,
                    "gpu_sample_coverage": frame_time_gate["gpu_sample_coverage"],
                    "renderer": renderer["rhi"],
                    "acceptance": report["acceptance"],
                },
                sort_keys=True,
            )
        )

    def tick(_delta_seconds: float) -> None:
        if state["done"]:
            return
        now = time.monotonic()
        elapsed = now - run_started
        if elapsed > TIMEOUT_SECONDS:
            finish(f"timed out after {TIMEOUT_SECONDS:.0f}s in phase {state['phase']}")
            return

        if state["phase"] == "waiting_for_play_world":
            game_world = editor.get_game_world()
            if not game_world:
                if now - float(state["play_request_started"]) > PLAY_START_TIMEOUT_SECONDS:
                    finish(
                        "no in-process PIE world appeared; choose New Editor Window (PIE), "
                        "not Standalone Game or Simulate"
                    )
                return
            game_cameras = [
                actor
                for actor in unreal.GameplayStatics.get_all_actors_of_class(
                    game_world, unreal.CameraActor
                )
                if actor.get_actor_label() == camera_label
            ]
            player_controller = unreal.GameplayStatics.get_player_controller(game_world, 0)
            if not player_controller:
                finish("no PlayerController; this is not an in-process gameplay PIE session")
                return
            if len(game_cameras) != 1:
                finish(
                    f"expected one game-world CameraActor labeled {camera_label!r}, "
                    f"found {len(game_cameras)}"
                )
                return
            player_controller.set_view_target(game_cameras[0])
            unreal.SystemLibrary.execute_console_command(game_world, "StopFPSChart")
            state["game_world"] = game_world
            try:
                unreal.SystemLibrary.execute_console_command(
                    game_world, f"r.SetRes {WIDTH}x{HEIGHT}w"
                )
                unreal.SystemLibrary.execute_console_command(
                    game_world, "t.FPSChart.ExcludeIdleTime 0"
                )
            except Exception as exc:
                unreal.log_warning(f"CITY_BENCHMARK resolution request warning: {exc}")
            state["warmup_started"] = now
            state["phase"] = "warmup"
            unreal.log(
                "CITY_BENCHMARK_GAMEPLAY_WARMUP "
                f"viewport_request={WIDTH}x{HEIGHT} camera={camera_label!r}"
            )
            return

        if state["phase"] == "warmup":
            if now - float(state["warmup_started"]) >= WARMUP_SECONDS:
                game_world = state["game_world"]
                state["resolution_px"] = _viewport_size_px(game_world)
                state["preset"] = _preset_summary()
                state["csv_paths_before"] = _fps_chart_csv_paths()
                unreal.SystemLibrary.execute_console_command(
                    game_world, "StartFPSChart AIQCityBenchmark"
                )
                state["sample_started"] = now
                state["sample_deadline"] = now + SAMPLE_SECONDS
                state["phase"] = "sampling"
                unreal.log(
                    f"CITY_BENCHMARK_SAMPLE_START monotonic={now:.6f} "
                    f"duration_s={SAMPLE_SECONDS:.0f} "
                    f"viewport={state['resolution_px']}"
                )
            return

        if state["phase"] == "sampling":
            if now >= float(state["sample_deadline"]):
                game_world = state["game_world"]
                state["chart_stopped_at"] = now
                unreal.SystemLibrary.execute_console_command(game_world, "StopFPSChart")
                state["csv_wait_deadline"] = now + CHART_WRITE_TIMEOUT_SECONDS
                state["phase"] = "waiting_for_csv"
                stop_play_session()
                unreal.log("CITY_BENCHMARK_STOPFPSCHART_REQUESTED")
            return

        if state["phase"] == "waiting_for_csv":
            chart_path = _find_new_fps_chart_csv(state["csv_paths_before"])
            if chart_path is not None:
                state["fps_chart_path"] = chart_path
                finish()
            elif now >= float(state["csv_wait_deadline"]):
                finish("StopFPSChart did not write a new *-FPS-Windows.csv chart")

    try:
        levels.editor_request_begin_play()
    except Exception as exc:
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        raise RuntimeError(f"could not start the configured in-process PIE session: {exc}") from exc
    tick_handle = unreal.register_slate_post_tick_callback(tick)


def run() -> None:
    mode = os.environ.get("AIQ_CITY_BENCHMARK_MODE", "gameplay").strip().casefold()
    if mode not in {"gameplay", "proxy"}:
        raise ValueError("AIQ_CITY_BENCHMARK_MODE must be 'gameplay' or 'proxy'")
    level_asset = _level_asset_path(os.environ.get("AIQ_CITY_LEVEL_PATH", DEFAULT_LEVEL_ASSET))
    camera_label = os.environ.get("AIQ_CITY_CAMERA_LABEL", DEFAULT_CAMERA_LABEL).strip()
    if not camera_label:
        raise ValueError("AIQ_CITY_CAMERA_LABEL must be non-empty")
    default_report_path = (
        DEFAULT_GAMEPLAY_REPORT_PATH if mode == "gameplay" else DEFAULT_PROXY_REPORT_PATH
    )
    report_path = _env_path("AIQ_CITY_BENCHMARK_REPORT_PATH", default_report_path)
    command_log_path = _env_path("AIQ_CITY_BENCHMARK_LOG_PATH", DEFAULT_COMMAND_LOG_PATH)
    if report_path.exists():
        raise FileExistsError(f"refusing to overwrite benchmark report: {report_path}")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise RuntimeError(
            f"wrong Unreal project loaded: {project_dir}; expected canonical project {PROJECT_ROOT}"
        )
    level_file = (
        Path(unreal.Paths.project_content_dir()).resolve()
        / Path(*level_asset.removeprefix("/Game/").split("/"))
    ).with_suffix(".umap")
    if not level_file.is_file():
        raise FileNotFoundError(f"benchmark level file is missing: {level_file}")

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels or not editor or not actor_subsystem:
        raise RuntimeError("Unreal level, editor, or actor subsystem is unavailable")
    if not levels.load_level(level_asset):
        raise RuntimeError(f"Unreal failed to load benchmark level: {level_asset}")
    world = editor.get_editor_world()
    if not world:
        raise RuntimeError("Unreal editor world is unavailable after loading the benchmark level")

    actors = actor_subsystem.get_all_level_actors()
    cameras = [
        actor
        for actor in actors
        if actor.get_actor_label() == camera_label and isinstance(actor, unreal.CameraActor)
    ]
    if len(cameras) != 1:
        raise RuntimeError(
            f"expected one CameraActor labeled {camera_label!r}, found {len(cameras)}"
        )
    camera = cameras[0]
    count_summary = _scene_counts(actors)
    unreal.log(
        "CITY_BENCHMARK_START "
        f"mode={mode} level={level_asset} camera={camera_label!r} "
        f"script={Path(__file__).resolve()}"
    )

    if mode == "gameplay":
        _run_gameplay_benchmark(
            level_asset=level_asset,
            level_file=level_file,
            camera_label=camera_label,
            levels=levels,
            editor=editor,
            actor_subsystem=actor_subsystem,
            report_path=report_path,
            command_log_path=command_log_path,
            scene_counts=count_summary,
        )
        return

    capture = actor_subsystem.spawn_actor_from_class(
        unreal.SceneCapture2D, camera.get_actor_location(), camera.get_actor_rotation()
    )
    if not capture:
        raise RuntimeError("Unreal failed to spawn temporary SceneCapture2D")
    capture.set_actor_label("Temporary City Benchmark Capture")
    capture_component = capture.capture_component2d
    render_target = unreal.RenderingLibrary.create_render_target2d(
        world, WIDTH, HEIGHT, unreal.TextureRenderTargetFormat.RTF_RGBA8
    )
    if not render_target:
        actor_subsystem.destroy_actor(capture)
        raise RuntimeError(f"Unreal failed to allocate {WIDTH}x{HEIGHT} render target")
    capture_component.set_editor_property("texture_target", render_target)
    capture_component.set_editor_property(
        "capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    )
    capture_component.set_editor_property(
        "fov_angle", camera.camera_component.get_editor_property("field_of_view")
    )
    capture_component.set_editor_property("capture_every_frame", True)
    capture_component.set_editor_property("always_persist_rendering_state", True)

    vram_before = _sample_gpu_memory()
    run_started = time.monotonic()
    state: dict[str, Any] = {
        "phase": "warmup",
        "warmup_started": run_started,
        "sample_started": None,
        "sample_deadline": None,
        "tick_intervals_seconds": [],
        "invalid_tick_interval_count": 0,
        "done": False,
    }
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    unreal.log(
        "CITY_BENCHMARK_WARMUP "
        f"level={level_asset} camera={camera_label!r} "
        f"capture={WIDTH}x{HEIGHT} warmup_s={WARMUP_SECONDS:.0f} sample_s={SAMPLE_SECONDS:.0f}"
    )

    def finish(error: str | None = None) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(tick_handle)
        except Exception as exc:
            unreal.log_warning(f"CITY_BENCHMARK callback cleanup warning: {exc}")
        try:
            actor_subsystem.destroy_actor(capture)
        except Exception as exc:
            unreal.log_warning(f"CITY_BENCHMARK temporary capture cleanup warning: {exc}")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)

        if error:
            unreal.log_error("CITY_BENCHMARK_FAILED " + error)
            return

        intervals = state["tick_intervals_seconds"]
        if not intervals:
            unreal.log_error("CITY_BENCHMARK_FAILED no valid Slate tick intervals were collected")
            return
        sample_ended = time.monotonic()
        sample_started = float(state["sample_started"])
        sample_deadline = float(state["sample_deadline"])
        measured_until = min(sample_ended, sample_deadline)
        vram_after = _sample_gpu_memory()
        intervals_ms = [interval * 1000.0 for interval in intervals]
        report = {
            "schema_version": "styled_city_editor_capture_benchmark.v1",
            "status": "completed",
            "acceptance": {"applicable": False, "passed": False},
            "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
            "level_asset": level_asset,
            "level_file": str(level_file),
            "camera_actor_label": camera_label,
            "capture": {
                "renderer": _renderer_from_command_log(command_log_path),
                "kind": "temporary GPU SceneCapture2D",
                "resolution_px": [WIDTH, HEIGHT],
                "capture_every_frame": True,
                "capture_source": "SCS_FINAL_COLOR_LDR",
            },
            "timing": {
                "metric_name": "editor_scene_capture_tick_proxy",
                "metric_scope": (
                    "Unreal Editor Slate post-tick delta while a 1920x1080 "
                    "SceneCapture2D captures every frame"
                ),
                "not_a_gpu_frame_time": True,
                "not_gameplay_fps_acceptance": True,
                "warmup_target_seconds": WARMUP_SECONDS,
                "warmup_actual_seconds": round(sample_started - float(state["warmup_started"]), 3),
                "sample_target_seconds": SAMPLE_SECONDS,
                "sample_actual_seconds": round(measured_until - sample_started, 3),
                "sample_finish_callback_lateness_seconds": round(
                    max(0.0, sample_ended - sample_deadline), 3
                ),
                "tick_sample_count": len(intervals_ms),
                "frame_count_proxy": len(intervals_ms),
                "invalid_tick_interval_count": state["invalid_tick_interval_count"],
                "percentile_method": "nearest_rank",
                "sampled_tick_interval_sum_seconds": round(sum(intervals), 3),
                "interval_ms": {
                    "p50": round(_percentile_nearest_rank(intervals_ms, 0.50), 3),
                    "p95": round(_percentile_nearest_rank(intervals_ms, 0.95), 3),
                    "p99": round(_percentile_nearest_rank(intervals_ms, 0.99), 3),
                    "max": round(max(intervals_ms), 3),
                },
            },
            "scene_counts": count_summary,
            "gpu_memory_nvidia_smi": {
                "before_warmup": vram_before,
                "after_sample": vram_after,
                "limitation": (
                    "nvidia-smi memory usage includes other GPU clients and is not "
                    "per-process VRAM unless the command reports process data."
                ),
            },
            "claim": (
                "Editor + SceneCapture tick proxy for this saved level and camera. "
                "This is not validated GPU frame time, final gameplay FPS, or an acceptance result."
            ),
            "no_map_or_asset_save_performed": True,
        }
        try:
            _write_report_new(report_path, report)
        except Exception as exc:
            unreal.log_error(f"CITY_BENCHMARK_FAILED report write failed: {exc!r}")
            return
        unreal.log(
            "CITY_BENCHMARK_COMPLETE "
            + json.dumps(
                {
                    "report_path": str(report_path),
                    "tick_sample_count": len(intervals_ms),
                    "interval_ms": report["timing"]["interval_ms"],
                    "sample_actual_seconds": report["timing"]["sample_actual_seconds"],
                },
                sort_keys=True,
            )
        )

    def tick(delta_seconds: float) -> None:
        if state["done"]:
            return
        now = time.monotonic()
        elapsed = now - run_started
        if elapsed > TIMEOUT_SECONDS:
            finish(f"timed out after {TIMEOUT_SECONDS:.0f}s in phase {state['phase']}")
            return
        if state["phase"] == "warmup":
            if now - float(state["warmup_started"]) >= WARMUP_SECONDS:
                state["phase"] = "sampling"
                state["sample_started"] = now
                state["sample_deadline"] = now + SAMPLE_SECONDS
                unreal.log(
                    f"CITY_BENCHMARK_SAMPLE_START monotonic={now:.6f} "
                    f"duration_s={SAMPLE_SECONDS:.0f}"
                )
            return

        if now >= float(state["sample_deadline"]):
            finish()
            return
        try:
            interval = float(delta_seconds)
        except (TypeError, ValueError):
            interval = 0.0
        if math.isfinite(interval) and interval > 0:
            state["tick_intervals_seconds"].append(interval)
        else:
            state["invalid_tick_interval_count"] += 1

    tick_handle = unreal.register_slate_post_tick_callback(tick)


if __name__ == "__main__" and unreal is not None:
    try:
        run()
    except Exception as exc:
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.log_error(f"CITY_BENCHMARK_FAILED {type(exc).__name__}: {exc}")
        raise
