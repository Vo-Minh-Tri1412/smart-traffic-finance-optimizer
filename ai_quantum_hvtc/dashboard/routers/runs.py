from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..context import DashboardContext, get_context
from ..jobs import JobRecord
from ..schemas import (
    IntersectionMetricModel,
    JobListResponse,
    JobStatus,
    MetricsSummary,
    RunCoverageResponse,
    RunDetail,
    RunListResponse,
    RunSummary,
    SimulationJobRequest,
    TracePage,
)
from ..services import DashboardServiceError, run_simulation, sumo_available
from ..store import RunNotFoundError, StoredRunMeta

router = APIRouter(tags=["runs"])

Ctx = Annotated[DashboardContext, Depends(get_context)]


def _metrics_summary(result: dict[str, Any]) -> MetricsSummary:
    return MetricsSummary(
        scenario_id=str(result.get("scenario_id", "")),
        controller_id=str(result.get("controller_id", "")),
        engine_id=str(result.get("engine_id", "")),
        seed=int(result.get("seed", 0)),
        total_vehicles=int(result.get("total_vehicles", 0)),
        throughput=int(result.get("throughput", 0)),
        total_waiting_time_seconds=float(result.get("total_waiting_time_seconds", 0.0)),
        average_waiting_time_seconds=float(result.get("average_waiting_time_seconds", 0.0)),
        max_queue_vehicles=float(result.get("max_queue_vehicles", 0.0)),
        average_queue_vehicles=float(result.get("average_queue_vehicles", 0.0)),
        stopped_vehicles=int(result.get("stopped_vehicles", 0)),
        emergency_delay_seconds=float(result.get("emergency_delay_seconds", 0.0)),
        bus_passenger_delay_seconds=_optional_float(result.get("bus_passenger_delay_seconds")),
        truck_delay_seconds=float(result.get("truck_delay_seconds", 0.0)),
        reroute_count=_optional_int(result.get("reroute_count")),
        failed_route_count=_optional_int(result.get("failed_route_count")),
        controller_interventions=int(result.get("controller_interventions", 0)),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _run_summary(ctx: DashboardContext, meta: StoredRunMeta) -> RunSummary | None:
    try:
        result = ctx.store.load_result_dict(meta.run_id)
    except RunNotFoundError:
        return None
    return RunSummary(
        run_id=meta.run_id,
        district_id=meta.district_id,
        scenario_id=meta.scenario_id,
        controller_id=meta.controller_id,
        engine_id=meta.engine_id,
        seed=meta.seed,
        created_at=meta.created_at,
        label=meta.label,
        trace_frames=meta.trace_frames,
        metrics=_metrics_summary(result),
    )


def _job_status(record: JobRecord) -> JobStatus:
    state = record.state
    if state not in {"queued", "running", "succeeded", "failed"}:
        state = "failed"
    return JobStatus(
        job_id=record.job_id,
        state=state,  # type: ignore[arg-type]
        run_id=record.run_id,
        error=record.error,
        created_at=record.created_at,
        finished_at=record.finished_at,
        request=record.request,
    )


@router.get("/runs", response_model=RunListResponse)
def list_runs(ctx: Ctx) -> RunListResponse:
    summaries = [_run_summary(ctx, meta) for meta in ctx.store.list_runs()]
    return RunListResponse(runs=[summary for summary in summaries if summary is not None])


@router.get("/runs/coverage", response_model=RunCoverageResponse)
def run_coverage(ctx: Ctx) -> RunCoverageResponse:
    return RunCoverageResponse(coverage=ctx.store.coverage())


@router.get("/runs/{run_id}", response_model=RunDetail)
def run_detail(run_id: str, ctx: Ctx) -> RunDetail:
    try:
        meta = ctx.store.get_meta(run_id)
        result = ctx.store.load_result_dict(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    intersections_raw = result.get("intersections", {})
    intersections: dict[str, IntersectionMetricModel] = {}
    if isinstance(intersections_raw, dict):
        for key, value in intersections_raw.items():
            if isinstance(value, dict):
                intersections[str(key)] = IntersectionMetricModel(**value)
    return RunDetail(
        run_id=meta.run_id,
        district_id=meta.district_id,
        scenario_id=meta.scenario_id,
        controller_id=meta.controller_id,
        engine_id=meta.engine_id,
        seed=meta.seed,
        created_at=meta.created_at,
        label=meta.label,
        trace_frames=meta.trace_frames,
        metrics=_metrics_summary(result),
        intersections=intersections,
    )


@router.get("/runs/{run_id}/trace", response_model=TracePage)
def run_trace(
    run_id: str,
    ctx: Ctx,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> TracePage:
    try:
        frames, total = ctx.store.read_trace(run_id, offset=offset, limit=limit)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TracePage(run_id=run_id, total_frames=total, offset=offset, limit=limit, frames=frames)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, ctx: Ctx) -> None:
    try:
        ctx.store.delete_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs", response_model=JobStatus, status_code=202)
def launch_run(request: SimulationJobRequest, ctx: Ctx) -> JobStatus:
    spec = ctx.spec_cache.get()
    if request.scenario_id not in spec.scenarios:
        raise HTTPException(status_code=422, detail=f"unknown scenario: {request.scenario_id}")
    if request.controller_id not in spec.controllers:
        raise HTTPException(status_code=422, detail=f"unknown controller: {request.controller_id}")
    if request.engine_id == "sumo":
        available, detail = sumo_available()
        if not available:
            raise HTTPException(status_code=409, detail=f"SUMO engine unavailable: {detail}")

    def runner(job_request: SimulationJobRequest) -> str:
        run_id = ctx.store.new_run_id(
            scenario_id=job_request.scenario_id,
            controller_id=job_request.controller_id,
            engine_id=job_request.engine_id,
        )
        sumo_work_dir = (
            ctx.store.run_dir(run_id) / "sumo" if job_request.engine_id == "sumo" else None
        )
        try:
            result = run_simulation(
                spec=spec,
                scenario_id=job_request.scenario_id,
                controller_id=job_request.controller_id,
                engine_id=job_request.engine_id,
                seed=job_request.seed,
                sumo_work_dir=sumo_work_dir,
            )
        except DashboardServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        meta = ctx.store.save_run(
            result=result,
            spec=spec,
            district_id=spec.metadata.district_id,
            label=job_request.label,
            run_id=run_id,
        )
        return meta.run_id

    record = ctx.jobs.submit(request, runner)
    return _job_status(record)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(ctx: Ctx) -> JobListResponse:
    return JobListResponse(jobs=[_job_status(record) for record in ctx.jobs.list_jobs()])


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_detail(job_id: str, ctx: Ctx) -> JobStatus:
    record = ctx.jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return _job_status(record)
