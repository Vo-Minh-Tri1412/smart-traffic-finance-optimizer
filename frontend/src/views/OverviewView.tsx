import { useQuery } from "@tanstack/react-query";
import { Activity, Clock3, Database, TrafficCone } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltipBody } from "../components/ChartTooltip";
import { Badge, Card, EmptyState, ErrorState, LoadingState, StatTile } from "../components/ui";
import { api } from "../lib/api";
import {
  controllerColor,
  controllerLabel,
  engineLabel,
  scenarioLabel,
} from "../lib/domain";
import { formatDateTime, formatNumber, formatSeconds } from "../lib/format";
import type { RunSummary } from "../lib/types";

/** Latest run per (scenario, controller), preferring newest created_at. */
function latestRunsIndex(runs: RunSummary[]): Map<string, RunSummary> {
  const index = new Map<string, RunSummary>();
  for (const run of runs) {
    const key = `${run.engine_id}|${run.scenario_id}|${run.controller_id}`;
    const current = index.get(key);
    if (!current || run.created_at > current.created_at) {
      index.set(key, run);
    }
  }
  return index;
}

export default function OverviewView() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const district = useQuery({ queryKey: ["district"], queryFn: api.district });
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.runs });

  const runs = useMemo(() => runsQuery.data?.runs ?? [], [runsQuery.data]);

  const { chartData, controllers } = useMemo(() => {
    const index = latestRunsIndex(runs);
    const scenarioIds = [...new Set(runs.map((run) => run.scenario_id))];
    const controllerIds = [...new Set(runs.map((run) => run.controller_id))].sort();
    const rows = scenarioIds.map((scenarioId) => {
      const row: Record<string, number | string> = {
        scenario: scenarioId,
        label: scenarioLabel(scenarioId),
      };
      for (const controllerId of controllerIds) {
        const run =
          index.get(`reference|${scenarioId}|${controllerId}`) ??
          index.get(`sumo|${scenarioId}|${controllerId}`);
        if (run) row[controllerId] = run.metrics.average_waiting_time_seconds;
      }
      return row;
    });
    return { chartData: rows, controllers: controllerIds };
  }, [runs]);

  const scenariosCovered = new Set(runs.map((run) => run.scenario_id)).size;
  const latestRun = runs[0];
  const sumoEngine = health.data?.engines.find((engine) => engine.engine_id === "sumo");

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">
            {district.data?.metadata.name ?? "Bảng điều khiển mô phỏng"}
          </h1>
          <p className="mt-1 text-xs text-ink-3">
            Điều khiển đèn giao thông thông minh và phân bổ ngân sách đầu tư công ·{" "}
            {district.data ? `spec v${district.data.metadata.version}` : "đang tải spec…"}
          </p>
        </div>
        {district.data && (
          <div className="flex gap-2">
            <Badge color="var(--color-series-1)">
              {district.data.intersections.length} nút giao
            </Badge>
            <Badge color="var(--color-series-2)">{district.data.roads.length} tuyến đường</Badge>
            <Badge color="var(--color-series-4)">{district.data.zones.length} phân khu</Badge>
          </div>
        )}
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatTile
          icon={Database}
          label="Lượt mô phỏng đã lưu"
          value={runsQuery.isSuccess ? runs.length : "…"}
          hint={latestRun ? `Mới nhất: ${formatDateTime(latestRun.created_at)}` : "Chưa có run nào"}
        />
        <StatTile
          icon={Activity}
          label="Kịch bản đã chạy"
          value={runsQuery.isSuccess ? scenariosCovered : "…"}
          hint={district.data ? `trên tổng ${district.data.scenarios.length} kịch bản` : undefined}
          accent="var(--color-series-2)"
        />
        <StatTile
          icon={Clock3}
          label="Chờ trung bình (run mới nhất)"
          value={latestRun ? formatSeconds(latestRun.metrics.average_waiting_time_seconds) : "—"}
          hint={
            latestRun
              ? `${scenarioLabel(latestRun.scenario_id)} · ${controllerLabel(latestRun.controller_id)}`
              : undefined
          }
          accent="var(--color-series-3)"
        />
        <StatTile
          icon={TrafficCone}
          label="Engine SUMO"
          value={sumoEngine ? (sumoEngine.available ? "Sẵn sàng" : "Chưa cài") : "…"}
          hint={
            sumoEngine?.available
              ? "Có thể chạy mô phỏng SUMO đầy đủ"
              : "Engine tham chiếu vẫn hoạt động"
          }
          accent={
            sumoEngine?.available ? "var(--color-status-good)" : "var(--color-status-warning)"
          }
        />
      </div>

      <Card
        title="Thời gian chờ trung bình theo kịch bản"
        subtitle="Mỗi cột là run mới nhất của controller trong kịch bản đó — thấp hơn là tốt hơn"
      >
        {runsQuery.isPending ? (
          <LoadingState />
        ) : runsQuery.isError ? (
          <ErrorState
            title="Không tải được danh sách run"
            detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
          />
        ) : chartData.length === 0 ? (
          <EmptyState
            title="Chưa có dữ liệu mô phỏng"
            detail="Sang trang Mô phỏng để chạy kịch bản đầu tiên."
          />
        ) : (
          <div className="h-80">
            <ResponsiveContainer>
              <BarChart data={chartData} barGap={2} margin={{ top: 8, right: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="0" />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={false}
                  interval={0}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={44}
                  tickFormatter={(value: number) => formatNumber(value)}
                  label={{
                    value: "giây",
                    angle: -90,
                    position: "insideLeft",
                    style: { fill: "var(--color-ink-3)", fontSize: 10 },
                  }}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <ChartTooltipBody
                        title={String(label)}
                        rows={payload.map((entry) => ({
                          color: String(entry.color),
                          name: controllerLabel(String(entry.dataKey)),
                          value: formatSeconds(Number(entry.value)),
                        }))}
                      />
                    ) : null
                  }
                />
                <Legend
                  formatter={(value: string) => (
                    <span className="text-[11px] text-ink-2">{controllerLabel(value)}</span>
                  )}
                  iconSize={9}
                />
                {controllers.map((controllerId) => (
                  <Bar
                    key={controllerId}
                    dataKey={controllerId}
                    fill={controllerColor(controllerId)}
                    radius={[4, 4, 0, 0]}
                    maxBarSize={26}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card
        title="Run gần đây"
        subtitle="5 lượt mô phỏng mới nhất"
        actions={
          <Link
            to="/runs"
            className="rounded-lg border border-hairline px-3 py-1.5 text-xs font-medium text-ink-2 transition hover:bg-surface-2"
          >
            Xem tất cả
          </Link>
        }
      >
        {runs.length === 0 ? (
          <EmptyState title="Chưa có run nào" />
        ) : (
          <ul className="divide-y divide-hairline">
            {runs.slice(0, 5).map((run) => (
              <li key={run.run_id} className="flex flex-wrap items-center gap-3 py-2.5 text-xs">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: controllerColor(run.controller_id) }}
                  aria-hidden
                />
                <span className="font-medium text-ink">{scenarioLabel(run.scenario_id)}</span>
                <span className="text-ink-3">{controllerLabel(run.controller_id)}</span>
                <Badge>{engineLabel(run.engine_id)}</Badge>
                <span className="ml-auto tabular-nums text-ink-2">
                  chờ TB {formatSeconds(run.metrics.average_waiting_time_seconds)}
                </span>
                <span className="tabular-nums text-ink-3">
                  {formatDateTime(run.created_at)}
                </span>
                <Link
                  to={`/replay/${run.run_id}`}
                  className="rounded-md border border-hairline px-2 py-1 font-medium text-ink-2 transition hover:bg-surface-2"
                >
                  Replay
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
