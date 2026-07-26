from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.reports import result_to_json, result_to_trace_jsonl
from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.metrics import IntersectionMetric, SimulationResult

META_FILE = "meta.json"
RESULT_FILE = "result.json"
TRACE_FILE = "trace.jsonl"

_RESULT_FIELDS = {item.name for item in fields(SimulationResult)}
_INTERSECTION_FIELDS = {item.name for item in fields(IntersectionMetric)}


@dataclass(frozen=True)
class StoredRunMeta:
    run_id: str
    district_id: str
    scenario_id: str
    controller_id: str
    engine_id: str
    seed: int
    created_at: str
    label: str = ""
    trace_frames: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "district_id": self.district_id,
            "scenario_id": self.scenario_id,
            "controller_id": self.controller_id,
            "engine_id": self.engine_id,
            "seed": self.seed,
            "created_at": self.created_at,
            "label": self.label,
            "trace_frames": self.trace_frames,
        }


def result_from_dict(data: dict[str, Any]) -> SimulationResult:
    """Rebuild a SimulationResult from its stored ``result.json`` payload."""

    intersections_raw = data.get("intersections", {})
    intersections = {
        key: IntersectionMetric(
            **{name: value[name] for name in _INTERSECTION_FIELDS if name in value}
        )
        for key, value in intersections_raw.items()
        if isinstance(value, dict)
    }
    kwargs = {
        name: data[name]
        for name in _RESULT_FIELDS
        if name in data and name not in {"intersections", "vehicle_trace_frames"}
    }
    return SimulationResult(**kwargs, intersections=intersections)


class RunStoreError(Exception):
    pass


class RunNotFoundError(RunStoreError):
    pass


class RunStore:
    """Filesystem-backed index of dashboard simulation runs.

    Layout: ``<runs_dir>/<run_id>/{meta.json,result.json,trace.jsonl}``.
    """

    def __init__(self, runs_dir: Path) -> None:
        self._runs_dir = runs_dir

    @property
    def runs_dir(self) -> Path:
        return self._runs_dir

    def ensure_dirs(self) -> None:
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def new_run_id(self, *, scenario_id: str, controller_id: str, engine_id: str) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        return f"{stamp}-{scenario_id}-{controller_id}-{engine_id}-{suffix}"

    def run_dir(self, run_id: str) -> Path:
        if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
            raise RunNotFoundError(f"invalid run id: {run_id!r}")
        return self._runs_dir / run_id

    def save_run(
        self,
        *,
        result: SimulationResult,
        spec: DistrictSpec,
        district_id: str,
        label: str = "",
        run_id: str | None = None,
    ) -> StoredRunMeta:
        resolved_run_id = run_id or self.new_run_id(
            scenario_id=result.scenario_id,
            controller_id=result.controller_id,
            engine_id=result.engine_id,
        )
        target = self.run_dir(resolved_run_id)
        target.mkdir(parents=True, exist_ok=True)
        result_to_json(result, target / RESULT_FILE)
        result_to_trace_jsonl(result, spec, target / TRACE_FILE)
        trace_frames = _count_lines(target / TRACE_FILE)
        meta = StoredRunMeta(
            run_id=resolved_run_id,
            district_id=district_id,
            scenario_id=result.scenario_id,
            controller_id=result.controller_id,
            engine_id=result.engine_id,
            seed=result.seed,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            label=label,
            trace_frames=trace_frames,
        )
        (target / META_FILE).write_text(
            json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return meta

    def list_runs(self) -> list[StoredRunMeta]:
        if not self._runs_dir.exists():
            return []
        metas: list[StoredRunMeta] = []
        for child in self._runs_dir.iterdir():
            meta = self._load_meta(child)
            if meta is not None:
                metas.append(meta)
        metas.sort(key=lambda item: item.created_at, reverse=True)
        return metas

    def get_meta(self, run_id: str) -> StoredRunMeta:
        meta = self._load_meta(self.run_dir(run_id))
        if meta is None:
            raise RunNotFoundError(f"run not found: {run_id}")
        return meta

    def load_result_dict(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / RESULT_FILE
        if not path.exists():
            raise RunNotFoundError(f"run result not found: {run_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RunStoreError(f"run result is not an object: {run_id}")
        return payload

    def load_result(self, run_id: str) -> SimulationResult:
        return result_from_dict(self.load_result_dict(run_id))

    def read_trace(
        self,
        run_id: str,
        *,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[list[dict[str, Any]], int]:
        path = self.run_dir(run_id) / TRACE_FILE
        if not path.exists():
            raise RunNotFoundError(f"run trace not found: {run_id}")
        frames: list[dict[str, Any]] = []
        total = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                if total >= offset and len(frames) < limit:
                    frame = json.loads(stripped)
                    if isinstance(frame, dict):
                        frames.append(frame)
                total += 1
        return frames, total

    def delete_run(self, run_id: str) -> None:
        target = self.run_dir(run_id)
        if not (target / META_FILE).exists():
            raise RunNotFoundError(f"run not found: {run_id}")
        shutil.rmtree(target)

    def latest_by_controller(
        self,
        *,
        scenario_id: str,
        engine_id: str,
    ) -> dict[str, StoredRunMeta]:
        latest: dict[str, StoredRunMeta] = {}
        for meta in self.list_runs():
            if meta.scenario_id != scenario_id or meta.engine_id != engine_id:
                continue
            current = latest.get(meta.controller_id)
            if current is None or meta.created_at > current.created_at:
                latest[meta.controller_id] = meta
        return latest

    def coverage(self) -> dict[str, dict[str, dict[str, str]]]:
        """engine_id -> scenario_id -> controller_id -> latest run_id."""

        coverage: dict[str, dict[str, dict[str, StoredRunMeta]]] = {}
        for meta in self.list_runs():
            by_scenario = coverage.setdefault(meta.engine_id, {})
            by_controller = by_scenario.setdefault(meta.scenario_id, {})
            current = by_controller.get(meta.controller_id)
            if current is None or meta.created_at > current.created_at:
                by_controller[meta.controller_id] = meta
        return {
            engine_id: {
                scenario_id: {
                    controller_id: meta.run_id for controller_id, meta in controllers.items()
                }
                for scenario_id, controllers in scenarios.items()
            }
            for engine_id, scenarios in coverage.items()
        }

    def _load_meta(self, run_dir: Path) -> StoredRunMeta | None:
        meta_path = run_dir / META_FILE
        if not run_dir.is_dir() or not meta_path.exists():
            return None
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return StoredRunMeta(
                run_id=str(payload["run_id"]),
                district_id=str(payload.get("district_id", "")),
                scenario_id=str(payload["scenario_id"]),
                controller_id=str(payload["controller_id"]),
                engine_id=str(payload["engine_id"]),
                seed=int(payload.get("seed", 0)),
                created_at=str(payload.get("created_at", "")),
                label=str(payload.get("label", "")),
                trace_frames=int(payload.get("trace_frames", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())
