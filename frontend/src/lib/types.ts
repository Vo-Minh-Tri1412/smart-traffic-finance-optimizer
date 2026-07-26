// TypeScript mirrors of the backend dashboard API schemas
// (ai_quantum_hvtc/dashboard/schemas.py).

export type EngineId = "reference" | "sumo";
export type JobState = "queued" | "running" | "succeeded" | "failed";
export type OptimizerAlgorithm = "exact" | "greedy";

export interface EngineStatus {
  engine_id: string;
  available: boolean;
  detail: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  python_version: string;
  district_id: string;
  spec_path: string;
  run_count: number;
  engines: EngineStatus[];
}

export interface MetricsSummary {
  scenario_id: string;
  controller_id: string;
  engine_id: string;
  seed: number;
  total_vehicles: number;
  throughput: number;
  total_waiting_time_seconds: number;
  average_waiting_time_seconds: number;
  max_queue_vehicles: number;
  average_queue_vehicles: number;
  stopped_vehicles: number;
  emergency_delay_seconds: number;
  bus_passenger_delay_seconds: number;
  truck_delay_seconds: number;
  reroute_count: number;
  failed_route_count: number;
  controller_interventions: number;
}

export interface RunSummary {
  run_id: string;
  district_id: string;
  scenario_id: string;
  controller_id: string;
  engine_id: string;
  seed: number;
  created_at: string;
  label: string;
  trace_frames: number;
  metrics: MetricsSummary;
}

export interface IntersectionMetric {
  intersection_id: string;
  delay_seconds: number;
  queue_vehicles: number;
  vehicles: number;
  emergency_delay_seconds: number;
  bus_passenger_delay_seconds: number;
  truck_delay_seconds: number;
}

export interface RunDetail extends RunSummary {
  intersections: Record<string, IntersectionMetric>;
}

export interface TraceEvent {
  type: string;
  [key: string]: unknown;
}

export interface TraceIntersectionQueue {
  intersection_id: string;
  queue_vehicles: number;
  delay_seconds: number;
}

export interface TraceFrame {
  schema_version: string;
  timestep: number;
  time_seconds: number;
  district_id: string;
  scenario_id: string;
  controller_id: string;
  engine_id: string;
  traffic_lights?: Record<string, string>;
  intersection_queues?: TraceIntersectionQueue[];
  road_occupancy?: unknown[];
  events?: TraceEvent[];
  metrics?: Record<string, number>;
  vehicles?: TraceVehicle[];
}

export interface TraceVehicle {
  vehicle_id: string;
  vehicle_type: string;
  x: number;
  y: number;
  speed: number;
  angle: number;
  lane_id?: string;
  road_id?: string;
}

export interface TracePage {
  run_id: string;
  total_frames: number;
  offset: number;
  limit: number;
  frames: TraceFrame[];
}

export interface SimulationJobRequest {
  scenario_id: string;
  controller_id: string;
  engine_id: EngineId;
  seed: number;
  label: string;
}

export interface JobStatus {
  job_id: string;
  state: JobState;
  run_id: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  request: SimulationJobRequest;
}

export interface CompareResponse {
  scenario_id: string;
  engine_id: string;
  baseline_controller_id: string;
  rows: CompareRow[];
}

export interface CompareRow {
  scenario_id: string;
  controller_id: string;
  engine_id: string;
  total_vehicles: number;
  throughput: number;
  average_waiting_time_seconds: number;
  total_waiting_time_seconds: number;
  max_queue_vehicles: number;
  average_queue_vehicles: number;
  stopped_vehicles: number;
  emergency_delay_seconds: number;
  bus_passenger_delay_seconds: number;
  truck_delay_seconds: number;
  controller_interventions: number;
  waiting_time_saved_vs_fixed_seconds: number;
  waiting_time_saved_vs_fixed_pct: number;
  throughput_gain_vs_fixed: number;
  emergency_delay_saved_vs_fixed_seconds: number;
  bus_passenger_delay_saved_vs_fixed_seconds: number;
  truck_delay_saved_vs_fixed_seconds: number;
  interpretation: string;
}

export interface CandidateScore {
  scenario_id: string;
  controller_id: string;
  candidate_id: string;
  intersection_id: string;
  upgrade_type: string;
  delay_saved_seconds: number;
  emergency_delay_saved_seconds: number;
  bus_passenger_delay_saved_seconds: number;
  truck_delay_saved_seconds: number;
  public_value_vnd: number;
  capex_vnd: number;
  annual_maintenance_vnd: number;
  net_public_value_vnd: number;
  benefit_cost_ratio: number;
  caveat: string;
}

export interface SelectedCandidate {
  candidate_id: string;
  intersection_id: string;
  cost_vnd: number;
  value_vnd: number;
}

export interface FinanceOptimizeRequest {
  budget_vnd: number;
  algorithm: OptimizerAlgorithm;
  scenario_id: string;
  controller_id: string;
  engine_id: EngineId;
  include_qubo?: boolean;
}

