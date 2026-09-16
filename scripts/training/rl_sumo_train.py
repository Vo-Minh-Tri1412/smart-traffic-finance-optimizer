from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.map_economics import (  # noqa: E402
    MapEconomicProfile,
    audit_profile_coverage,
    load_map_economic_profile,
)
from ai_quantum_hvtc.rl import (  # noqa: E402
    SumoMapEconomicReward,
    build_sumo_map_economic_reward,
    build_sumo_rl_reward,
    training_blockers,
    validate_reward_profile_against_spec,
)
from ai_quantum_hvtc.rl import (  # noqa: E402
    load_reward_profile as load_technical_reward_profile,
)
from ai_quantum_hvtc.simulation.engines.sumo.config import resolve_sumo_binary  # noqa: E402
from ai_quantum_hvtc.simulation.engines.sumo.errors import SumoRuntimeError  # noqa: E402
from ai_quantum_hvtc.simulation.engines.sumo.exporter import (  # noqa: E402
    SumoExportPaths,
    export_sumo_project,
)
from ai_quantum_hvtc.simulation.specs.loader import load_district_spec  # noqa: E402


@dataclass(frozen=True)
class TrainingPlan:
    status: str
    run_id: str
    cloud_runtime: str
    spec_path: str
    scenario_id: str
    reward_profile_id: str
    reward_profile_status: str
    reward_mode: str
    map_economic_profile_path: str | None
    map_economic_profile_id: str | None
    map_economic_profile_status: str | None
    map_economic_coverage: dict[str, Any] | None
    total_timesteps: int
    out_dir: str
    agent_mode: str
    memory_mode: str
    frame_stack_size: int
    num_envs: int
    rollout_steps: int
    validation_errors: list[str]
    training_blockers: list[str]
    notes: list[str]


def detect_cloud_runtime() -> str:
    if os.environ.get("COLAB_RELEASE_TAG") or Path("/content").exists():
        return "colab"
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle/working").exists():
        return "kaggle"
    return "local"


