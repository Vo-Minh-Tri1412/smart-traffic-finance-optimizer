from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cloudpickle
import numpy as np
import pytest
import sumo_rl
import supersuit
from gymnasium.spaces import Box, Discrete
from pettingzoo.utils.env import ParallelEnv

from ai_quantum_hvtc.rl.action_guard import (
    ActionGuardError,
    DiscreteActionGuardParallelEnv,
    capture_discrete_action_counts,
    validate_action_interval,
)
from scripts.training import rl_sumo_train


class _FakeSignal:
    def __init__(self, green_phase: object = 1, is_yellow: object = False) -> None:
        self.green_phase = green_phase
        self.is_yellow = is_yellow


class _FakeParallelEnv(ParallelEnv[str, np.ndarray, Any]):
    metadata: dict[str, Any] = {"name": "action-guard-test"}

    def __init__(
        self,
        action_sizes: dict[str, int],
        *,
        signal_states: dict[str, _FakeSignal | None] | None = None,
    ) -> None:
        super().__init__()
        self.possible_agents = list(action_sizes)
        self.agents = self.possible_agents.copy()
        self.action_spaces = {agent: Discrete(size) for agent, size in action_sizes.items()}
        self.observation_spaces = {
            agent: Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32) for agent in action_sizes
        }
        self.traffic_signals = signal_states or {agent: _FakeSignal() for agent in action_sizes}
        self.sim_step = 42.0
        self.step_calls = 0
        self.received_actions: dict[str, Any] | None = None

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]]]:
        del seed, options
        return (
            {agent: np.zeros(1, dtype=np.float32) for agent in self.agents},
            {agent: {} for agent in self.agents},
        )

    def step(
        self,
        actions: dict[str, Any],
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        self.step_calls += 1
        self.received_actions = dict(actions)
        observations = {agent: np.zeros(1, dtype=np.float32) for agent in self.agents}
        rewards = {agent: 0.0 for agent in self.agents}
        flags = {agent: False for agent in self.agents}
        infos = {agent: {"kept": True} for agent in self.agents}
        return observations, rewards, flags, flags.copy(), infos

    def render(self) -> None:
        return None

    def close(self) -> None:
        return None

    def action_space(self, agent: str) -> Discrete:
        return self.action_spaces[agent]

    def observation_space(self, agent: str) -> Box:
        return self.observation_spaces[agent]


def _guard(
    env: _FakeParallelEnv,
    *,
    action_counts: dict[str, int] | None = None,
    event_log_path: Path,
) -> DiscreteActionGuardParallelEnv:
    return DiscreteActionGuardParallelEnv(
        env,
        action_counts=action_counts or capture_discrete_action_counts(env),
        phase_source=env,
        event_log_path=event_log_path,
        run_id="RUN-103-TEST",
    )


def test_capture_and_guard_preserve_unequal_local_action_sizes_and_log_padded_action(
    tmp_path: Path,
) -> None:
    raw_env = _FakeParallelEnv({"small": 2, "large": 4})
    action_counts = capture_discrete_action_counts(raw_env)
    padded_env = _FakeParallelEnv({"small": 4, "large": 4})
    event_path = tmp_path / "RUN-103-TEST" / "logs" / "action_interventions.jsonl"
    env = _guard(padded_env, action_counts=action_counts, event_log_path=event_path)

    _, _, _, _, infos = env.step({"small": 3, "large": 1})

    assert padded_env.received_actions == {"small": 1, "large": 1}
    assert padded_env.step_calls == 1
    intervention = infos["small"]["action_guard_interventions"][0]
    assert intervention["schema"] == "rl_action_intervention.v1"
    assert intervention["run_id"] == "RUN-103-TEST"
    assert intervention["agent"] == "small"
    assert intervention["action"] == 3
    assert intervention["legal_n"] == 2
    assert intervention["current_phase"] == 1
    assert intervention["time"] == 42
    assert intervention["reason"] == "padded_action"
    assert intervention["resolution"] == "held_current_green"
    assert intervention["submission_state"] == "attempted"
    assert intervention["step_outcome"] == "unverified"
    assert intervention["env_instance_id"]
    assert infos["small"]["kept"] is True
    assert json.loads(event_path.read_text(encoding="utf-8").splitlines()[0]) == intervention


@pytest.mark.parametrize(
    ("action", "expected_reason"),
    [(-1, "negative_action"), (1.5, "non_integer_action"), (True, "non_integer_action")],
)
def test_invalid_action_holds_current_phase(
    tmp_path: Path,
    action: object,
    expected_reason: str,
) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)

    _, _, _, _, infos = env.step({"signal": action})

    assert base_env.received_actions == {"signal": 1}
    intervention = infos["signal"]["action_guard_interventions"][0]
    assert intervention["reason"] == expected_reason
    assert intervention["resolution"] == "held_current_green"


