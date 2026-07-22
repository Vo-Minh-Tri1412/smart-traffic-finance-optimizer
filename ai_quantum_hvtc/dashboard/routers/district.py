from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends

from ..context import DashboardContext, get_context
from ..schemas import DistrictResponse
from ..services import district_payload

router = APIRouter(tags=["district"])

Ctx = Annotated[DashboardContext, Depends(get_context)]


@router.get("/district", response_model=DistrictResponse)
def district(ctx: Ctx) -> DistrictResponse:
    payload = cast(dict[str, Any], district_payload(ctx.spec_cache.get()))
    return DistrictResponse(**payload)
