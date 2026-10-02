from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import DashboardConfig, config_from_env
from .context import DashboardContext
from .jobs import JobManager
from .routers import (
    compare_router,
    district_router,
    experiments_router,
    finance_router,
    introspect_router,
    runs_router,
    system_router,
)
from .services import SpecCache, seed_demo_runs
from .store import RunStore

API_PREFIX = "/api"


def create_app(config: DashboardConfig | None = None) -> FastAPI:
    resolved = config or config_from_env()
    store = RunStore(resolved.runs_dir)
    spec_cache = SpecCache(resolved.spec_path)
    jobs = JobManager()
    ctx = DashboardContext(config=resolved, store=store, spec_cache=spec_cache, jobs=jobs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.ensure_dirs()
        if resolved.seed_demo_runs:
            thread = threading.Thread(
                target=seed_demo_runs,
                kwargs={
                    "store": store,
                    "spec_cache": spec_cache,
                    "scenarios": resolved.demo_seed_scenarios,
                    "controllers": resolved.demo_seed_controllers,
                },
                name="dash-demo-seed",
                daemon=True,
            )
            thread.start()
        yield
        jobs.shutdown()

    app = FastAPI(
        title="AI Quantum HVTC Dashboard",
        description=(
            "Backend dashboard for the smart-traffic public-finance system: "
            "district spec, simulation runs, trace replay, controller comparison, "
            "and budget-constrained investment optimization."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.ctx = ctx

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (
        system_router,
        district_router,
        runs_router,
        experiments_router,
        compare_router,
        finance_router,
        introspect_router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    index_html = resolved.frontend_dist / "index.html"
    if index_html.exists():
        app.mount(
            "/",
            StaticFiles(directory=resolved.frontend_dist, html=True),
            name="frontend",
        )

    return app


def get_app() -> FastAPI:
    """Uvicorn factory entrypoint: ``uvicorn ai_quantum_hvtc.dashboard.app:get_app``."""

    return create_app()
