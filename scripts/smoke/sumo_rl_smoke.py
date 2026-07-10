from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_WINDOWS_SUMO_HOMES = (
    Path(r"C:\Program Files (x86)\Eclipse\Sumo"),
    Path(r"C:\Program Files\Eclipse\Sumo"),
    Path.home() / ".local" / "sumo" / "1.27.1",
    Path.home() / ".local" / "sumo" / "sumo-1.27.1",
)


@dataclass(frozen=True)
class SmokeResult:
    sumo_home: str | None
    sumo_version: str
    net_file: str
    route_file: str
    steps_executed: int
    observation_shape: list[int] | None
    total_reward: float
    final_simulation_step: float | int | None
    final_system_total_waiting_time: float | int | None
    final_system_total_stopped: float | int | None


def _has_sumo_binaries(path: Path) -> bool:
    executable_suffix = ".exe" if os.name == "nt" else ""
    return (path / "bin" / f"sumo{executable_suffix}").is_file() and (
        path / "bin" / f"sumo-gui{executable_suffix}"
    ).is_file()


def find_sumo_home(explicit: str | None = None) -> Path | None:
    candidates: list[Path] = []

    if explicit:
        candidates.append(Path(explicit))

    env_home = os.environ.get("SUMO_HOME")
    if env_home:
        candidates.append(Path(env_home))

    candidates.extend(DEFAULT_WINDOWS_SUMO_HOMES)

    for candidate in candidates:
        with suppress(OSError):
            resolved = candidate.expanduser().resolve()
            if _has_sumo_binaries(resolved):
                return resolved

    sumo_binary = shutil.which("sumo")
    if sumo_binary:
        return Path(sumo_binary).resolve().parent.parent

    return None


def configure_sumo_environment(sumo_home: Path | None) -> None:
    if sumo_home is None:
        return
    os.environ["SUMO_HOME"] = str(sumo_home)
    bin_path = str(sumo_home / "bin")
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if bin_path not in path_parts:
        os.environ["PATH"] = os.pathsep.join([bin_path, *path_parts])


def read_sumo_version() -> str:
    result = subprocess.run(
        ["sumo", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()[0].strip()


def package_net_paths() -> tuple[Path, Path]:
    spec = importlib.util.find_spec("sumo_rl")
    if spec is None or spec.submodule_search_locations is None:
        raise ImportError("sumo_rl package is not installed")

    package_dir = Path(next(iter(spec.submodule_search_locations)))
    net_dir = package_dir / "nets" / "2way-single-intersection"
    net_file = net_dir / "single-intersection.net.xml"
    route_file = net_dir / "single-intersection-vhvh.rou.xml"
    if not net_file.is_file() or not route_file.is_file():
        raise FileNotFoundError("SUMO-RL packaged single-intersection network is missing")
    return net_file, route_file


def _observation_shape(observation: Any) -> list[int] | None:
    shape = getattr(observation, "shape", None)
    if shape is None:
        return None
    return [int(value) for value in shape]


def run_smoke_test(*, steps: int, seed: int, sumo_home: str | None = None) -> SmokeResult:
    resolved_sumo_home = find_sumo_home(sumo_home)
    configure_sumo_environment(resolved_sumo_home)

    sumo_version = read_sumo_version()
    net_file, route_file = package_net_paths()

    from sumo_rl import SumoEnvironment

    env = SumoEnvironment(
        net_file=str(net_file),
        route_file=str(route_file),
        use_gui=False,
        single_agent=True,
        begin_time=0,
        num_seconds=max(steps * 5 + 10, 40),
        delta_time=5,
        yellow_time=2,
        min_green=5,
        max_green=30,
        sumo_seed=seed,
        sumo_warnings=False,
        additional_sumo_cmd="--no-step-log true --duration-log.disable true",
    )

    total_reward = 0.0
    final_info: dict[str, Any] = {}
    steps_executed = 0

    try:
        observation, final_info = env.reset(seed=seed)
        observation_shape = _observation_shape(observation)

        for step_index in range(steps):
            action_count = int(getattr(env.action_space, "n", 1))
            action = step_index % max(action_count, 1)
            observation, reward, terminated, truncated, final_info = env.step(action)
            total_reward += float(reward)
            steps_executed += 1
            if terminated or truncated:
                break
    finally:
        env.close()

    return SmokeResult(
        sumo_home=str(resolved_sumo_home) if resolved_sumo_home else None,
        sumo_version=sumo_version,
        net_file=str(net_file),
        route_file=str(route_file),
        steps_executed=steps_executed,
        observation_shape=observation_shape,
        total_reward=round(total_reward, 6),
        final_simulation_step=final_info.get("step"),
        final_system_total_waiting_time=final_info.get("system_total_waiting_time"),
        final_system_total_stopped=final_info.get("system_total_stopped"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a minimal SUMO-RL smoke test.")
    parser.add_argument("--steps", type=int, default=6, help="Number of environment steps.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic SUMO seed.")
    parser.add_argument(
        "--sumo-home",
        default=None,
        help="Optional SUMO_HOME override. Auto-detects common Windows install paths.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.steps < 1:
        raise SystemExit("--steps must be >= 1")

    result = run_smoke_test(steps=args.steps, seed=args.seed, sumo_home=args.sumo_home)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
