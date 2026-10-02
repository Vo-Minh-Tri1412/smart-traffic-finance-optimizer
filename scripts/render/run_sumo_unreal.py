"""Launch live SUMO traffic on the retained map and visualize it in Unreal.

SUMO is the only simulation authority. The TCP bridge sends vehicle_trace.v2
poses and SUMO signal states after every TraCI step; Unreal renders those states.
The existing random route file is a visualization input, not calibrated demand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
import subprocess
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "render_unreal" / "TrafficRender.uproject"
DEFAULT_GEOMETRY = ROOT / "render_unreal/CitySources/district7_geometry_manifest.v1.json"
DEFAULT_ROUTES = (
    ROOT / "simulation_projects/map_intake/02_prepared_sources/"
    "district7_osm_seed_20260702/district7_random.rou.xml"
)
MATERIAL_NAMES = ("Vehicle", "Red", "Yellow", "Green", "Dark", "Road", "Ground", "CarPalette")


def encode_packet(packet: dict[str, Any]) -> bytes:
    return (json.dumps(packet, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def unreal_object_path(value: str) -> str:
    """Accept a package path or the Editor's Copy Reference object path."""
    if "'" in value:
        value = value.split("'")[1]
    if value.startswith("/Game/") and "." not in value.rsplit("/", 1)[-1]:
        value += "." + value.rsplit("/", 1)[-1]
    return value


def wait_for_ready(client: socket.socket, output: Path) -> None:
    client.settimeout(1)
    deadline = time.monotonic() + 180
    received = bytearray()
    while time.monotonic() < deadline:
        report_path = output / "unreal_live_report.json"
        if report_path.is_file():
            with suppress(OSError, ValueError):
                report = json.loads(report_path.read_text(encoding="utf-8-sig"))
                if report.get("status") == "failed":
                    raise RuntimeError(f"Unreal: {report.get('error')}")
        try:
            data = client.recv(128)
        except TimeoutError:
            continue
        if not data:
            raise ConnectionError("Unreal closed the bridge before scene readiness")
        received.extend(data)
        if b"\n" in received:
            if bytes(received) != b"ready\n":
                raise RuntimeError("Invalid Unreal scene-readiness response")
            return
    raise TimeoutError("Unreal scene initialization exceeded 180 seconds")


