from __future__ import annotations

import sys
from typing import Annotated

from fastapi import APIRouter, Depends

from ..context import DashboardContext, get_context
from ..schemas import EngineStatus, HealthResponse
from ..services import sumo_available

router = APIRouter(tags=["system"])

Ctx = Annotated[DashboardContext, Depends(get_context)]


@router.get("/health", response_model=HealthResponse)
def health(ctx: Ctx) -> HealthResponse:
    sumo_ok, sumo_detail = sumo_available()
    spec = ctx.spec_cache.get()
    return HealthResponse(
        status="ok",
        service="ai-quantum-hvtc dashboard",
        python_version=(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        district_id=spec.metadata.district_id,
        spec_path=str(ctx.spec_cache.spec_path),
        run_count=len(ctx.store.list_runs()),
        engines=[
            EngineStatus(engine_id="reference", available=True, detail="in-process graph engine"),
            EngineStatus(engine_id="sumo", available=sumo_ok, detail=sumo_detail),
        ],
    )
