from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.render.run_sumo_unreal import DEFAULT_GEOMETRY, DEFAULT_ROUTES, serve_simulation


@pytest.mark.skipif(
    not DEFAULT_GEOMETRY.is_file() or not DEFAULT_ROUTES.is_file(),
    reason="Retained SUMO map/routes unavailable",
)
def test_live_bridge_streams_retained_sumo_poses_and_signal_links(tmp_path: Path) -> None:
    """Exercise real TraCI and TCP, including the consumer readiness handshake."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(
                serve_simulation,
                listener,
                geometry_path=DEFAULT_GEOMETRY,
                routes=DEFAULT_ROUTES,
                output=tmp_path,
                duration=2,
                step_length=0.2,
                speed=0,
            )
            with socket.create_connection(listener.getsockname(), timeout=30) as client:
                client.settimeout(30)
                with client.makefile("rb") as stream:
                    hello = json.loads(stream.readline())
                    assert hello["packet_type"] == "hello"
                    assert hello["traffic_light_heads"]
                    geometry = json.loads(
                        Path(hello["geometry_manifest"]).read_text(encoding="utf-8"),
                    )
                    assert geometry["source_net_sha256"] == (
                        "80637f09674799490eecfcd9ae1c9abe3f795795350ca3b61e8aa53d4d1f33e0"
                    )
                    assert geometry["lane_count"] == 32013
                    client.sendall(b"ready\n")
                    frames = []
                    while True:
                        packet = json.loads(stream.readline())
                        if packet["packet_type"] == "complete":
                            break
                        assert packet["packet_type"] == "frame"
                        frames.append(packet)
                    assert len(frames) == 10
                    assert [f["time_seconds"] for f in frames] == sorted(
                        f["time_seconds"] for f in frames
                    )
                    lights = {
                        light["traffic_light_id"]: light["state"]
                        for light in frames[-1]["traffic_lights"]
                    }
                    for head in hello["traffic_light_heads"]:
                        assert head["link_index"] < len(lights[head["traffic_light_id"]])
                    first = frames[0]["vehicles"][0]
                    last = frames[-1]["vehicles"][0]
                    assert first["vehicle_id"] == last["vehicle_id"]
                    assert (first["x"], first["y"]) != (last["x"], last["y"])
                    assert last["reference_point"] == "front_bumper_center"
                    assert all(last[key] > 0 for key in ("length_m", "width_m", "height_m"))
            report = future.result(timeout=30)
            assert report["status"] == "complete"
            assert report["frames_sent"] == len(frames)
            recorded = [
                json.loads(line)
                for line in (tmp_path / "live_frames.jsonl").read_text().splitlines()
            ]
            assert recorded == frames
