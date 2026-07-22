import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Play, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltipBody } from "../components/ChartTooltip";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import { api, ApiError } from "../lib/api";
import {
  controllerColor,
  controllerLabel,
  engineLabel,
  scenarioLabel,
} from "../lib/domain";
import { formatDateTime, formatInt, formatNumber, formatSeconds } from "../lib/format";
import type { EngineId } from "../lib/types";

function JobStrip() {
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: (query) => {
      const jobs = query.state.data?.jobs ?? [];
      return jobs.some((job) => job.state === "queued" || job.state === "running") ? 1000 : false;
    },
  });
  const queryClient = useQueryClient();
  const jobs = jobsQuery.data?.jobs ?? [];
  const active = jobs.filter((job) => job.state === "queued" || job.state === "running");
  const recentFailed = jobs.filter((job) => job.state === "failed").slice(0, 2);

  // When an active job finishes, refresh the run list once.
  const activeCount = active.length;
  const prevActiveCount = useRef(0);
  useEffect(() => {
    if (activeCount < prevActiveCount.current) {
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      void queryClient.invalidateQueries({ queryKey: ["coverage"] });
    }
    prevActiveCount.current = activeCount;
  }, [activeCount, queryClient]);

  if (active.length === 0 && recentFailed.length === 0) return null;

  return (
    <div className="space-y-2">
      <AnimatePresence>
        {active.map((job) => (
          <motion.div
            key={job.job_id}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-3 rounded-xl border border-hairline bg-surface-2 px-4 py-2.5 text-xs"
          >
            <RefreshCw size={13} className="animate-spin text-ink-3" aria-hidden />
            <span className="font-medium text-ink">
              Đang chạy: {scenarioLabel(job.request.scenario_id)} ·{" "}
              {controllerLabel(job.request.controller_id)}
            </span>
            <Badge>{engineLabel(job.request.engine_id)}</Badge>
            <span className="ml-auto text-ink-3">
              {job.state === "queued" ? "đang xếp hàng" : "đang mô phỏng…"}
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
      {recentFailed.map((job) => (
        <div
          key={job.job_id}
          className="rounded-xl border px-4 py-2.5 text-xs"
          style={{
            borderColor: "color-mix(in srgb, var(--color-status-critical) 40%, transparent)",
            background: "color-mix(in srgb, var(--color-status-critical) 8%, transparent)",
          }}
        >
          <span className="font-medium text-ink">
            Run lỗi ({controllerLabel(job.request.controller_id)}):
          </span>{" "}
          <span className="text-ink-2">{job.error}</span>
        </div>
      ))}
    </div>
  );
}

function LaunchPanel() {
  const district = useQuery({ queryKey: ["district"], queryFn: api.district });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const queryClient = useQueryClient();

  const [scenarioId, setScenarioId] = useState("normal_weekday");
  const [controllerId, setControllerId] = useState("fixed_time");
  const [engineId, setEngineId] = useState<EngineId>("reference");
  const [seed, setSeed] = useState(42);

  const launch = useMutation({
    mutationFn: api.launchRun,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const sumoAvailable =
    health.data?.engines.find((engine) => engine.engine_id === "sumo")?.available ?? false;

  const scenarios = district.data?.scenarios ?? [];
  const controllers = district.data?.controllers ?? [];

  return (
    <Card
      title="Chạy mô phỏng mới"
      subtitle="Backend chạy engine và lưu artifact (metrics + trace) — giao diện chỉ replay kết quả"
    >
      <div className="flex flex-wrap items-end gap-4">
        <Select
          label="Kịch bản"
          value={scenarioId}
          onChange={setScenarioId}
          options={scenarios.map((scenario) => ({
            value: scenario.id,
            label: scenarioLabel(scenario.id),
          }))}
        />
        <Select
          label="Controller"
          value={controllerId}
          onChange={setControllerId}
          options={controllers.map((controller) => ({
            value: controller.id,
            label: controllerLabel(controller.id),
          }))}
        />
        <Select
          label="Engine"
          value={engineId}
          onChange={(value) => setEngineId(value as EngineId)}
          options={[
            { value: "reference", label: "Engine tham chiếu (nhanh)" },
            {
              value: "sumo",
              label: sumoAvailable ? "SUMO (đầy đủ)" : "SUMO (chưa cài đặt)",
            },
          ]}
        />
        <label className="flex items-center gap-2 text-xs text-ink-3">
          Seed
          <input
            type="number"
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
            className="w-20 rounded-lg border border-hairline bg-surface-2 px-2.5 py-1.5 text-xs font-medium tabular-nums text-ink outline-none focus:border-accent"
          />
        </label>
        <button
          type="button"
          disabled={launch.isPending || (engineId === "sumo" && !sumoAvailable)}
          onClick={() =>
            launch.mutate({
              scenario_id: scenarioId,
              controller_id: controllerId,
              engine_id: engineId,
              seed,
              label: "dashboard",
            })
          }
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ background: "var(--color-series-1)" }}
        >
          <Play size={14} aria-hidden />
          {launch.isPending ? "Đang gửi…" : "Chạy mô phỏng"}
        </button>
      </div>
      {launch.isError && (
        <p className="mt-3 text-xs" style={{ color: "var(--color-status-critical)" }}>
          {launch.error instanceof ApiError ? launch.error.message : "Không gửi được yêu cầu."}
        </p>
      )}
      {engineId === "sumo" && !sumoAvailable && (
        <p className="mt-3 text-xs text-ink-3">
          SUMO chưa có trên máy backend — cài SUMO và đặt SUMO_HOME để mở khóa engine đầy đủ.
        </p>
      )}
    </Card>
  );
}

function RunDetailPanel({ runId }: { runId: string }) {
  const detail = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.runDetail(runId),
  });

  const topIntersections = useMemo(() => {
    if (!detail.data) return [];
    return Object.values(detail.data.intersections)
      .sort((a, b) => b.delay_seconds - a.delay_seconds)
      .slice(0, 8)
      .map((item) => ({
        id: item.intersection_id,
        delay: item.delay_seconds,
        queue: item.queue_vehicles,
      }));
  }, [detail.data]);

  if (detail.isPending) return <LoadingState label="Đang tải chi tiết run…" />;
  if (detail.isError || !detail.data) {
    return <ErrorState title="Không tải được chi tiết run" />;
  }

  const metrics = detail.data.metrics;
  const color = controllerColor(detail.data.controller_id);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
      <div className="grid grid-cols-2 gap-3 text-xs">
        {[
          ["Tổng phương tiện", formatInt(metrics.total_vehicles)],
          ["Hoàn thành lộ trình", formatInt(metrics.throughput)],
          ["Chờ trung bình", formatSeconds(metrics.average_waiting_time_seconds)],
          ["Hàng đợi tối đa", `${formatNumber(metrics.max_queue_vehicles)} xe`],
          ["Trễ xe cấp cứu", formatSeconds(metrics.emergency_delay_seconds)],
          ["Trễ xe tải", formatSeconds(metrics.truck_delay_seconds)],
          ["Xe phải dừng", formatInt(metrics.stopped_vehicles)],
          ["Can thiệp controller", formatInt(metrics.controller_interventions)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl bg-surface-2 p-3">
            <p className="text-[10px] text-ink-3">{label}</p>
            <p className="mt-1 text-sm font-semibold tabular-nums text-ink">{value}</p>
          </div>
        ))}
      </div>

      <div>
        <p className="mb-2 text-[11px] font-semibold text-ink-2">
          Nút giao chịu tải nặng nhất (tổng trễ)
        </p>
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={topIntersections} layout="vertical" margin={{ right: 12 }}>
              <CartesianGrid horizontal={false} strokeDasharray="0" />
              <XAxis
                type="number"
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => formatNumber(value / 3600)}
                label={{
                  value: "giờ trễ tích lũy",
                  position: "insideBottom",
                  dy: 8,
                  style: { fill: "var(--color-ink-3)", fontSize: 10 },
                }}
              />
              <YAxis
                type="category"
                dataKey="id"
                width={40}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <ChartTooltipBody
                      title={String(payload[0].payload.id)}
                      rows={[
                        {
                          color,
                          name: "Tổng trễ",
                          value: formatSeconds(Number(payload[0].payload.delay)),
                        },
                        {
                          name: "Hàng đợi TB",
                          value: `${formatNumber(Number(payload[0].payload.queue))} xe`,
                        },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="delay" fill={color} radius={[0, 4, 4, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default function RunsView() {
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.runs });
  const queryClient = useQueryClient();
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const deleteRun = useMutation({
    mutationFn: api.deleteRun,
    onSuccess: () => {
      setConfirmDeleteId(null);
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const runs = runsQuery.data?.runs ?? [];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Mô phỏng</h1>
        <p className="mt-1 text-xs text-ink-3">
          Chạy kịch bản × controller, theo dõi job và duyệt kho artifact run.
        </p>
      </header>

      <LaunchPanel />
      <JobStrip />

      <Card title="Kho run" subtitle={`${runs.length} lượt mô phỏng đã lưu`}>
        {runsQuery.isPending ? (
          <LoadingState />
        ) : runsQuery.isError ? (
          <ErrorState
            title="Không tải được danh sách run"
            detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
          />
        ) : runs.length === 0 ? (
          <EmptyState
            title="Chưa có run nào"
            detail="Dùng bảng phía trên để chạy mô phỏng đầu tiên."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-hairline text-[10px] uppercase tracking-wide text-ink-3">
                  <th className="pb-2 pr-3 font-medium">Kịch bản</th>
                  <th className="pb-2 pr-3 font-medium">Controller</th>
                  <th className="pb-2 pr-3 font-medium">Engine</th>
                  <th className="pb-2 pr-3 text-right font-medium">Chờ TB</th>
                  <th className="pb-2 pr-3 text-right font-medium">Lưu lượng</th>
                  <th className="pb-2 pr-3 text-right font-medium">Trễ cấp cứu</th>
                  <th className="pb-2 pr-3 text-right font-medium">Thời điểm</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <RunRow
                    key={run.run_id}
                    run={run}
                    expanded={expandedRunId === run.run_id}
                    onToggle={() =>
                      setExpandedRunId(expandedRunId === run.run_id ? null : run.run_id)
                    }
                    confirmingDelete={confirmDeleteId === run.run_id}
                    onDeleteRequest={() => setConfirmDeleteId(run.run_id)}
                    onDeleteCancel={() => setConfirmDeleteId(null)}
                    onDeleteConfirm={() => deleteRun.mutate(run.run_id)}
                    deleting={deleteRun.isPending && confirmDeleteId === run.run_id}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function RunRow({
  run,
  expanded,
  onToggle,
  confirmingDelete,
  onDeleteRequest,
  onDeleteCancel,
  onDeleteConfirm,
  deleting,
}: {
  run: import("../lib/types").RunSummary;
  expanded: boolean;
  onToggle: () => void;
  confirmingDelete: boolean;
  onDeleteRequest: () => void;
  onDeleteCancel: () => void;
  onDeleteConfirm: () => void;
  deleting: boolean;
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-b border-hairline transition hover:bg-surface-2/60"
        onClick={onToggle}
      >
        <td className="py-2.5 pr-3">
          <span className="flex items-center gap-2 font-medium text-ink">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: controllerColor(run.controller_id) }}
              aria-hidden
            />
            {scenarioLabel(run.scenario_id)}
          </span>
        </td>
        <td className="py-2.5 pr-3 text-ink-2">{controllerLabel(run.controller_id)}</td>
        <td className="py-2.5 pr-3 text-ink-3">{engineLabel(run.engine_id)}</td>
        <td className="py-2.5 pr-3 text-right tabular-nums text-ink">
          {formatSeconds(run.metrics.average_waiting_time_seconds)}
        </td>
        <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
          {formatInt(run.metrics.throughput)}/{formatInt(run.metrics.total_vehicles)}
        </td>
        <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
          {formatSeconds(run.metrics.emergency_delay_seconds)}
        </td>
        <td className="py-2.5 pr-3 text-right tabular-nums text-ink-3">
          {formatDateTime(run.created_at)}
        </td>
        <td className="py-2.5">
          <div
            className="flex items-center justify-end gap-1.5"
            onClick={(event) => event.stopPropagation()}
          >
            <Link
              to={`/replay/${run.run_id}`}
              className="rounded-md border border-hairline px-2 py-1 text-[11px] font-medium text-ink-2 transition hover:bg-surface-2"
            >
              Replay
            </Link>
            {confirmingDelete ? (
              <span className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={onDeleteConfirm}
                  disabled={deleting}
                  className="rounded-md px-2 py-1 text-[11px] font-semibold text-white"
                  style={{ background: "var(--color-status-critical)" }}
                >
                  {deleting ? "Đang xóa…" : "Xóa hẳn"}
                </button>
                <button
                  type="button"
                  onClick={onDeleteCancel}
                  className="rounded-md border border-hairline px-2 py-1 text-[11px] text-ink-3"
                >
                  Hủy
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={onDeleteRequest}
                title="Xóa run"
                className="rounded-md border border-hairline p-1.5 text-ink-3 transition hover:bg-surface-2 hover:text-ink"
              >
                <Trash2 size={13} aria-hidden />
              </button>
            )}
            <ChevronDown
              size={14}
              className={`text-ink-3 transition-transform ${expanded ? "rotate-180" : ""}`}
              aria-hidden
            />
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-hairline bg-surface-2/40">
          <td colSpan={8} className="p-4">
            <RunDetailPanel runId={run.run_id} />
          </td>
        </tr>
      )}
    </>
  );
}
