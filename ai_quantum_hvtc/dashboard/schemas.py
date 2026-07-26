from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EngineId = Literal["reference", "sumo"]
JobState = Literal["queued", "running", "succeeded", "failed"]
OptimizerAlgorithm = Literal["exact", "greedy"]


class EngineStatus(BaseModel):
    engine_id: str
    available: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: str
    service: str
    python_version: str
    district_id: str
    spec_path: str
    run_count: int
    engines: list[EngineStatus]


class MetricsSummary(BaseModel):
    scenario_id: str
    controller_id: str
    engine_id: str
    seed: int
    total_vehicles: int
    throughput: int
    total_waiting_time_seconds: float
    average_waiting_time_seconds: float
    max_queue_vehicles: float
    average_queue_vehicles: float
    stopped_vehicles: int
    emergency_delay_seconds: float
    bus_passenger_delay_seconds: float
    truck_delay_seconds: float
    reroute_count: int
    failed_route_count: int
    controller_interventions: int


class RunSummary(BaseModel):
    run_id: str
    district_id: str
    scenario_id: str
    controller_id: str
    engine_id: str
    seed: int
    created_at: str
    label: str = ""
    trace_frames: int = 0
    metrics: MetricsSummary


class IntersectionMetricModel(BaseModel):
    intersection_id: str
    delay_seconds: float
    queue_vehicles: float
    vehicles: int
    emergency_delay_seconds: float
    bus_passenger_delay_seconds: float
    truck_delay_seconds: float


class RunDetail(RunSummary):
    intersections: dict[str, IntersectionMetricModel] = Field(default_factory=dict)


class RunListResponse(BaseModel):
    runs: list[RunSummary]


class RunCoverageResponse(BaseModel):
    """scenario_id -> controller_id -> latest run_id, per engine."""

    coverage: dict[str, dict[str, dict[str, str]]]


class TracePage(BaseModel):
    run_id: str
    total_frames: int
    offset: int
    limit: int
    frames: list[dict[str, Any]]


class SimulationJobRequest(BaseModel):
    scenario_id: str
    controller_id: str
    engine_id: EngineId = "reference"
    seed: int = 42
    label: str = ""


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    run_id: str | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None
    request: SimulationJobRequest


class JobListResponse(BaseModel):
    jobs: list[JobStatus]


class CompareResponse(BaseModel):
    scenario_id: str
    engine_id: str
    baseline_controller_id: str
    rows: list[dict[str, Any]]


class CandidateScoreModel(BaseModel):
    scenario_id: str
    controller_id: str
    candidate_id: str
    intersection_id: str
    upgrade_type: str
    delay_saved_seconds: float
    emergency_delay_saved_seconds: float
    bus_passenger_delay_saved_seconds: float
    truck_delay_saved_seconds: float
    public_value_vnd: float
    capex_vnd: float
    annual_maintenance_vnd: float
    net_public_value_vnd: float
    benefit_cost_ratio: float
    caveat: str


class SelectedCandidateModel(BaseModel):
    candidate_id: str
    intersection_id: str
    cost_vnd: float
    value_vnd: float


class FinanceOptimizeRequest(BaseModel):
    budget_vnd: float = Field(gt=0)
    algorithm: OptimizerAlgorithm = "greedy"
    scenario_id: str
    controller_id: str = "rule_based"
    engine_id: EngineId = "reference"
    include_qubo: bool = False


class FinanceOptimizeResponse(BaseModel):
    scenario_id: str
    controller_id: str
    engine_id: str
    algorithm: str
    budget_vnd: float
    total_cost_vnd: float
    total_net_public_value_vnd: float
    scores: list[CandidateScoreModel]
    selected: list[SelectedCandidateModel]
    caveats: list[str]
    qubo: dict[str, dict[str, float]] | None = None


class DistrictResponse(BaseModel):
    metadata: dict[str, Any]
    zones: list[dict[str, Any]]
    intersections: list[dict[str, Any]]
    roads: list[dict[str, Any]]
    vehicle_types: list[dict[str, Any]]
    flows: list[dict[str, Any]]
    scenarios: list[dict[str, Any]]
    controllers: list[dict[str, Any]]
    investment_candidates: list[dict[str, Any]]
    finance_assumptions: dict[str, Any]
