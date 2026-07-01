from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_quantum_hvtc.rl import (  # noqa: E402
    build_sumo_rl_reward,
    load_reward_profile,
    training_blockers,
    validate_reward_profile_against_spec,
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
    total_timesteps: int
    out_dir: str
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
    command = [
        netconvert,
        "--node-files",
        str(paths.nodes),
        "--edge-files",
        str(paths.edges),
        "--output-file",
        str(paths.net),
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
    profile = load_reward_profile(args.reward_profile)
    validation_errors = validate_reward_profile_against_spec(profile, spec)
    blockers = training_blockers(
        profile,
        spec,
        allow_draft_reward=args.allow_draft_reward,
        acknowledge_pending_hard_constraints=args.acknowledge_pending_hard_constraints,
    )
    runtime = args.cloud_runtime if args.cloud_runtime != "auto" else detect_cloud_runtime()
    notes = [
        "Default mode is dry-run; pass --train explicitly on Colab/Kaggle to start PPO.",
        "This scaffold trains a SUMO-RL signal-control policy, not a route-choice policy.",
        "Hard emergency priority must become an action filter/override before final claims.",
    ]
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
        total_timesteps=args.total_timesteps,
        out_dir=str(Path(args.out_dir)),
        validation_errors=validation_errors,
        training_blockers=blockers,
        notes=notes,
    )


def train(args: argparse.Namespace) -> dict[str, Any]:
    runtime = args.cloud_runtime if args.cloud_runtime != "auto" else detect_cloud_runtime()
    if runtime == "local" and not args.allow_local_training:
        raise SystemExit(
            "Refusing to train locally. Use Colab/Kaggle or pass --allow-local-training."
        )

    spec = load_district_spec(args.spec)
    profile = load_reward_profile(args.reward_profile)
    blockers = training_blockers(
        profile,
        spec,
        allow_draft_reward=args.allow_draft_reward,
        acknowledge_pending_hard_constraints=args.acknowledge_pending_hard_constraints,
    )
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

    from stable_baselines3 import PPO
    from sumo_rl import SumoEnvironment  # type: ignore[import-untyped]

    reward_fn = build_sumo_rl_reward(profile, spec, scenario_id=args.scenario)
    env = SumoEnvironment(
        net_file=str(paths.net),
        route_file=str(paths.routes),
        out_csv_name=str(log_dir / args.run_id),
        use_gui=False,
        single_agent=True,
        begin_time=0,
        num_seconds=spec.metadata.horizon_seconds,
        delta_time=max(1, spec.metadata.time_step_seconds),
        yellow_time=args.yellow_time,
        min_green=args.min_green,
        max_green=args.max_green,
        reward_fn=reward_fn,
        sumo_seed=args.seed,
        sumo_warnings=False,
        additional_sumo_cmd="--no-step-log true --duration-log.disable true",
    )
    try:
        model = PPO("MlpPolicy", env, verbose=1, seed=args.seed)
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
        "scenario": args.scenario,
        "total_timesteps": args.total_timesteps,
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
    parser.add_argument("--out-dir", required=True, help="Cloud output folder, e.g. Drive/Kaggle.")
    parser.add_argument("--run-id", default="RUN-RL-V0-001")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--total-timesteps", type=int, default=10_000)
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
    parser.add_argument("--acknowledge-pending-hard-constraints", action="store_true")
    parser.add_argument("--yellow-time", type=int, default=2)
    parser.add_argument("--min-green", type=int, default=5)
    parser.add_argument("--max-green", type=int, default=50)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.train and args.dry_run:
        raise SystemExit("Choose either --dry-run or --train, not both.")
    if args.total_timesteps < 1:
        raise SystemExit("--total-timesteps must be >= 1")

    plan = create_training_plan(args)
    if not args.train:
        print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
        return 0

    result = train(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
