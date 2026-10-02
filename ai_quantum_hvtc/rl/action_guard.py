from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from numbers import Integral, Real
from pathlib import Path
from typing import Any

from gymnasium.spaces import Discrete
from pettingzoo.utils.env import ParallelEnv
from pettingzoo.utils.wrappers import BaseParallelWrapper


class ActionGuardError(RuntimeError):
    """Raised when an invalid action cannot be replaced with a safe current phase."""


def capture_discrete_action_counts(env: ParallelEnv[str, Any, Any]) -> dict[str, int]:
    """Capture each agent's local action count before a padding wrapper changes it."""

    counts: dict[str, int] = {}
    for agent in env.possible_agents:
        action_space = env.action_space(agent)
        if not isinstance(action_space, Discrete):
            raise ValueError(
                f"Action guard requires a Discrete space for agent {agent!r}; "
                f"got {type(action_space).__name__}."
            )
        if isinstance(action_space.n, bool) or not isinstance(action_space.n, Integral):
            raise ValueError(f"Action space size for agent {agent!r} must be an integer.")
        legal_n = int(action_space.n)
        if legal_n < 1:
            raise ValueError(f"Action space size for agent {agent!r} must be positive.")
        counts[agent] = legal_n
    return counts


def validate_action_interval(*, delta_time: int, yellow_time: int) -> None:
    """Reject action intervals that could request a phase before yellow clearance ends."""

    if isinstance(delta_time, bool) or not isinstance(delta_time, Integral) or delta_time < 1:
        raise ValueError("Training delta_time must be a positive integer.")
    if isinstance(yellow_time, bool) or not isinstance(yellow_time, Integral) or yellow_time < 0:
        raise ValueError("Training yellow_time must be a non-negative integer.")
    # SUMO-RL 1.4.5 itself asserts delta_time > yellow_time during construction.
    if delta_time <= yellow_time:
        raise ValueError(
            "Training delta_time must be greater than yellow_time so a policy action "
            "cannot interrupt yellow clearance."
        )