def build_sumo_net(paths: SumoExportPaths) -> None:
    netconvert = resolve_sumo_binary("netconvert")
    if netconvert is None:
        raise SumoRuntimeError("netconvert was not found. Install SUMO in the cloud runtime first.")
    # `subprocess.run(..., cwd=paths.work_dir)` makes relative paths resolve inside the work
    # directory. Export paths may be relative to the project root, so pass absolute paths to avoid
    # accidentally looking for `<work_dir>/<work_dir>/district.nod.xml` on Windows/cloud runners.
    nodes = paths.nodes.resolve()
    edges = paths.edges.resolve()
    net = paths.net.resolve()
    command = [
        netconvert,
        "--node-files",
        str(nodes),
        "--edge-files",
        str(edges),
        "--output-file",
        str(net),
        "--no-turnarounds",
        "true",
    ]
    completed = subprocess.run(
        command,
        cwd=paths.work_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SumoRuntimeError(
            "netconvert failed:\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )


def create_training_plan(args: argparse.Namespace) -> TrainingPlan:
    spec = load_district_spec(args.spec)
    if args.scenario not in spec.scenarios:
        raise SystemExit(f"unknown scenario_id: {args.scenario}")
    profile = load_technical_reward_profile(args.reward_profile)
    validation_errors = validate_reward_profile_against_spec(profile, spec)
    blockers = training_blockers(
        profile,
        spec,
        allow_draft_reward=args.allow_draft_reward,
        acknowledge_pending_hard_constraints=args.acknowledge_pending_hard_constraints,
    )
    map_profile, map_coverage, map_blockers = _load_map_economic_context(args)
    blockers.extend(map_blockers)
    runtime = args.cloud_runtime if args.cloud_runtime != "auto" else detect_cloud_runtime()
    notes = [
        (
            "Default mode is dry-run; pass --train explicitly on Colab/Kaggle to start the "
            "selected PPO/RecurrentPPO policy."
        ),
        (
            "The default policy is shared multi-agent signal control with LSTM memory, "
            "not route choice."
        ),
        "Hard emergency priority must become an action filter/override before final claims.",
    ]
    if map_profile is not None:
        notes.append(
            "Map-economic mode monetizes incremental SUMO timeLoss; raw VND remains separate "
            "from the normalized/clipped PPO reward."
        )
    if runtime == "local":
        notes.append(
            "Local runtime detected; training is blocked unless --allow-local-training is set."
        )
    return TrainingPlan(
        status="dry_run" if not args.train else "ready_to_train",
        run_id=args.run_id,
        cloud_runtime=runtime,
        spec_path=str(Path(args.spec)),
        scenario_id=args.scenario,
        reward_profile_id=profile.profile_id,
        reward_profile_status=profile.status,
        reward_mode=(
            "map_economic_incremental" if map_profile is not None else "technical_profile"
        ),
        map_economic_profile_path=(
            str(Path(args.map_economic_profile)) if args.map_economic_profile else None
        ),
        map_economic_profile_id=(
            map_profile.metadata.profile_id if map_profile is not None else None
        ),
        map_economic_profile_status=(
            map_profile.metadata.status if map_profile is not None else None
        ),
        map_economic_coverage=map_coverage,
        total_timesteps=args.total_timesteps,
        out_dir=str(Path(args.out_dir)),
        agent_mode=args.agent_mode,
        memory_mode=args.memory,
        frame_stack_size=args.frame_stack_size,
        num_envs=args.num_envs,
        rollout_steps=args.rollout_steps,
        validation_errors=validation_errors,
        training_blockers=blockers,
        notes=notes,
    )


def _sumo_environment_kwargs(
    *,
    paths: SumoExportPaths,
    log_dir: Path,
    run_id: str,
    reward_fn: Any,
    spec: Any,
    seed: int,
    yellow_time: int,
    min_green: int,
    max_green: int,
) -> dict[str, Any]:
    """Build one shared SUMO-RL configuration for single- and multi-agent modes.

    The environment remains deliberately template-friendly: demand, reward and observation
    extensions are supplied by the district spec and reward profile instead of being hard-coded
    for one map.  Multi-agent mode uses SUMO-RL's PettingZoo parallel API so a shared policy can
    scale from a small ROI smoke test to a full Quận 7/large-ROI run.
    """

    return {
        "net_file": str(paths.net),
        "route_file": str(paths.routes),
        "out_csv_name": str(log_dir / run_id),
        "use_gui": False,
        "begin_time": 0,
        "num_seconds": spec.metadata.horizon_seconds,
        "delta_time": max(1, spec.metadata.time_step_seconds),
        "yellow_time": yellow_time,
        "min_green": min_green,
        "max_green": max_green,
        "reward_fn": reward_fn,
        "sumo_seed": seed,
        "sumo_warnings": False,
        "additional_sumo_cmd": "--no-step-log true --duration-log.disable true",
    }


def _build_training_env(
    *,
    args: argparse.Namespace,
    paths: SumoExportPaths,
    log_dir: Path,
    reward_fn: Any,
    spec: Any,
) -> Any:
    """Create a SB3-compatible environment with optional temporal memory.

    In multi-agent mode, each traffic signal is an agent and the policy is shared through the
    SuperSuit PettingZoo-to-VecEnv adapter.  RecurrentPPO receives one recurrent state per
    vectorized agent stream.  This is a scalable baseline; future graph/centralized-critic work
    can replace this adapter without changing SUMO export or reward contracts.
    """

    kwargs = _sumo_environment_kwargs(
        paths=paths,
        log_dir=log_dir,
        run_id=args.run_id,
        reward_fn=reward_fn,
        spec=spec,
        seed=args.seed,
        yellow_time=args.yellow_time,
        min_green=args.min_green,
        max_green=args.max_green,
    )

    if args.agent_mode == "multi_agent":
        _patch_sumo_rl_pettingzoo_compat()
        from sumo_rl import parallel_env
        from supersuit import (
            concat_vec_envs_v1,
            pad_action_space_v0,
            pad_observations_v0,
            pettingzoo_env_to_vec_env_v1,
        )

        env = parallel_env(**kwargs)
        # SUMO-RL 1.4.5's PettingZoo wrapper predates the render_mode attribute expected by
        # SuperSuit's MarkovVectorEnv. Headless training has no renderer, so an explicit None is
        # the correct compatibility value.
        if not hasattr(env.unwrapped, "render_mode"):
            env.unwrapped.render_mode = None
        # Incoming lanes/phases differ across real intersections. Padding keeps one shared policy
        # shape while preserving each agent's local feature ordering.
        env = pad_observations_v0(env)
        env = pad_action_space_v0(env)
        env = pettingzoo_env_to_vec_env_v1(env)
        # Always pass through concat_vec_envs_v1 so the MarkovVectorEnv becomes an SB3 VecEnv,
        # including the default single-copy case.
        env = concat_vec_envs_v1(
            env,
            args.num_envs,
            base_class="stable_baselines3",
        )
        # Supersuit 3.11's SB3 wrapper delegates ``seed`` to a Gymnasium VectorEnv that only
        # accepts reset(seed=...). SUMO's `sumo_seed` is already fixed in kwargs, so expose the
        # SB3-compatible no-op seed hook while retaining deterministic SUMO initialization.
        if not hasattr(env.venv, "seed"):
            env.seed = lambda seed=None: [seed] * env.num_envs
    else:
        from sumo_rl import SumoEnvironment

        env = SumoEnvironment(single_agent=True, **kwargs)

    if args.memory == "frame_stack":
        from stable_baselines3.common.vec_env import VecFrameStack

        env = VecFrameStack(env, n_stack=args.frame_stack_size)
    return env


def _patch_sumo_rl_pettingzoo_compat() -> None:
    """Bridge SUMO-RL 1.4.x's old PettingZoo import to the current class export.

    SUMO-RL 1.4.5 imports ``agent_selector`` as if it were callable, while compatible PettingZoo
    releases expose the module and the ``AgentSelector`` class separately. Keep this tiny adapter
    local to the training entrypoint so the rest of the project does not depend on private library
    internals.
    """

    import sumo_rl.environment.env as sumo_env_module
    from pettingzoo.utils.agent_selector import AgentSelector

    if not callable(sumo_env_module.agent_selector):
        sumo_env_module.agent_selector = AgentSelector


def _build_policy(args: argparse.Namespace, env: Any, *, seed: int) -> Any:
    if args.memory == "lstm":
        from sb3_contrib import RecurrentPPO

        return RecurrentPPO(
            "MlpLstmPolicy",
            env,
            n_steps=args.rollout_steps,
            verbose=1,
            seed=seed,
        )

    from stable_baselines3 import PPO

    return PPO(
        "MlpPolicy",
        env,
        n_steps=args.rollout_steps,
        verbose=1,
        seed=seed,
    )


def train(args: argparse.Namespace) -> dict[str, Any]:
    runtime = args.cloud_runtime if args.cloud_runtime != "auto" else detect_cloud_runtime()
    if runtime == "local" and not args.allow_local_training:
        raise SystemExit(
            "Refusing to train locally. Use Colab/Kaggle or pass --allow-local-training."
        )

    spec = load_district_spec(args.spec)
    profile = load_technical_reward_profile(args.reward_profile)
    blockers = training_blockers(
        profile,
        spec,
        allow_draft_reward=args.allow_draft_reward,
        acknowledge_pending_hard_constraints=args.acknowledge_pending_hard_constraints,
    )
    map_profile, map_coverage, map_blockers = _load_map_economic_context(args)
    blockers.extend(map_blockers)
    if blockers:
        raise SystemExit("Training blocked:\n- " + "\n- ".join(blockers))

    out_dir = Path(args.out_dir)
    sumo_dir = out_dir / "sumo"
    model_dir = out_dir / "models"
    log_dir = out_dir / "logs"
    for directory in (sumo_dir, model_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    paths = export_sumo_project(
        spec=spec,
        scenario_id=args.scenario,
        controller_id="rl_policy",
        seed=args.seed,
        work_dir=sumo_dir,
    )
    build_sumo_net(paths)

    map_reward: SumoMapEconomicReward | None = None
    reward_fn: Callable[[Any], float]
    if map_profile is not None:
        map_reward = build_sumo_map_economic_reward(map_profile, spec)
        reward_fn = map_reward
    else:
        reward_fn = build_sumo_rl_reward(profile, spec, scenario_id=args.scenario)
    env = _build_training_env(
        args=args,
        paths=paths,
        log_dir=log_dir,
        reward_fn=reward_fn,
        spec=spec,
    )
    try:
        model = _build_policy(args, env, seed=args.seed)
        model.learn(total_timesteps=args.total_timesteps)
        model_path = model_dir / f"{args.run_id}.zip"
        model.save(str(model_path))
    finally:
        env.close()

    manifest = {
        "status": "trained",
        "run_id": args.run_id,
        "runtime": runtime,
        "model_path": str(model_path),
        "sumo_artifacts": str(sumo_dir),
        "reward_profile": str(args.reward_profile),
        "reward_mode": (
            "map_economic_incremental" if map_profile is not None else "technical_profile"
        ),
        "map_economic_profile": (
            str(args.map_economic_profile) if args.map_economic_profile else None
        ),
        "map_economic_profile_id": (
            map_profile.metadata.profile_id if map_profile is not None else None
        ),
        "map_economic_profile_status": (
            map_profile.metadata.status if map_profile is not None else None
        ),
        "map_economic_coverage": map_coverage,
        "economic_ledger_scope": (
            "Callback-local sampled controlled-lane increments; first sightings and departed "
            "vehicles are excluded. Vector environment copies own their ledgers; this manifest "
            "does not aggregate them. Use complete SUMO trip outcomes for finance evaluation."
            if map_profile is not None
            else None
        ),
        "scenario": args.scenario,
        "total_timesteps": args.total_timesteps,
        "agent_mode": args.agent_mode,
        "memory_mode": args.memory,
        "frame_stack_size": args.frame_stack_size if args.memory == "frame_stack" else 0,
        "num_envs": args.num_envs,
        "rollout_steps": args.rollout_steps,
        "observation_note": (
            "SUMO-RL default per-signal observation remains the template. Replace or extend it "
            "with the project observation/sensor adapter before camera-based claims."
        ),
    }
    (out_dir / "training_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cloud-oriented SUMO-RL training scaffold with a pluggable reward profile."
    )
    parser.add_argument("--spec", required=True, help="District spec JSON path.")
    parser.add_argument("--scenario", required=True, help="Scenario id from the district spec.")
    parser.add_argument("--reward-profile", required=True, help="Reward profile TOML path.")
    parser.add_argument(
        "--map-economic-profile",
        help=(
            "Optional map_economic_profile.v1 JSON. When supplied, PPO receives the "
            "incremental map-aware economic reward and the TOML profile remains the safety gate."
        ),
    )
    parser.add_argument("--out-dir", required=True, help="Cloud output folder, e.g. Drive/Kaggle.")
    parser.add_argument("--run-id", default="RUN-RL-V0-001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--total-timesteps", type=int, default=10_000)
    parser.add_argument(
        "--agent-mode",
        choices=["multi_agent", "single_agent"],
        default="multi_agent",
        help="Use one shared policy across all SUMO traffic signals or a single signal.",
    )
    parser.add_argument(
        "--memory",
        choices=["lstm", "frame_stack", "none"],
        default="lstm",
        help="Temporal memory: RecurrentPPO LSTM, vector frame stack, or plain PPO.",
    )
    parser.add_argument(
        "--frame-stack-size",
        type=int,
        default=4,
        help="Number of observations stacked when --memory frame_stack is selected.",
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=1,
        help="Number of parallel PettingZoo copies in multi-agent mode.",
    )
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=128,
        help="Per-vector-agent rollout length before each PPO update.",
    )
    parser.add_argument(
        "--cloud-runtime",
        choices=["auto", "colab", "kaggle", "local"],
        default="auto",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only. This is the default.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Actually train. Intended for Colab/Kaggle.",
    )
    parser.add_argument("--allow-local-training", action="store_true")
    parser.add_argument("--allow-draft-reward", action="store_true")
    parser.add_argument(
        "--allow-unreviewed-map-economics",
        action="store_true",
        help=(
            "Allow exploratory training despite failed map-economic production coverage. "
            "This does not authorize policy or finance claims."
        ),
    )
    parser.add_argument("--acknowledge-pending-hard-constraints", action="store_true")
    parser.add_argument("--yellow-time", type=int, default=2)
    parser.add_argument("--min-green", type=int, default=5)
    parser.add_argument("--max-green", type=int, default=50)
    return parser


def _load_map_economic_context(
    args: argparse.Namespace,
) -> tuple[MapEconomicProfile | None, dict[str, Any] | None, list[str]]:
    if not args.map_economic_profile:
        return None, None, []
    profile = load_map_economic_profile(args.map_economic_profile)
    coverage = audit_profile_coverage(profile)
    blockers: list[str] = []
    spec = load_district_spec(args.spec)
    if profile.metadata.map_project_id != spec.metadata.district_id:
        blockers.append(
            "map-economic profile map_project_id does not match the training district_id; "
            "an explicit existing-net/OD binding is required"
        )
    if not coverage.production_gate_passed and not args.allow_unreviewed_map_economics:
        blockers.extend(
            f"map-economic production gate: {reason}" for reason in coverage.production_gate_reasons
        )
    return profile, coverage.to_dict(), blockers


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.train and args.dry_run:
        raise SystemExit("Choose either --dry-run or --train, not both.")
    if args.total_timesteps < 1:
        raise SystemExit("--total-timesteps must be >= 1")
    if args.frame_stack_size < 1:
        raise SystemExit("--frame-stack-size must be >= 1")
    if args.num_envs < 1:
        raise SystemExit("--num-envs must be >= 1")
    if args.rollout_steps < 1:
        raise SystemExit("--rollout-steps must be >= 1")

    plan = create_training_plan(args)
    if not args.train:
        print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
        return 0

    result = train(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
