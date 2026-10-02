from __future__ import annotations

import json
from pathlib import Path

import pytest
from supersuit import pad_action_space_v0

from ai_quantum_hvtc.rl.action_guard import (
    DiscreteActionGuardParallelEnv,
    capture_discrete_action_counts,
)
from scripts.smoke.sumo_rl_smoke import (
    configure_sumo_environment,
    find_sumo_home,
    package_net_paths,
)
from scripts.training.rl_sumo_train import _patch_sumo_rl_pettingzoo_compat


def test_real_sumo_rl_parallel_env_intercepts_invalid_action(
    tmp_path: Path,
) -> None:
    sumo_home = find_sumo_home()
    if sumo_home is None:
        pytest.skip("SUMO binaries are unavailable")
    configure_sumo_environment(sumo_home)

    _patch_sumo_rl_pettingzoo_compat()
    from sumo_rl import parallel_env

    net_file, route_file = package_net_paths()
    delta_time = 5
    raw_env = parallel_env(
        net_file=str(net_file),
        route_file=str(route_file),
        use_gui=False,
        begin_time=0,
        num_seconds=45,
        delta_time=delta_time,
        yellow_time=2,
        min_green=1,
        max_green=30,
        sumo_seed=42,
        sumo_warnings=False,
        additional_sumo_cmd="--no-step-log true --duration-log.disable true",
    )
    action_counts = capture_discrete_action_counts(raw_env)
    phase_source = raw_env.unwrapped
    guarded_env = DiscreteActionGuardParallelEnv(
        pad_action_space_v0(raw_env),
        action_counts=action_counts,
        phase_source=phase_source,
        event_log_path=tmp_path / "RUN-103-REAL" / "logs" / "action_interventions.jsonl",
        run_id="RUN-103-REAL",
    )

    try:
        _, _ = guarded_env.reset(seed=42)
        agent = raw_env.possible_agents[0]
        before = float(phase_source.env.sim_step)
        illegal_action = action_counts[agent]

        _, _, _, _, infos = guarded_env.step({agent: illegal_action})

        after = float(phase_source.env.sim_step)
        intervention = infos[agent]["action_guard_interventions"][0]
        event_path = guarded_env.event_log_path
        logged = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
    finally:
        guarded_env.close()

    assert after - before == delta_time
    assert intervention["schema"] == "rl_action_intervention.v1"
    assert intervention["agent"] == agent
    assert intervention["action"] == illegal_action
    assert intervention["legal_n"] == action_counts[agent]
    assert intervention["reason"] == "action_out_of_range"
    assert intervention["resolution"] == "held_current_green"
    assert intervention["submission_state"] == "attempted"
    assert intervention["step_outcome"] == "unverified"
    assert intervention["env_instance_id"]
    assert logged == intervention