class DiscreteActionGuardParallelEnv(BaseParallelWrapper[str, Any, Any]):
    """Reject padded/local-invalid actions and hold the current green when resolvable."""

    def __init__(
        self,
        env: ParallelEnv[str, Any, Any],
        *,
        action_counts: Mapping[str, int],
        phase_source: object,
        event_log_path: Path | str,
        run_id: str,
    ) -> None:
        self.action_counts = dict(action_counts)
        self.phase_source = phase_source
        self.event_log_path = Path(event_log_path)
        self.run_id = run_id
        self.env_instance_id: str | None = None
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.event_log_path.open("x", encoding="utf-8"):
                pass
        except FileExistsError as exc:
            with suppress(Exception):
                env.close()
            raise ActionGuardError(
                f"Action intervention log already exists for this run: {self.event_log_path}"
            ) from exc
        except OSError as exc:
            with suppress(Exception):
                env.close()
            raise ActionGuardError(
                f"Cannot reserve action intervention log {self.event_log_path}: {exc}"
            ) from exc
        super().__init__(env)

    def step(
        self,
        actions: dict[str, Any],
    ) -> tuple[
        dict[str, Any],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        env_instance_id = self._ensure_env_instance_id()
        sanitized_actions = dict(actions)
        events_by_agent: dict[str, list[dict[str, Any]]] = {}
        unresolved: list[str] = []

        for agent, action in actions.items():
            legal_n = self.action_counts.get(agent)
            reason = self._invalid_action_reason(agent, action, legal_n)
            if reason is None:
                continue

            phase, reported_phase, resolution_reason = self._resolve_current_green(agent, legal_n)
            can_hold = phase is not None
            event: dict[str, Any] = {
                "schema": "rl_action_intervention.v1",
                "run_id": self.run_id,
                "env_instance_id": env_instance_id,
                "agent": str(agent),
                "action": _json_value(action),
                "legal_n": legal_n,
                "current_phase": reported_phase,
                "time": self._simulation_time(),
                "reason": reason,
                "resolution": "held_current_green" if can_hold else "failed_closed",
                "resolution_reason": resolution_reason,
                "submission_state": "not_attempted",
                "step_outcome": "not_started",
            }
            events_by_agent.setdefault(agent, []).append(event)

            if phase is None:
                unresolved.append(f"{agent}: {resolution_reason}")
            else:
                sanitized_actions[agent] = phase

        if unresolved:
            details = "; ".join(unresolved)
            for events in events_by_agent.values():
                for event in events:
                    event["resolution"] = "failed_closed"
                    if event["resolution_reason"] is None:
                        event["resolution_reason"] = "batch_aborted_due_to_unresolved_action"
            self._persist_interventions(events_by_agent)
            raise ActionGuardError(
                "Refusing to advance SUMO because the current green phase could not be "
                f"resolved for invalid actions ({details})."
            )

        # Persist the intent before stepping: an I/O failure must never allow SUMO
        # to advance without a durable record that a replacement was submitted.
        for events in events_by_agent.values():
            for event in events:
                event["submission_state"] = "attempted"
                event["step_outcome"] = "unverified"
        self._persist_interventions(events_by_agent)

        try:
            observations, rewards, terminations, truncations, infos = super().step(
                sanitized_actions
            )
        except Exception:
            outcomes = [
                {
                    "schema": "rl_action_intervention_outcome.v1",
                    "run_id": self.run_id,
                    "env_instance_id": env_instance_id,
                    "agent": event["agent"],
                    "step_outcome": "step_failed",
                    "reason": "parallel_environment_step_failed",
                }
                for events in events_by_agent.values()
                for event in events
            ]
            with suppress(Exception):
                self._append_events(outcomes)
            raise
        infos = dict(infos)
        for agent, events in events_by_agent.items():
            info = dict(infos.get(agent, {}))
            existing = info.get("action_guard_interventions", [])
            interventions = list(existing) if isinstance(existing, list) else []
            interventions.extend(dict(event) for event in events)
            info["action_guard_interventions"] = interventions
            infos[agent] = info

        return observations, rewards, terminations, truncations, infos

    def _invalid_action_reason(self, agent: str, action: object, legal_n: int | None) -> str | None:
        if legal_n is None:
            return "unknown_agent"
        if isinstance(action, bool) or not isinstance(action, Integral):
            return "non_integer_action"
        value = int(action)
        if value < 0:
            return "negative_action"
        if value >= legal_n:
            padded_n = _discrete_action_count(self.env.action_space(agent))
            return "padded_action" if value < padded_n else "action_out_of_range"
        return None

    def _resolve_current_green(
        self, agent: str, legal_n: int | None
    ) -> tuple[int | None, int | None, str | None]:
        signal = _find_traffic_signal(self.phase_source, agent)
        if signal is None:
            return None, None, "traffic_signal_unavailable"

        raw_phase = getattr(signal, "green_phase", None)
        if getattr(signal, "is_yellow", None) is not False:
            return None, None, "signal_not_confirmed_in_green_phase"
        if isinstance(raw_phase, bool) or not isinstance(raw_phase, Integral):
            return None, None, "current_phase_missing_or_non_integer"

        phase = int(raw_phase)
        if legal_n is None or phase < 0 or phase >= legal_n:
            return None, phase, "current_phase_out_of_range"
        return phase, phase, None

    def _simulation_time(self) -> float | int | None:
        for candidate in _walk_environment(self.phase_source):
            try:
                value = getattr(candidate, "sim_step", None)
            except Exception:
                continue
            if isinstance(value, bool) or not isinstance(value, Real):
                continue
            numeric = float(value)
            if math.isfinite(numeric):
                return int(numeric) if numeric.is_integer() else numeric
        return None

    def _persist_interventions(self, events_by_agent: Mapping[str, list[dict[str, Any]]]) -> None:
        events = [event for agent_events in events_by_agent.values() for event in agent_events]
        try:
            self._append_events(events)
        except Exception as exc:
            raise ActionGuardError(
                f"Cannot persist action intervention log {self.event_log_path}; "
                "refusing to advance SUMO."
            ) from exc

    def _append_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        if not events:
            return
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()

    def _ensure_env_instance_id(self) -> str:
        if self.env_instance_id is None:
            self.env_instance_id = uuid.uuid4().hex
        return self.env_instance_id

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        # SuperSuit cloudpickle-clones guarded environments for vectorization.
        # Each clone must identify itself after deserialization, not inherit the
        # source instance's event identity.
        state["env_instance_id"] = None
        return state


def _find_traffic_signal(source: object, agent: str) -> object | None:
    for candidate in _walk_environment(source):
        try:
            signals = getattr(candidate, "traffic_signals", None)
        except Exception:
            continue
        if isinstance(signals, Mapping) and agent in signals:
            return signals[agent]
    return None


def _walk_environment(source: object) -> list[object]:
    pending = [source]
    visited: set[int] = set()
    result: list[object] = []
    while pending:
        candidate = pending.pop()
        if id(candidate) in visited:
            continue
        visited.add(id(candidate))
        result.append(candidate)
        for name in ("env", "aec_env", "unwrapped"):
            try:
                nested = getattr(candidate, name, None)
            except Exception:
                continue
            if nested is not None and nested is not candidate:
                pending.append(nested)
    return result


def _discrete_action_count(action_space: object) -> int:
    if not isinstance(action_space, Discrete):
        return 0
    return int(action_space.n)


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else repr(value)
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return repr(value)
    return value