def test_valid_actions_pass_through_without_intervention(tmp_path: Path) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)

    _, _, _, _, infos = env.step({"signal": 2})

    assert base_env.received_actions == {"signal": 2}
    assert "action_guard_interventions" not in infos["signal"]
    assert event_path.read_text(encoding="utf-8") == ""


def test_existing_run_log_is_not_overwritten_or_merged(tmp_path: Path) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    previous_run_event = '{"run_id":"PREVIOUS-RUN"}\n'
    event_path.write_text(previous_run_event, encoding="utf-8")

    with pytest.raises(ActionGuardError, match="already exists"):
        _guard(base_env, event_log_path=event_path)

    assert base_env.step_calls == 0
    assert event_path.read_text(encoding="utf-8") == previous_run_event


def test_cloned_wrappers_append_events_with_distinct_stable_instance_ids(
    tmp_path: Path,
) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)
    cloned_env = cloudpickle.loads(cloudpickle.dumps(env))

    _, _, _, _, infos = env.step({"signal": 3})
    _, _, _, _, cloned_infos = cloned_env.step({"signal": 3})
    first_id = infos["signal"]["action_guard_interventions"][0]["env_instance_id"]
    clone_id = cloned_infos["signal"]["action_guard_interventions"][0]["env_instance_id"]

    env.step({"signal": 3})
    cloned_env.step({"signal": 3})
    logged_events = [
        json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
    ]
    assert first_id != clone_id
    assert {event["env_instance_id"] for event in logged_events} == {first_id, clone_id}
    assert [event["env_instance_id"] for event in logged_events] == [
        first_id,
        clone_id,
        first_id,
        clone_id,
    ]


def test_intervention_log_failure_prevents_environment_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)

    def fail_to_write(_events: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(env, "_append_events", fail_to_write)

    with pytest.raises(ActionGuardError, match="Cannot persist action intervention log"):
        env.step({"signal": 3})

    assert base_env.step_calls == 0
    assert event_path.read_text(encoding="utf-8") == ""


def test_failed_environment_step_gets_separate_outcome_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_env = _FakeParallelEnv({"signal": 3})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)

    def fail_step(_actions: object) -> None:
        raise RuntimeError("simulator failed")

    monkeypatch.setattr(base_env, "step", fail_step)

    with pytest.raises(RuntimeError, match="simulator failed"):
        env.step({"signal": 3})

    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["schema"] == "rl_action_intervention.v1"
    assert events[0]["submission_state"] == "attempted"
    assert events[0]["step_outcome"] == "unverified"
    assert events[1]["schema"] == "rl_action_intervention_outcome.v1"
    assert events[1]["step_outcome"] == "step_failed"


@pytest.mark.parametrize(
    ("signal", "expected_resolution_reason"),
    [
        (None, "traffic_signal_unavailable"),
        (_FakeSignal(green_phase=None), "current_phase_missing_or_non_integer"),
        (_FakeSignal(green_phase=3), "current_phase_out_of_range"),
        (_FakeSignal(is_yellow=True), "signal_not_confirmed_in_green_phase"),
    ],
)
def test_unresolvable_current_phase_logs_and_fails_before_step(
    tmp_path: Path,
    signal: _FakeSignal | None,
    expected_resolution_reason: str,
) -> None:
    base_env = _FakeParallelEnv({"signal": 3}, signal_states={"signal": signal})
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(base_env, event_log_path=event_path)

    with pytest.raises(ActionGuardError, match="Refusing to advance SUMO"):
        env.step({"signal": 4})

    assert base_env.step_calls == 0
    event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["reason"] == "action_out_of_range"
    assert event["resolution"] == "failed_closed"
    assert event["resolution_reason"] == expected_resolution_reason


def test_unresolved_agent_fails_closed_for_every_invalid_action_in_batch(
    tmp_path: Path,
) -> None:
    base_env = _FakeParallelEnv(
        {"resolvable": 3, "unresolvable": 3},
        signal_states={"resolvable": _FakeSignal(), "unresolvable": None},
    )
    event_path = tmp_path / "action_interventions.jsonl"
    env = _guard(
        base_env,
        action_counts={"resolvable": 2, "unresolvable": 2},
        event_log_path=event_path,
    )

    with pytest.raises(ActionGuardError, match="Refusing to advance SUMO"):
        env.step({"resolvable": 2, "unresolvable": 4})

    assert base_env.step_calls == 0
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert {event["resolution"] for event in events} == {"failed_closed"}
    assert {event["submission_state"] for event in events} == {"not_attempted"}
    assert {event["step_outcome"] for event in events} == {"not_started"}
    by_agent = {event["agent"]: event for event in events}
    assert by_agent["resolvable"]["resolution_reason"] == ("batch_aborted_due_to_unresolved_action")
    assert by_agent["unresolvable"]["resolution_reason"] == "traffic_signal_unavailable"


