from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..context import DashboardContext, get_context
from ..schemas import (
    CandidateScoreModel,
    FinanceOptimizeRequest,
    FinanceOptimizeResponse,
    SelectedCandidateModel,
)
from ..services import DashboardServiceError, optimize_budget, score_investments
from ..store import RunStoreError

router = APIRouter(tags=["finance"])

Ctx = Annotated[DashboardContext, Depends(get_context)]

_STANDING_CAVEATS = [
    "Giá trị tài chính dùng giả định demo (placeholder); nhóm Kinh tế phải duyệt trước khi "
    "dùng làm kết luận chính sách.",
    "Metric mô phỏng đến từ engine tham chiếu/SUMO; chưa phải bằng chứng tiết kiệm thực tế.",
]


@router.post("/finance/optimize", response_model=FinanceOptimizeResponse)
def optimize(request: FinanceOptimizeRequest, ctx: Ctx) -> FinanceOptimizeResponse:
    spec = ctx.spec_cache.get()
    try:
        scores = score_investments(
            store=ctx.store,
            spec=spec,
            scenario_id=request.scenario_id,
            controller_id=request.controller_id,
            engine_id=request.engine_id,
        )
        selected, qubo = optimize_budget(
            scores=scores,
            budget_vnd=request.budget_vnd,
            algorithm=request.algorithm,
            include_qubo=request.include_qubo,
        )
    except RunStoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DashboardServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    intersection_by_candidate = {score.candidate_id: score.intersection_id for score in scores}
    caveats = list(
        dict.fromkeys([score.caveat for score in scores if score.caveat] + _STANDING_CAVEATS)
    )
    return FinanceOptimizeResponse(
        scenario_id=request.scenario_id,
        controller_id=request.controller_id,
        engine_id=request.engine_id,
        algorithm=request.algorithm,
        budget_vnd=request.budget_vnd,
        total_cost_vnd=round(sum(option.cost_vnd for option in selected), 3),
        total_net_public_value_vnd=round(sum(option.value_vnd for option in selected), 3),
        scores=[CandidateScoreModel(**asdict(score)) for score in scores],
        selected=[
            SelectedCandidateModel(
                candidate_id=option.candidate_id,
                intersection_id=intersection_by_candidate.get(option.candidate_id, ""),
                cost_vnd=round(option.cost_vnd, 3),
                value_vnd=round(option.value_vnd, 3),
            )
            for option in selected
        ],
        caveats=caveats,
        qubo=qubo,
    )
