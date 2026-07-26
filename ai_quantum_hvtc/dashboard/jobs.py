from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from .schemas import SimulationJobRequest


class JobRunner(Protocol):
    def __call__(self, request: SimulationJobRequest, /) -> str:
        """Execute the job and return the created run id."""
        ...


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    request: SimulationJobRequest
    state: str = "queued"
    run_id: str | None = None
    error: str | None = None
    created_at: str = ""
    finished_at: str | None = None
    _order: int = field(default=0, compare=False)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class JobManager:
    """Tracks background simulation jobs executed on a small worker pool."""

    def __init__(self, max_workers: int = 2, history_limit: int = 100) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dash-job")
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._counter = 0
        self._history_limit = history_limit

    def submit(self, request: SimulationJobRequest, runner: JobRunner) -> JobRecord:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._counter += 1
            record = JobRecord(
                job_id=job_id,
                request=request,
                state="queued",
                created_at=_now(),
                _order=self._counter,
            )
            self._jobs[job_id] = record
            self._trim_locked()
        self._executor.submit(self._execute, job_id, request, runner)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job._order, reverse=True)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _execute(self, job_id: str, request: SimulationJobRequest, runner: JobRunner) -> None:
        self._update(job_id, state="running")
        try:
            run_id = runner(request)
        except Exception as exc:  # noqa: BLE001 - job errors surface via the API
            self._update(job_id, state="failed", error=str(exc), finished_at=_now())
            return
        self._update(job_id, state="succeeded", run_id=run_id, finished_at=_now())

    def _update(
        self,
        job_id: str,
        *,
        state: str,
        run_id: str | None = None,
        error: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return
            self._jobs[job_id] = replace(
                current,
                state=state,
                run_id=run_id if run_id is not None else current.run_id,
                error=error if error is not None else current.error,
                finished_at=finished_at if finished_at is not None else current.finished_at,
            )

    def _trim_locked(self) -> None:
        if len(self._jobs) <= self._history_limit:
            return
        finished = [
            job
            for job in sorted(self._jobs.values(), key=lambda item: item._order)
            if job.state in {"succeeded", "failed"}
        ]
        overflow = len(self._jobs) - self._history_limit
        for job in finished[:overflow]:
            self._jobs.pop(job.job_id, None)