@pytest.mark.parametrize(
    ("delta_time", "yellow_time"),
    [(5, 5), (4, 5), (0, 0), (6, -1)],
)
def test_action_interval_rejects_clearance_interruption(
    delta_time: int,
    yellow_time: int,
) -> None:
    with pytest.raises(ValueError, match="Training"):
        validate_action_interval(delta_time=delta_time, yellow_time=yellow_time)


def test_action_interval_allows_next_action_after_yellow_clearance() -> None:
    validate_action_interval(delta_time=6, yellow_time=5)


@pytest.mark.parametrize(
    ("time_step_seconds", "yellow_time", "expected_message"),
    [
        (6, 6, "greater than yellow_time"),
        (0, 0, "positive integer"),
        (-1, 0, "positive integer"),
    ],
)
def test_training_builder_rejects_interval_before_constructing_sumo_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    time_step_seconds: int,
    yellow_time: int,
    expected_message: str,
) -> None:
    def fail_if_sumo_env_constructed(**_kwargs: Any) -> None:
        raise AssertionError("SUMO environment must not be constructed for an unsafe interval")

    monkeypatch.setattr(rl_sumo_train, "_patch_sumo_rl_pettingzoo_compat", lambda: None)
    monkeypatch.setattr(sumo_rl, "parallel_env", fail_if_sumo_env_constructed)

    with pytest.raises(ValueError, match=expected_message):
        rl_sumo_train._build_training_env(
            args=SimpleNamespace(
                agent_mode="multi_agent",
                run_id="RUN-103-INVALID-TIMING",
                seed=7,
                yellow_time=yellow_time,
                min_green=5,
                max_green=50,
                num_envs=1,
                memory="none",
                frame_stack_size=4,
            ),
            paths=SimpleNamespace(net=tmp_path / "toy.net.xml", routes=tmp_path / "toy.rou.xml"),
            log_dir=tmp_path / "logs",
            reward_fn=lambda _signal: 0.0,
            spec=SimpleNamespace(
                metadata=SimpleNamespace(
                    horizon_seconds=20,
                    time_step_seconds=time_step_seconds,
                )
            ),
        )


def test_training_builder_guards_after_padding_before_vectorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_env = _FakeParallelEnv({"small": 2, "large": 4})
    call_order: list[str] = []
    captured: dict[str, Any] = {}

    def fake_parallel_env(**kwargs: Any) -> _FakeParallelEnv:
        call_order.append("parallel_env")
        assert kwargs["delta_time"] == 6
        assert kwargs["yellow_time"] == 2
        return raw_env

    def fake_pad_observations(env: _FakeParallelEnv) -> _FakeParallelEnv:
        call_order.append("pad_observations")
        return env

    def fake_pad_actions(env: _FakeParallelEnv) -> _FakeParallelEnv:
        call_order.append("pad_actions")
        env.action_spaces = {agent: Discrete(4) for agent in env.possible_agents}
        return env

    def fake_vectorize(env: DiscreteActionGuardParallelEnv) -> object:
        call_order.append("vectorize")
        captured["guard"] = env
        assert env.action_counts == {"small": 2, "large": 4}
        env.step({"small": 3, "large": 2})
        return object()

    def fake_concat(env: object, num_envs: int, *, base_class: str) -> object:
        call_order.append("concat")
        assert num_envs == 1
        assert base_class == "stable_baselines3"
        return SimpleNamespace(venv=SimpleNamespace(seed=lambda *_args: None))

    monkeypatch.setattr(rl_sumo_train, "_patch_sumo_rl_pettingzoo_compat", lambda: None)
    monkeypatch.setattr(sumo_rl, "parallel_env", fake_parallel_env)
    monkeypatch.setattr(supersuit, "pad_observations_v0", fake_pad_observations)
    monkeypatch.setattr(supersuit, "pad_action_space_v0", fake_pad_actions)
    monkeypatch.setattr(supersuit, "pettingzoo_env_to_vec_env_v1", fake_vectorize)
    monkeypatch.setattr(supersuit, "concat_vec_envs_v1", fake_concat)

    result = rl_sumo_train._build_training_env(
        args=SimpleNamespace(
            agent_mode="multi_agent",
            run_id="RUN-103-WIRING",
            seed=7,
            yellow_time=2,
            min_green=5,
            max_green=50,
            num_envs=1,
            memory="none",
            frame_stack_size=4,
        ),
        paths=SimpleNamespace(net=tmp_path / "toy.net.xml", routes=tmp_path / "toy.rou.xml"),
        log_dir=tmp_path / "logs",
        reward_fn=lambda _signal: 0.0,
        spec=SimpleNamespace(metadata=SimpleNamespace(horizon_seconds=20, time_step_seconds=6)),
    )

    assert call_order == [
        "parallel_env",
        "pad_observations",
        "pad_actions",
        "vectorize",
        "concat",
    ]
    assert isinstance(result, SimpleNamespace)
    assert raw_env.received_actions == {"small": 1, "large": 2}
    assert captured["guard"].event_log_path == (
        tmp_path / "logs" / "RUN-103-WIRING_action_interventions.jsonl"
    )