def load_geometry(path: Path) -> tuple[dict[str, Any], Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "geometry_manifest.v1":
        raise ValueError("The geometry manifest must use geometry_manifest.v1")
    net = Path(data["net_xml"])
    if not net.is_absolute():
        net = path.parent / net
    net = net.resolve(strict=True)
    actual_hash = hashlib.sha256(net.read_bytes()).hexdigest()
    declared = data.get("source_net_sha256")
    if declared and actual_hash != declared:
        raise ValueError("The retained SUMO net no longer matches its geometry manifest")
    data["net_xml"] = str(net)
    data["source_net_sha256"] = actual_hash
    return data, net


def traffic_light_geometry(connection: Any) -> tuple[list[dict[str, Any]], dict[str, float]]:
    heads: list[dict[str, Any]] = []
    focus = {"x": 0.0, "y": 0.0}
    for tls_id in sorted(connection.trafficlight.getIDList()):
        seen: set[tuple[int, str]] = set()
        lane_offsets: dict[str, int] = {}
        for index, links in enumerate(connection.trafficlight.getControlledLinks(tls_id)):
            for incoming, _outgoing, _via in links:
                if (index, incoming) in seen:
                    continue
                seen.add((index, incoming))
                shape = connection.lane.getShape(incoming)
                if len(shape) < 2:
                    raise ValueError(f"Signal lane has no usable geometry: {incoming}")
                x, y = shape[-1]
                dx, dy = x - shape[-2][0], y - shape[-2][1]
                length = math.hypot(dx, dy)
                ordinal = lane_offsets.get(incoming, 0)
                lane_offsets[incoming] = lane_offsets.get(incoming, 0) + 1
                heads.append(
                    {
                        "traffic_light_id": tls_id,
                        "link_index": index,
                        "lane_id": incoming,
                        "x": x,
                        "y": y,
                        "forward_x": dx / length if length else 0.0,
                        "forward_y": dy / length if length else 1.0,
                        "lane_width_m": connection.lane.getWidth(incoming),
                        "lane_head_ordinal": ordinal,
                    }
                )
                if len(heads) == 1:
                    focus = {"x": x, "y": y}
    return heads, focus


def snapshot(connection: Any, timestep: int) -> dict[str, Any]:
    vehicles = []
    for vehicle_id in sorted(connection.vehicle.getIDList()):
        x, y, z = connection.vehicle.getPosition3D(vehicle_id)
        vehicles.append(
            {
                "vehicle_id": vehicle_id,
                "vehicle_type": connection.vehicle.getTypeID(vehicle_id),
                "x": x,
                "y": y,
                "elevation_m": z,
                "speed": connection.vehicle.getSpeed(vehicle_id),
                "angle": connection.vehicle.getAngle(vehicle_id),
                "lane_id": connection.vehicle.getLaneID(vehicle_id),
                "road_id": connection.vehicle.getRoadID(vehicle_id),
                "length_m": connection.vehicle.getLength(vehicle_id),
                "width_m": connection.vehicle.getWidth(vehicle_id),
                "height_m": connection.vehicle.getHeight(vehicle_id),
                "ground_clearance_m": 0.0,
                "pos_lat_m": connection.vehicle.getLateralLanePosition(vehicle_id),
                "reference_point": "front_bumper_center",
                "elevation_source": "sumo_position3d",
            }
        )
    now = connection.simulation.getTime()
    lights = [
        {
            "traffic_light_id": tls_id,
            "phase_index": connection.trafficlight.getPhase(tls_id),
            "state": connection.trafficlight.getRedYellowGreenState(tls_id),
            "remaining_seconds": max(0.0, connection.trafficlight.getNextSwitch(tls_id) - now),
        }
        for tls_id in sorted(connection.trafficlight.getIDList())
    ]
    frame: dict[str, Any] = {
        "packet_type": "frame",
        "schema_version": "vehicle_trace.v2",
        "timestep": timestep,
        "time_seconds": now,
        "district_id": "district7_osm_seed_20260702",
        "scenario_id": "live_visualization",
        "controller_id": "fixed_time",
        "engine_id": "sumo",
        "vehicles": vehicles,
        "traffic_lights": lights,
    }
    if vehicles:
        upcoming = connection.vehicle.getNextTLS(vehicles[0]["vehicle_id"])
        if upcoming and upcoming[0][2] < 35:
            tls_id, link_index, distance, _state = upcoming[0]
            links = connection.trafficlight.getControlledLinks(tls_id)[link_index]
            if links:
                x, y = connection.lane.getShape(links[0][0])[-1]
                frame["camera_junction"] = {
                    "traffic_light_id": tls_id,
                    "x": x,
                    "y": y,
                    "distance_m": distance,
                }
    return frame


def serve_simulation(
    listener: socket.socket,
    *,
    geometry_path: Path,
    routes: Path,
    output: Path,
    duration: float,
    step_length: float,
    speed: float,
) -> dict[str, Any]:
    import sumolib
    import traci

    geometry, net = load_geometry(geometry_path)
    routes = routes.resolve(strict=True)
    frozen_geometry = output / "geometry_manifest.json"
    frozen_geometry.write_text(json.dumps(geometry, indent=2), encoding="utf-8")
    run_id = output.name
    report: dict[str, Any] = {
        "schema_version": "sumo_unreal_live_producer.v1",
        "run_id": run_id,
        "net_xml": str(net),
        "source_net_sha256": geometry["source_net_sha256"],
        "routes": str(routes),
        "routes_sha256": hashlib.sha256(routes.read_bytes()).hexdigest(),
        "duration_seconds": duration,
        "step_length_seconds": step_length,
        "playback_speed": speed,
        "status": "waiting_for_unreal",
        "frames_sent": 0,
        "input_scope": "existing random routes for integration visualization",
    }
    report_path = output / "sumo_live_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    listener.settimeout(180)
    connection = None
    with listener.accept()[0] as client, (output / "sumo.stdout.log").open("w") as log:
        client.settimeout(180)
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        label = f"live-{uuid.uuid4().hex}"
        try:
            traci.start(
                [
                    sumolib.checkBinary("sumo"),
                    "-n",
                    str(net),
                    "-r",
                    str(routes),
                    "--step-length",
                    str(step_length),
                    "--seed",
                    "11",
                    "--no-step-log",
                    "true",
                    "--quit-on-end",
                    "true",
                ],
                label=label,
                doSwitch=False,
                stdout=log,
            )
            connection = traci.getConnection(label)
            heads, focus = traffic_light_geometry(connection)
            client.sendall(
                encode_packet(
                    {
                        "packet_type": "hello",
                        "schema_version": "sumo_live_bridge.v1",
                        "run_id": run_id,
                        "geometry_manifest": str(frozen_geometry),
                        "traffic_light_heads": heads,
                        "camera_focus": focus,
                    }
                )
            )
            with client.makefile("rb"):
                wait_for_ready(client, output)
                client.settimeout(15)
                report["status"] = "live"
                report["traffic_light_head_count"] = len(heads)
                start = time.monotonic()
                with (output / "live_frames.jsonl").open("x", encoding="utf-8") as trace:
                    last: dict[str, Any] = {}
                    for timestep in range(math.ceil(duration / step_length)):
                        if speed:
                            deadline = start + timestep * step_length / speed
                            delay = deadline - time.monotonic()
                            if delay > 0:
                                time.sleep(delay)
                        connection.simulationStep()
                        last = snapshot(connection, timestep)
                        wire = encode_packet(last)
                        client.sendall(wire)
                        trace.write(wire.decode("utf-8"))
                        report["frames_sent"] += 1
                        if timestep % 10 == 0:
                            report["sumo_time_seconds"] = last["time_seconds"]
                            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    client.sendall(encode_packet({"packet_type": "complete", "run_id": run_id}))
                    report["status"] = "complete"
                    report["sumo_time_seconds"] = last["time_seconds"]
                    report["last_sample_vehicle"] = next(iter(last["vehicles"]), None)
                    report["wall_seconds"] = round(time.monotonic() - start, 3)
                    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    time.sleep(0.5)
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            with suppress(OSError):
                client.sendall(encode_packet({"packet_type": "error", "message": str(exc)}))
            raise
        finally:
            if connection is not None:
                connection.close()
    return report


def prepare_unreal(engine: Path, output: Path) -> Path:
    editor = engine / "Engine/Binaries/Win64/UnrealEditor.exe"
    if not editor.is_file():
        raise FileNotFoundError(f"Unreal Editor not found: {editor}; use --engine-root")
    sources = PROJECT.parent / "Plugins/TrafficRenderBridge/Source"
    binary = (
        PROJECT.parent / "Plugins/TrafficRenderBridge/Binaries/Win64/"
        "UnrealEditor-TrafficRenderRuntime.dll"
    )
    newest_source = max(p.stat().st_mtime for p in sources.rglob("*") if p.is_file())
    if not binary.exists() or binary.stat().st_mtime < newest_source:
        print("Building the native live bridge...", flush=True)
        subprocess.run(
            [
                str(engine / "Engine/Build/BatchFiles/Build.bat"),
                "TrafficRenderEditor",
                "Win64",
                "Development",
                f"-Project={PROJECT}",
                "-WaitMutex",
                "-NoHotReloadFromIDE",
                "-MaxParallelActions=2",
            ],
            check=True,
            cwd=ROOT,
        )
    assets = PROJECT.parent / "Content/LiveTraffic/Materials"
    profiles = PROJECT.parent / "Content/LiveTraffic/Profiles"
    complete = all((assets / f"M_{name}.uasset").exists() for name in MATERIAL_NAMES)
    complete = complete and (profiles / "LiveScene.uasset").exists()
    complete = (
        complete
        and (PROJECT.parent / "Content/LiveTraffic/Blueprints/BP_LiveController.uasset").exists()
    )
    if not complete:
        print("Preparing live renderer materials...", flush=True)
        with (output / "bootstrap.log").open("w") as log:
            subprocess.run(
                [
                    str(editor.with_name("UnrealEditor-Cmd.exe")),
                    str(PROJECT),
                    "-unattended",
                    "-NullRHI",
                    f"-ExecutePythonScript={ROOT / 'scripts/render/bootstrap_live_traffic.py'}",
                    "-nosplash",
                ],
                check=True,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if not all((assets / f"M_{name}.uasset").exists() for name in MATERIAL_NAMES):
            raise RuntimeError(
                f"Live material bootstrap incomplete; inspect {output / 'bootstrap.log'}",
            )
    return editor


def verify_output(output: Path, producer: dict[str, Any], geometry: dict[str, Any]) -> None:
    deadline = time.monotonic() + 20
    path = output / "unreal_live_report.json"
    consumer: dict[str, Any] = {}
    while time.monotonic() < deadline:
        if path.exists():
            with suppress(ValueError, OSError):
                consumer = json.loads(path.read_text(encoding="utf-8-sig"))
            if consumer.get("status") in {"complete", "failed"}:
                break
        time.sleep(0.2)
    checks = {
        "unreal_completed": consumer.get("status") == "complete",
        "same_run": consumer.get("run_id") == producer["run_id"],
        "all_frames_received": consumer.get("frames_received") == producer["frames_sent"],
        "sumo_time_matches": abs(
            consumer.get("sumo_time_seconds", -1) - producer["sumo_time_seconds"],
        )
        < 0.0001,
        "vehicles_moved": consumer.get("vehicle_pose_changes", 0) > 0,
        "signals_changed": consumer.get("traffic_light_state_changes", 0) > 0,
        "retained_map_rendered": consumer.get("rendered_lane_count", 0) >= geometry["lane_count"],
        "all_signal_heads_rendered": (
            consumer.get("traffic_light_head_count") == producer["traffic_light_head_count"]
        ),
        "screenshots_saved": all(
            (output / name).is_file() for name in ("live_02s.png", "live_06s.png")
        )
        or len(list(output.glob("frame_*.png"))) >= 10,
    }
    sample = producer.get("last_sample_vehicle")
    observed = consumer.get("sample_vehicle", {})
    if sample:
        origin = geometry["local_origin"]
        angle = math.radians(sample["angle"])
        expected_x = (sample["x"] - math.sin(angle) * sample["length_m"] / 2 - origin["x"]) * 100
        expected_y = (sample["y"] - math.cos(angle) * sample["length_m"] / 2 - origin["y"]) * 100
        checks["rendered_pose_matches_sumo"] = (
            observed.get("vehicle_id") == sample["vehicle_id"]
            and abs(observed.get("unreal_x_cm", math.inf) - expected_x) < 0.1
            and abs(observed.get("unreal_y_cm", math.inf) - expected_y) < 0.1
        )
        if observed.get("template_length_m", 0) > 0:
            ratios = [
                observed[f"visual_{axis}_m"] / observed[f"template_{axis}_m"]
                for axis in ("length", "width", "height")
            ]
            checks["visual_aspect_ratio_preserved"] = max(ratios) - min(ratios) < 0.0001
            checks["visual_inside_physical_proxy"] = all(
                observed[f"visual_{axis}_m"] <= sample[f"{axis}_m"] + 0.001
                for axis in ("length", "width", "height")
            )
    if "building_parts" in consumer:
        checks["urban_buildings_present"] = consumer["building_parts"] > 0
        checks["lane_markings_present"] = consumer.get("lane_marking_segments", 0) > 0
        checks["sidewalks_present"] = consumer.get("sidewalk_segments", 0) > 0
        checks["greenery_present"] = consumer.get("tree_count", 0) > 0
    verdict = {"passed": all(checks.values()), "checks": checks, "unreal": consumer}
    (output / "verification.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print(json.dumps(verdict, indent=2), flush=True)
    if not verdict["passed"]:
        raise RuntimeError(f"Live verification failed; inspect {output}")


def encode_capture(output: Path) -> None:
    frames = sorted(output.glob("frame_*.png"))
    if len(frames) < 2:
        raise RuntimeError("Recording did not produce enough viewport frames")
    # Readback can miss the requested sampling cadence. Preserve actual capture timing.
    timing = [p.stat().st_mtime for p in frames]
    lines = ["ffconcat version 1.0"]
    for index, frame in enumerate(frames):
        lines.append(f"file '{frame.name}'")
        if index + 1 < len(frames):
            lines.append(f"duration {max(0.001, timing[index + 1] - timing[index]):.6f}")
    lines.append(f"file '{frames[-1].name}'")
    concat = output / "capture_timing.ffconcat"
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-fps_mode",
            "vfr",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            "-y",
            str(output / "live_simulation.mp4"),
        ],
        check=True,
    )
    (output / "capture_timing.json").write_text(
        json.dumps(
            {
                "frame_count": len(frames),
                "wall_span_seconds": timing[-1] - timing[0],
                "timing_source": "GPU screenshot file write timestamps",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    parser.add_argument("--visual-profile", help="Optional scene Data Asset override")
    parser.add_argument(
        "--controller-class",
        default="/Game/LiveTraffic/Blueprints/BP_LiveController.BP_LiveController_C",
        help="Blueprint subclass path for the live actor",
    )
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=Path(
            os.environ.get("UNREAL_ENGINE_ROOT", "D:/Starter Game/UE_5.8"),
        ),
    )
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--step-length", type=float, default=0.1)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Save two GPU screenshots and verify the live run",
    )
    parser.add_argument(
        "--record-seconds",
        type=float,
        default=0,
        help="Record the actual game viewport at 10 FPS to a local MP4 (requires ffmpeg)",
    )
    args = parser.parse_args()
    if not all(math.isfinite(v) and v > 0 for v in (args.duration, args.step_length, args.speed)):
        parser.error("duration, step-length and speed must be finite and positive")
    if args.verify and args.duration < 8:
        parser.error("--verify requires at least 8 seconds for its GPU captures")
    if not math.isfinite(args.record_seconds) or args.record_seconds < 0:
        parser.error("record-seconds must be finite and non-negative")
    geometry, _net = load_geometry(args.geometry.resolve(strict=True))
    args.routes = args.routes.resolve(strict=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = ROOT / "artifacts/unreal_live" / run_id
    output.mkdir(parents=True, exist_ok=False)
    editor = prepare_unreal(args.engine_root, output)
    binary = PROJECT.parent / (
        "Plugins/TrafficRenderBridge/Binaries/Win64/UnrealEditor-TrafficRenderRuntime.dll"
    )
    (output / "native_binary.json").write_text(
        json.dumps(
            {
                "path": str(binary),
                "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "mtime_ns": binary.stat().st_mtime_ns,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        command = [
            str(editor),
            str(PROJECT),
            "/Engine/Maps/Entry",
            "-game",
            "-windowed",
            "-ResX=1280",
            "-ResY=720",
            "-nosplash",
            f"-TrafficLivePort={listener.getsockname()[1]}",
            f"-TrafficLiveReport={output / 'unreal_live_report.json'}",
            f"-abslog={output / 'unreal.log'}",
        ]
        if args.verify:
            command += [f"-TrafficLiveCaptureDir={output}", "-TrafficLiveAutoExit"]
        if args.controller_class:
            command += [f"-TrafficLiveControllerClass={args.controller_class}"]
        if args.visual_profile:
            command += [f"-TrafficLiveProfile={unreal_object_path(args.visual_profile)}"]
        if args.record_seconds:
            command += [
                f"-TrafficLiveCaptureDir={output}",
                f"-TrafficLiveRecordSeconds={args.record_seconds}",
            ]
        print(f"Starting live SUMO + Unreal. Output: {output}", flush=True)
        with (output / "unreal.stdout.log").open("w") as log:
            editor_process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                producer = serve_simulation(
                    listener,
                    geometry_path=args.geometry.resolve(),
                    routes=args.routes,
                    output=output,
                    duration=args.duration,
                    step_length=args.step_length,
                    speed=args.speed,
                )
                if args.verify:
                    verify_output(output, producer, geometry)
                    editor_process.wait(timeout=30)
                    if editor_process.returncode:
                        raise RuntimeError(f"Unreal exited with code {editor_process.returncode}")
                if args.record_seconds:
                    encode_capture(output)
                snapshot_path = output / "visual_snapshot.json"
                if snapshot_path.is_file():
                    producer["visual_snapshot_sha256"] = hashlib.sha256(
                        snapshot_path.read_bytes(),
                    ).hexdigest()
                    (output / "sumo_live_report.json").write_text(
                        json.dumps(producer, indent=2),
                        encoding="utf-8",
                    )
                print(f"Live run complete: {output}", flush=True)
            except (Exception, KeyboardInterrupt):
                editor_process.terminate()
                editor_process.wait(timeout=15)
                raise


if __name__ == "__main__":
    main()
