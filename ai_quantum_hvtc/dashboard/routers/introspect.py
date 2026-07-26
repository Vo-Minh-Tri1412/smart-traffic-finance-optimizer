from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..context import DashboardContext, get_context
from ..system import (
    DataResponse,
    DistrictsResponse,
    PipelineResponse,
    RLResponse,
    SystemStateResponse,
    build_data,
    build_districts,
    build_pipeline,
    build_rl,
    build_state,
)

router = APIRouter(tags=["system"])

Ctx = Annotated[DashboardContext, Depends(get_context)]


@router.get("/system/pipeline", response_model=PipelineResponse)
def system_pipeline(ctx: Ctx) -> PipelineResponse:
    return build_pipeline()


@router.get("/system/rl", response_model=RLResponse)
def system_rl(ctx: Ctx) -> RLResponse:
    return build_rl(
        config=ctx.config,
        spec=ctx.spec_cache.get(),
        models_dir=ctx.config.models_dir,
    )


@router.get("/system/data", response_model=DataResponse)
def system_data(ctx: Ctx) -> DataResponse:
    return build_data(config=ctx.config, store=ctx.store)


@router.get("/system/state", response_model=SystemStateResponse)
def system_state(ctx: Ctx) -> SystemStateResponse:
    return build_state(config=ctx.config, spec=ctx.spec_cache.get(), store=ctx.store)


@router.get("/districts", response_model=DistrictsResponse)
def districts(ctx: Ctx) -> DistrictsResponse:
    return build_districts(ctx.config)
