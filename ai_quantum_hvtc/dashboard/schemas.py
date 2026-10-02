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
    bus_passenger_delay_seconds: float | None
    truck_delay_seconds: float
    reroute_count: int | None
    failed_route_count: int | None
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
    bus_passenger_delay_seconds: float | None = None
    truck_delay_seconds: float


class RunDetail(RunSummary):
    intersections: dict[str, IntersectionMetricModel] = Field(default_factory=dict)


class RunListResponse(BaseModel):
    runs: list[RunSummary]


class ExperimentListItem(BaseModel):
    experiment_id: str
    state: Literal["verified", "verification_failed"]
    content_sha256: str | None = None
    project_id: str | None = None
    mode: str | None = None
    discovered_run_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Direct child run-directory names; each run remains unverified until requested."
        ),
    )


class ExperimentListResponse(BaseModel):
    configured: bool
    status: Literal["not_configured", "available", "unavailable"]
    experiments: list[ExperimentListItem] = Field(default_factory=list)


class ExperimentOutputSummary(BaseModel):
    role: str
    state: Literal["verified", "unverified"]
    sha256: str | None = None
    bytes: int | None = None


class ExperimentRunVerification(BaseModel):
    configured: bool
    state: Literal[
        "not_configured",
        "unavailable",
        "not_found",
        "verification_failed",
        "unsealed",
        "outputs_verified",
    ]
    experiment_id: str | None = None
    run_id: str | None = None
    content_sha256: str | None = None
    mode: str | None = None
    case_id: str | None = None
    split: str | None = None
    seed: int | None = None
    controller_id: str | None = None
    outputs: list[ExperimentOutputSummary] = Field(default_factory=list)


class RuntimeDemandAccountingView(BaseModel):
    status: Literal["available", "partial", "unavailable"]
    scope: Literal["per_intended_requested_vehicle_trip"]
    reason: str | None
    intended_trip_count: int | None
    raw_ledger_row_count: int | None
    status_counts: dict[str, int | None]
    tripinfo_observed_count: int | None
    tripinfo_unfinished_requested: bool | None


class RuntimeSummaryAccountingView(BaseModel):
    status: Literal["available", "partial", "unavailable"]
    final_step_time_seconds: float | None
    loaded: int | None
    inserted: int | None
    waiting: int | None
    arrived: int | None
    running: int | None
    ended: int | None


class RuntimeStatisticAccountingView(BaseModel):
    status: Literal["available", "partial", "unavailable"]
    total_teleports: int | None
    safety_collisions: int | None


class RuntimeAggregateAccountingView(BaseModel):
    scope: Literal["whole_simulation_vehicle_and_event_counters"]
    status: Literal["available", "partial", "unavailable"]
    summary: RuntimeSummaryAccountingView
    statistic: RuntimeStatisticAccountingView
    limitations: list[str]


class RuntimeTripAccountingView(BaseModel):
    execution_status: Literal[
        "debug_simulation_finished",
        "debug_simulation_failed_or_partial",
    ]
    evidence_scope: Literal["managed_debug_runtime_accounting_only"]
    demand_accounting: RuntimeDemandAccountingView
    aggregate_simulation_accounting: RuntimeAggregateAccountingView


class ExperimentRuntimeAccountingResponse(BaseModel):
    configured: bool
    state: Literal[
        "not_configured",
        "unavailable",
        "not_found",
        "unsealed",
        "verification_failed",
        "available",
    ]
    experiment_id: str | None = None
    run_id: str | None = None
    accounting: RuntimeTripAccountingView | None = None


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
