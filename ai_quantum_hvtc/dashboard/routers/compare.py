from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..context import DashboardContext, get_context
from ..schemas import CompareResponse
from ..services import compare_controllers
from ..store import RunStoreError

router = APIRouter(tags=["compare"])

Ctx = Annotated[DashboardContext, Depends(get_context)]


@router.get("/compare", response_model=CompareResponse)
def compare(
    ctx: Ctx,
    scenario_id: Annotated[str, Query(min_length=1)],
    engine_id: Annotated[str, Query()] = "reference",
) -> CompareResponse:
    try:
        baseline_controller_id, rows = compare_controllers(
            store=ctx.store,
            scenario_id=scenario_id,
            engine_id=engine_id,
        )
    except RunStoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CompareResponse(
        scenario_id=scenario_id,
        engine_id=engine_id,
        baseline_controller_id=baseline_controller_id,
        rows=rows,
    )
