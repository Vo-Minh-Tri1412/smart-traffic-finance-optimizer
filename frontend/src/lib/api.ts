import type {
  CompareResponse,
  DataResponse,
  DistrictResponse,
  DistrictsResponse,
  FinanceOptimizeRequest,
  FinanceOptimizeResponse,
  HealthResponse,
  JobStatus,
  PipelineResponse,
  RLResponse,
  RunCoverageResponse,
  RunDetail,
  RunSummary,
  SimulationJobRequest,
  SystemStateResponse,
  TracePage,
} from "./types";

// Same-origin by default: the Vite dev server proxies /api to the FastAPI
// backend, and in production FastAPI serves the built frontend itself.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Không kết nối được backend dashboard.");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  district: () => request<DistrictResponse>("/api/district"),
  runs: () => request<{ runs: RunSummary[] }>("/api/runs"),
  runDetail: (runId: string) => request<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`),
  runTrace: (runId: string, offset = 0, limit = 2000) =>
    request<TracePage>(
      `/api/runs/${encodeURIComponent(runId)}/trace?offset=${offset}&limit=${limit}`,
    ),
  deleteRun: (runId: string) =>
    request<void>(`/api/runs/${encodeURIComponent(runId)}`, { method: "DELETE" }),
  coverage: () => request<RunCoverageResponse>("/api/runs/coverage"),
  launchRun: (body: SimulationJobRequest) =>
    request<JobStatus>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<{ jobs: JobStatus[] }>("/api/jobs"),
  job: (jobId: string) => request<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`),
  compare: (scenarioId: string, engineId: string) =>
    request<CompareResponse>(
      `/api/compare?scenario_id=${encodeURIComponent(scenarioId)}&engine_id=${encodeURIComponent(engineId)}`,
    ),
  financeOptimize: (body: FinanceOptimizeRequest) =>
    request<FinanceOptimizeResponse>("/api/finance/optimize", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  pipeline: () => request<PipelineResponse>("/api/system/pipeline"),
  rl: () => request<RLResponse>("/api/system/rl"),
  systemData: () => request<DataResponse>("/api/system/data"),
  systemState: () => request<SystemStateResponse>("/api/system/state"),
  districts: () => request<DistrictsResponse>("/api/districts"),
};
