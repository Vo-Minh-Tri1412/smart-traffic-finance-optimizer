from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from .config import DashboardConfig
from .jobs import JobManager
from .services import SpecCache
from .store import RunStore


@dataclass
class DashboardContext:
    """Shared service container attached to the FastAPI app state."""

    config: DashboardConfig
    store: RunStore
    spec_cache: SpecCache
    jobs: JobManager


def get_context(request: Request) -> DashboardContext:
    ctx = getattr(request.app.state, "ctx", None)
    if not isinstance(ctx, DashboardContext):
        raise RuntimeError("dashboard context is not initialized")
    return ctx