export interface FinanceOptimizeResponse {
  scenario_id: string;
  controller_id: string;
  engine_id: string;
  algorithm: string;
  budget_vnd: number;
  total_cost_vnd: number;
  total_net_public_value_vnd: number;
  scores: CandidateScore[];
  selected: SelectedCandidate[];
  caveats: string[];
  qubo: Record<string, Record<string, number>> | null;
}

export interface DistrictZone {
  id: string;
  name: string;
  type: string;
  intersection_ids: string[];
  economic_role: string;
  peak_windows: string[];
}

export interface DistrictIntersection {
  id: string;
  name: string;
  x: number;
  y: number;
  tags: string[];
  signalized: boolean;
}

export interface DistrictRoad {
  id: string;
  from: string;
  to: string;
  length_km: number;
  speed_kph: number;
  lanes: number;
  capacity: number;
  tags: string[];
  truck_allowed: boolean;
}

export interface DistrictScenario {
  id: string;
  name: string;
  description: string;
  flow_multipliers: Record<string, number>;
  road_capacity_multipliers: Record<string, number>;
  closed_roads: string[];
}

export interface DistrictController {
  id: string;
  name: string;
  type: string;
}

export interface InvestmentCandidate {
  id: string;
  intersection_id: string;
  upgrade_type: string;
  capex_vnd: number;
  annual_maintenance_vnd: number;
  affected_flow_ids: string[];
  caveat: string;
}

export interface DistrictFlow {
  id: string;
  origin_zone: string;
  destination_zone: string;
  trip_purpose: string;
  departure_start: number;
  departure_end: number;
  base_volume: number;
  vehicle_mix: Record<string, number>;
  route_policy: string;
}

export interface DistrictResponse {
  metadata: {
    id: string;
    name: string;
    version: string;
    horizon_seconds: number;
    time_step_seconds: number;
  };
  zones: DistrictZone[];
  intersections: DistrictIntersection[];
  roads: DistrictRoad[];
  vehicle_types: {
    id: string;
    passenger_count: number;
    pcu: number;
    value_class: string;
    priority_level: number;
  }[];
  flows: DistrictFlow[];
  scenarios: DistrictScenario[];
  controllers: DistrictController[];
  investment_candidates: InvestmentCandidate[];
  finance_assumptions: Record<string, unknown> & {
    value_of_time_vnd_per_hour?: number;
    status?: Record<string, string>;
  };
}

export interface RunCoverageResponse {
  coverage: Record<string, Record<string, Record<string, string>>>;
}

// --- System introspection (ai_quantum_hvtc/dashboard/system.py) ---

export type StageStatus = "implemented" | "partial" | "scaffold" | "planned";
export type CheckStatus = "ok" | "warn" | "fail";

export interface PipelineStage {
  id: string;
  name: string;
  layer: string;
  status: StageStatus;
  summary: string;
  inputs: string[];
  outputs: string[];
  modules: string[];
}

export interface PipelineResponse {
  layers: string[];
  stages: PipelineStage[];
  status_legend: Record<string, string>;
}

export interface RewardWeightRow {
  key: string;
  weight: number;
}

export interface HardConstraint {
  id: string;
  type: string;
  enforcement: string;
  status: string;
  vehicle_types: string[];
  notes: string;
}

export interface RewardProfile {
  profile_id: string;
  status: string;
  owner: string;
  description: string;
  source_path: string;
  loaded: boolean;
  base_weights: RewardWeightRow[];
  vehicle_type_weights: RewardWeightRow[];
  trip_purpose_weights: RewardWeightRow[];
  scenario_weights: RewardWeightRow[];
  route_priority_weights: {
    flow_id: string;
    weight: number;
    description: string;
  }[];
  time_window_weights: {
    label: string;
    start: number;
    end: number;
    weight: number;
    flow_ids: string[];
    trip_purposes: string[];
  }[];
  hard_constraints: HardConstraint[];
}

export interface RLResponse {
  policy_trained: boolean;
  policy_note: string;
  training_ready: boolean;
  blockers: string[];
  reward_profile: RewardProfile | null;
  reward_profile_error: string | null;
  observation_space: {
    version: string;
    feature_groups: string[];
    source_document: string;
  };
  action_space: {
    version: string;
    action_type: string;
    caveat: string;
  };
  training_config: Record<string, unknown> & { present?: boolean };
}

export interface DataStream {
  id: string;
  name: string;
  status: StageStatus;
  summary: string;
  location: string;
}

export interface ConfigFile {
  name: string;
  path: string;
  present: boolean;
}

export interface DataResponse {
  run_store: {
    run_count: number;
    scenarios: string[];
    controllers: string[];
    engines: string[];
    directory: string;
  };
  streams: DataStream[];
  dvc: Record<string, string>;
  configs: ConfigFile[];
}

export interface ReadinessCheck {
  name: string;
  status: CheckStatus;
  detail: string;
}

export interface SystemStateResponse {
  summary: string;
  ok_count: number;
  warn_count: number;
  fail_count: number;
  checks: ReadinessCheck[];
}

export interface DistrictRegistryEntry {
  district_id: string;
  name: string;
  status: string;
  source_kind: string;
  note: string;
  active: boolean;
}

export interface DistrictsResponse {
  active_district_id: string;
  districts: DistrictRegistryEntry[];
}
