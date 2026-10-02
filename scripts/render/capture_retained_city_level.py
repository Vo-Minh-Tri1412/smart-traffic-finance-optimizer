"""Capture the saved retained SUMO city level with Unreal's GPU renderer.

Run with the canonical render_unreal/TrafficRender.uproject and UE 5.8:

    UnrealEditor-Cmd.exe <project> -ExecutePythonScript=<this-file>

This may change the material on the actor labeled ``Retained City Ground``.
The road geometry and saved camera stay untouched. The camera label defaults to
the overview camera and can be selected with ``AIQ_CITY_CAMERA_LABEL``. Set
``AIQ_CITY_HIDE_ACTOR_LABEL`` to exclude one actor from this temporary capture;
the actor remains visible in the saved level and other captures. The
SceneCapture2D actor is temporary and is not saved into the level.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = (ROOT / "render_unreal").resolve()
DEFAULT_LEVEL_ASSET = "/Game/City/District7_OSM/District7_OSM"
LEVEL_ASSET = os.environ.get("AIQ_CITY_LEVEL_PATH", DEFAULT_LEVEL_ASSET)
CAMERA_LABEL = os.environ.get("AIQ_CITY_CAMERA_LABEL", "Retained City Overview Camera")
HIDE_ACTOR_LABEL = os.environ.get("AIQ_CITY_HIDE_ACTOR_LABEL", "").strip()
ROAD_MATERIAL_ASSET = os.environ.get(
    "AIQ_CITY_ROAD_MATERIAL_ASSET", "/Game/Demo092/Materials/Asphalt"
)
GROUND_MATERIAL_ASSET = os.environ.get(
    "AIQ_CITY_GROUND_MATERIAL_ASSET", "/Game/Demo092/Materials/Concrete"
)
OUTPUT_DIR = ROOT / "artifacts" / "tmp" / "city_pipeline"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default.resolve()
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


SCREENSHOT_PATH = _env_path("AIQ_CITY_SCREENSHOT_PATH", OUTPUT_DIR / "city_overview.png")
REPORT_PATH = _env_path("AIQ_CITY_CAPTURE_REPORT_PATH", OUTPUT_DIR / "city_capture.json")
OUTPUT_DIR = SCREENSHOT_PATH.parent
WIDTH = 1920
HEIGHT = 1080
WARMUP_FRAMES = 180
WARMUP_SECONDS = 35.0
CAPTURE_SETTLE_FRAMES = 20
TIMEOUT_SECONDS = 900.0
OUTPUT_LOCKS: list[Path] = []


def _actor_label(actor: Any) -> str:
    return actor.get_actor_label()


def _project_preflight() -> Path:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    if project_dir != PROJECT_ROOT:
        raise RuntimeError(
            f"wrong Unreal project loaded: {project_dir}; expected canonical project {PROJECT_ROOT}"
        )
    level_value = LEVEL_ASSET.strip().rstrip("/")
    if not level_value.startswith("/Game/") or level_value.endswith(".umap"):
        raise ValueError("AIQ_CITY_LEVEL_PATH must be a /Game package path without .umap")
    level_parts = level_value.removeprefix("/Game/").split("/")
    if not level_parts or any(not re.fullmatch(r"[A-Za-z0-9_]+", part) for part in level_parts):
        raise ValueError("AIQ_CITY_LEVEL_PATH contains an invalid Unreal package name")
    level_file = Path(unreal.Paths.project_content_dir()).resolve() / Path(
        *level_parts
    ).with_suffix(".umap")
    if not level_file.is_file():
        raise FileNotFoundError(f"saved retained city level is missing: {level_file}")
    if SCREENSHOT_PATH.exists():
        raise FileExistsError(f"refusing to overwrite screenshot: {SCREENSHOT_PATH}")
    if REPORT_PATH.exists():
        raise FileExistsError(f"refusing to overwrite QA report: {REPORT_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _reserve_output_paths()
    return level_file


def _reserve_output_paths() -> None:
    if SCREENSHOT_PATH == REPORT_PATH:
        raise ValueError("screenshot and capture report must use different paths")
    try:
        for path in (SCREENSHOT_PATH, REPORT_PATH):
            lock = path.with_name(f".{path.name}.city-capture.lock")
            with lock.open("x", encoding="utf-8") as reservation:
                reservation.write("reserved by capture_retained_city_level.py\n")
            OUTPUT_LOCKS.append(lock)
    except Exception:
        _release_output_paths()
        raise


def _release_output_paths() -> None:
    for lock in OUTPUT_LOCKS:
        try:
            lock.unlink(missing_ok=True)
        except OSError as exc:
            unreal.log_warning(f"Could not remove capture reservation {lock}: {exc}")
    OUTPUT_LOCKS.clear()


def _find_required_actors(actors: list[Any]) -> tuple[Any, Any, Any]:
    geometry_class = unreal.load_class(
        None, "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
    )
    if not geometry_class:
        raise RuntimeError("TrafficSumoGeometryActor class is not loaded")

    geometry = [
        actor
        for actor in actors
        if _actor_label(actor) == "Retained SUMO Road Geometry"
        and actor.get_class().get_path_name()
        == "/Script/TrafficRenderRuntime.TrafficSumoGeometryActor"
    ]
    cameras = [
        actor
        for actor in actors
        if _actor_label(actor) == CAMERA_LABEL and isinstance(actor, unreal.CameraActor)
    ]
    grounds = [
        actor
        for actor in actors
        if _actor_label(actor) == "Retained City Ground"
        and isinstance(actor, unreal.StaticMeshActor)
    ]
    for name, matches in (
        ("Retained SUMO Road Geometry", geometry),
        (CAMERA_LABEL, cameras),
        ("Retained City Ground", grounds),
    ):
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} actor, found {len(matches)}")
    return geometry[0], cameras[0], grounds[0]


def _save_ground_material(levels: Any, ground: Any, level_file: Path) -> str:
    component = ground.static_mesh_component
    if not component or component.get_num_materials() < 1:
        raise RuntimeError("Retained City Ground has no material slot 0")
    if GROUND_MATERIAL_ASSET.strip().lower() in {"preserve", "keep", "none"}:
        current = component.get_material(0)
        if not current:
            raise RuntimeError("Retained City Ground has no assigned material to preserve")
        return current.get_path_name()

    material = unreal.load_asset(GROUND_MATERIAL_ASSET)
    if not material:
        raise RuntimeError(f"ground material asset is missing: {GROUND_MATERIAL_ASSET}")
    component.set_material(0, material)
    assigned = component.get_material(0)
    assigned_path = assigned.get_path_name() if assigned else ""
    assigned_asset_path = assigned_path.split(".", 1)[0]
    if assigned_asset_path != GROUND_MATERIAL_ASSET:
        raise RuntimeError(
            f"failed to assign ground material: expected {GROUND_MATERIAL_ASSET}, "
            f"got {assigned_path}"
        )

    save_result = levels.save_current_level()
    if save_result is False or not level_file.is_file():
        raise RuntimeError(f"Unreal did not save the retained city level: {level_file}")
    return assigned_path


def _geometry_qa(geometry: Any) -> dict[str, Any]:
    summary_text = geometry.get_build_summary_json()
    if not isinstance(summary_text, str):
        raise RuntimeError("geometry actor returned no build summary")
    summary = json.loads(summary_text)
    tile_count = int(summary.get("rendered_tile_count", 0))
    tile_size = float(summary.get("tile_size_meters", 0.0))
    skipped = int(summary.get("skipped_degenerate_segment_count", 0))
    rendered_segments = int(summary.get("rendered_segment_count", 0))
    if tile_count <= 0:
        # Keep the default capture usable for the preserved pre-tiling level.
        return {
            "tile_qa_available": False,
            "rendered_segment_count": rendered_segments,
        }
    mesh_components = geometry.get_components_by_class(unreal.ProceduralMeshComponent)
    if tile_size <= 0 or skipped < 0:
        raise RuntimeError(f"geometry actor returned invalid tile QA: {summary!r}")
    if len(mesh_components) != tile_count + 1:
        raise RuntimeError(
            "geometry mesh component count does not match rendered tile count: "
            f"components={len(mesh_components)}, tiles={tile_count}"
        )
    expected_material_path = ROAD_MATERIAL_ASSET
    for component in mesh_components:
        material = component.get_material(0)
        material_path = material.get_path_name().split(".", 1)[0] if material else ""
        if material_path != expected_material_path:
            raise RuntimeError(
                "a road mesh component has the wrong material: "
                f"expected {expected_material_path}, got {material_path!r}"
            )
    return {
        "tile_qa_available": True,
        "rendered_tile_count": tile_count,
        "tile_size_meters": tile_size,
        "skipped_degenerate_segment_count": skipped,
        "rendered_segment_count": rendered_segments,
        "road_material_asset": expected_material_path,
        "road_mesh_component_count": len(mesh_components),
    }


def _capture_hidden_actor_qa(actors: list[Any]) -> tuple[Any | None, dict[str, Any] | None]:
    if not HIDE_ACTOR_LABEL:
        return None, None
    matches = [actor for actor in actors if _actor_label(actor) == HIDE_ACTOR_LABEL]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one capture-only hidden actor {HIDE_ACTOR_LABEL!r}, found {len(matches)}"
        )
    actor = matches[0]
    cube_components = []
    for component in actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        mesh_path = mesh.get_path_name().split(".", 1)[0] if mesh else ""
        if mesh_path == "/Engine/BasicShapes/Cube":
            cube_components.append(component)
    return actor, {
        "actor_label": HIDE_ACTOR_LABEL,
        "capture_only": True,
        "saved_level_visibility_changed": False,
        "exclusion_method": "SceneCaptureComponent2D.HideActorComponents",
        "cube_hism_component_count": len(cube_components),
        "cube_instance_count": sum(
            int(component.get_instance_count()) for component in cube_components
        ),
        "reason": (
            "Exclude map Cube visual placeholders from this still while keeping them "
            "in the saved level."
        ),
    }


def _write_report(report: dict[str, Any]) -> None:
    with REPORT_PATH.open("x", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")


def run() -> None:
    level_file = _project_preflight()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels or not editor or not actor_subsystem:
        raise RuntimeError("Unreal level, editor, or actor subsystem is unavailable")
    if not levels.load_level(LEVEL_ASSET):
        raise RuntimeError(f"Unreal failed to load saved level: {LEVEL_ASSET}")

    world = editor.get_editor_world()
    if not world:
        raise RuntimeError("Unreal editor world is unavailable after loading the saved level")
    all_actors = actor_subsystem.get_all_level_actors()
    geometry, camera, ground = _find_required_actors(all_actors)
    hidden_actor, hidden_actor_qa = _capture_hidden_actor_qa(all_actors)
    geometry_qa = _geometry_qa(geometry)
    ground_material_path = _save_ground_material(levels, ground, level_file)

    camera_location = camera.get_actor_location()
    camera_rotation = camera.get_actor_rotation()
    camera_fov = camera.camera_component.get_editor_property("field_of_view")
    capture = actor_subsystem.spawn_actor_from_class(
        unreal.SceneCapture2D, camera_location, camera_rotation
    )
    if not capture:
        raise RuntimeError("Unreal failed to spawn temporary SceneCapture2D")
    capture.set_actor_label("Temporary Retained City GPU Capture")
    capture_component = capture.capture_component2d
    render_target = unreal.RenderingLibrary.create_render_target2d(
        world, WIDTH, HEIGHT, unreal.TextureRenderTargetFormat.RTF_RGBA8
    )
    if not render_target:
        raise RuntimeError(f"Unreal failed to allocate {WIDTH}x{HEIGHT} render target")
    capture_component.set_editor_property("texture_target", render_target)
    capture_component.set_editor_property(
        "capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    )
    capture_component.set_editor_property("fov_angle", camera_fov)
    capture_component.set_editor_property("capture_every_frame", True)
    capture_component.set_editor_property("always_persist_rendering_state", True)
    if hidden_actor:
        hide_actor_components = getattr(capture_component, "hide_actor_components", None)
        if not callable(hide_actor_components):
            raise RuntimeError("SceneCapture2D does not expose HideActorComponents")
        hide_actor_components(hidden_actor)

    for command in (
        "r.ScreenPercentage 100",
        "r.ShadowQuality 4",
        "r.AmbientOcclusionLevels 2",
        "r.Streaming.PoolSize 1400",
    ):
        unreal.SystemLibrary.execute_console_command(world, command)

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    state: dict[str, Any] = {
        "frames": 0,
        "capture_frame": None,
        "started_at": time.monotonic(),
        "last_wait_log": 0,
        "done": False,
    }
    unreal.log(
        "CITY_CAPTURE_READY waiting for GPU warmup; "
        f"saved_level={LEVEL_ASSET} resolution={WIDTH}x{HEIGHT}"
    )

    def finish(message: str, error: bool = False) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(tick_handle)
        except Exception as exc:
            unreal.log_warning(f"CITY_CAPTURE callback cleanup warning: {exc}")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        _release_output_paths()
        if error:
            unreal.log_error("CITY_CAPTURE_FAILED " + message)
        else:
            unreal.log("CITY_CAPTURE_COMPLETE " + message)

    def tick(_delta_seconds: float) -> None:
        if state["done"]:
            return
        state["frames"] += 1
        elapsed = time.monotonic() - state["started_at"]
        if elapsed > TIMEOUT_SECONDS:
            finish(
                f"timed out after {TIMEOUT_SECONDS:.0f}s; "
                f"frames={state['frames']} captured={state['capture_frame'] is not None}",
                error=True,
            )
            return
        if state["capture_frame"] is None:
            if state["frames"] >= WARMUP_FRAMES and elapsed >= WARMUP_SECONDS:
                try:
                    unreal.AutomationLibrary.finish_loading_before_screenshot()
                    capture_component.capture_scene()
                    state["capture_frame"] = state["frames"]
                    unreal.log(
                        f"CITY_CAPTURE_GPU_FRAME frame={state['frames']} elapsed={elapsed:.1f}s"
                    )
                except Exception as exc:
                    finish(f"SceneCapture2D capture_scene failed: {exc!r}", error=True)
            elif elapsed - state["last_wait_log"] >= 30:
                state["last_wait_log"] = int(elapsed // 30) * 30
                unreal.log(f"CITY_CAPTURE_WARMING frames={state['frames']} elapsed={elapsed:.1f}s")
            return

        if state["frames"] < state["capture_frame"] + CAPTURE_SETTLE_FRAMES:
            return
        try:
            unreal.RenderingLibrary.export_render_target(
                world, render_target, str(SCREENSHOT_PATH.parent), SCREENSHOT_PATH.name
            )
            if not SCREENSHOT_PATH.is_file() or SCREENSHOT_PATH.stat().st_size <= 0:
                raise RuntimeError(
                    f"render target export did not create a non-empty image: {SCREENSHOT_PATH}"
                )
            report = {
                "schema_version": "retained_city_gpu_capture.v1",
                "status": "captured",
                "renderer": "Unreal Engine 5.8 GPU SceneCapture2D",
                "project_file": str(PROJECT_ROOT / "TrafficRender.uproject"),
                "saved_level_asset": LEVEL_ASSET,
                "saved_level_file": str(level_file),
                "geometry_qa": geometry_qa,
                "geometry_actor": _actor_label(geometry),
                "camera_actor": _actor_label(camera),
                "camera_location_cm": [
                    camera_location.x,
                    camera_location.y,
                    camera_location.z,
                ],
                "camera_rotation_degrees": [
                    camera_rotation.roll,
                    camera_rotation.pitch,
                    camera_rotation.yaw,
                ],
                "camera_fov_degrees": camera_fov,
                "ground_actor": _actor_label(ground),
                "ground_material_asset": ground_material_path,
                "capture_only_hidden_actor": hidden_actor_qa,
                "screenshot_file": str(SCREENSHOT_PATH),
                "resolution_px": [WIDTH, HEIGHT],
                "warmup_frames": state["frames"],
                "warmup_seconds": round(elapsed, 2),
                "claim": (
                    "GPU capture of the saved retained SUMO city level using the selected camera; "
                    "illustrative semantic placements only, with no demand, vehicle replay, "
                    "or traffic-performance claim."
                ),
            }
            _write_report(report)
            finish(str(SCREENSHOT_PATH))
        except Exception as exc:
            finish(f"export or QA report failed: {exc!r}", error=True)

    tick_handle = unreal.register_slate_post_tick_callback(tick)


try:
    run()
except Exception as exc:
    _release_output_paths()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    unreal.log_error(f"CITY_CAPTURE_FAILED {type(exc).__name__}: {exc}")
    raise
