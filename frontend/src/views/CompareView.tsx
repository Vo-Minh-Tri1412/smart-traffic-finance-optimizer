import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltipBody } from "../components/ChartTooltip";
import { Card, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import { api } from "../lib/api";
import { controllerColor, controllerLabel, scenarioLabel } from "../lib/domain";
import { formatInt, formatNumber, formatPercent, formatSeconds } from "../lib/format";
import type { CompareRow } from "../lib/types";

const METRIC_OPTIONS = [
  { value: "average_waiting_time_seconds", label: "Chờ trung bình (giây)", lowerBetter: true },
  { value: "total_waiting_time_seconds", label: "Tổng thời gian chờ (giây)", lowerBetter: true },
  { value: "throughput", label: "Lưu lượng hoàn thành (xe)", lowerBetter: false },
  { value: "emergency_delay_seconds", label: "Trễ xe cấp cứu (giây)", lowerBetter: true },
  { value: "bus_passenger_delay_seconds", label: "Trễ khách xe buýt (giây)", lowerBetter: true },
  { value: "truck_delay_seconds", label: "Trễ xe tải (giây)", lowerBetter: true },
] as const;

type MetricKey = (typeof METRIC_OPTIONS)[number]["value"];

function DeltaChip({ value, lowerBetter }: { value: number; lowerBetter: boolean }) {
  if (Math.abs(value) < 1e-9) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-ink-3">
        <Minus size={12} aria-hidden /> không đổi
      </span>
    );
  }
  const improved = lowerBetter ? value > 0 : value < 0;
  const color = improved ? "var(--color-status-good)" : "var(--color-status-critical)";
  const Icon = value > 0 ? ArrowDownRight : ArrowUpRight;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium" style={{ color }}>
      <Icon size={12} aria-hidden />
      {improved ? "cải thiện" : "kém hơn"}
    </span>
  );
}

export default function CompareView() {
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: api.coverage });

  const engineOptions = useMemo(() => {
    const engines = Object.keys(coverage.data?.coverage ?? {});
    return engines.length > 0 ? engines : ["reference"];
  }, [coverage.data]);

  const [engineId, setEngineId] = useState("reference");
  const scenarioOptions = useMemo(() => {
    const byScenario = coverage.data?.coverage?.[engineId] ?? {};
    return Object.entries(byScenario)
      .filter(([, controllers]) => "fixed_time" in controllers)
      .map(([scenarioId]) => scenarioId);
  }, [coverage.data, engineId]);

  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const activeScenario =
    scenarioId && scenarioOptions.includes(scenarioId) ? scenarioId : scenarioOptions[0] ?? null;

  const [metric, setMetric] = useState<MetricKey>("average_waiting_time_seconds");
  const metricInfo = METRIC_OPTIONS.find((option) => option.value === metric)!;

  const compareQuery = useQuery({
    queryKey: ["compare", activeScenario, engineId],
    queryFn: () => api.compare(activeScenario!, engineId),
    enabled: activeScenario !== null,
  });

  const rows = useMemo(() => compareQuery.data?.rows ?? [], [compareQuery.data]);

  const chartData = useMemo(
    () =>
      rows.map((row) => ({
        controller: row.controller_id,
        label: controllerLabel(row.controller_id),
        value: row[metric],
      })),
    [rows, metric],
  );
  const metricUnavailable = chartData.length > 0 && chartData.every((entry) => entry.value === null);

  const bestAlternative = useMemo(() => {
    const alternatives = rows.filter((row) => row.controller_id !== "fixed_time");
    if (alternatives.length === 0) return null;
    return alternatives.reduce((best, row) =>
      row.waiting_time_saved_vs_fixed_seconds > best.waiting_time_saved_vs_fixed_seconds
        ? row
        : best,
    );
  }, [rows]);

  if (coverage.isPending) return <LoadingState />;
  if (coverage.isError) {
    return (
      <ErrorState
        title="Không tải được dữ liệu so sánh"
        detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
      />
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">So sánh controller</h1>
          <p className="mt-1 text-xs text-ink-3">
            Đối chiếu các chiến lược điều khiển đèn với mốc fixed-time trong cùng kịch bản.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Select
            label="Engine"
            value={engineId}
            onChange={setEngineId}
            options={engineOptions.map((engine) => ({ value: engine, label: engine }))}
          />
          {activeScenario && (
            <Select
              label="Kịch bản"
              value={activeScenario}
              onChange={setScenarioId}
              options={scenarioOptions.map((scenario) => ({
                value: scenario,
                label: scenarioLabel(scenario),
              }))}
            />
          )}
        </div>
      </header>

      {activeScenario === null ? (
        <EmptyState
          title="Chưa đủ dữ liệu để so sánh"
          detail="Cần ít nhất một run fixed_time trong một kịch bản. Sang trang Mô phỏng để chạy."
        />
      ) : compareQuery.isPending ? (
        <LoadingState />
      ) : compareQuery.isError ? (
        <ErrorState title="Không tải được bảng so sánh" />
      ) : (
        <>
          {bestAlternative && (
            <Card>
              <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-3">
                    Controller tốt nhất (theo tổng chờ)
                  </p>
                  <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-ink">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ background: controllerColor(bestAlternative.controller_id) }}
                      aria-hidden
                    />
                    {controllerLabel(bestAlternative.controller_id)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-3">
                    Thời gian chờ tiết kiệm
                  </p>
                  <p className="mt-1 text-lg font-semibold tabular-nums text-ink">
                    {formatSeconds(bestAlternative.waiting_time_saved_vs_fixed_seconds)}{" "}
                    <span className="text-xs font-normal text-ink-3">
                      ({formatPercent(bestAlternative.waiting_time_saved_vs_fixed_pct)})
                    </span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-3">
                    Lưu lượng thay đổi
                  </p>
                  <p className="mt-1 text-lg font-semibold tabular-nums text-ink">
                    {bestAlternative.throughput_gain_vs_fixed >= 0 ? "+" : ""}
                    {formatInt(bestAlternative.throughput_gain_vs_fixed)} xe
                  </p>
                </div>
                <div className="max-w-72">
                  <p className="text-[10px] uppercase tracking-wide text-ink-3">Nhận xét</p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-2">
                    {bestAlternative.interpretation}
                  </p>
                </div>
              </div>
            </Card>
          )}

          <Card
            title="So sánh theo chỉ số"
            subtitle={
              metricInfo.lowerBetter ? "Cột thấp hơn là tốt hơn" : "Cột cao hơn là tốt hơn"
            }
            actions={
              <Select
                value={metric}
                onChange={(value) => setMetric(value as MetricKey)}
                options={METRIC_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
            }
          >
            <div className="h-72">
              {metricUnavailable ? (
                <div className="flex h-full items-center justify-center text-xs text-ink-3">
                  Không khả dụng trong dữ liệu nguồn.
                </div>
              ) : <ResponsiveContainer>
                <BarChart data={chartData} barGap={2} margin={{ top: 24, right: 8 }}>
                  <CartesianGrid vertical={false} strokeDasharray="0" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={52}
                    tickFormatter={(value: number) => formatNumber(value)}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    content={({ active, payload }) =>
                      active && payload?.length ? (
                        <ChartTooltipBody
                          title={String(payload[0].payload.label)}
                          rows={[
                            {
                              color: controllerColor(String(payload[0].payload.controller)),
                              name: metricInfo.label,
                              value:
                                payload[0].value == null
                                  ? "Không khả dụng"
                                  : formatNumber(Number(payload[0].value)),
                            },
                          ]}
                        />
                      ) : null
                    }
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    <LabelList
                      dataKey="value"
                      position="top"
                      formatter={(value) => (value == null ? "" : formatNumber(Number(value)))}
                      style={{ fill: "var(--color-ink-2)", fontSize: 11 }}
                    />
                    {chartData.map((entry) => (
                      <Cell key={entry.controller} fill={controllerColor(entry.controller)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>}
            </div>
          </Card>

          <Card
            title="Bảng chi tiết so với fixed-time"
            subtitle="Giá trị dương ở các cột “tiết kiệm” nghĩa là tốt hơn mốc fixed-time"
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-xs">
                <thead>
                  <tr className="border-b border-hairline text-[10px] uppercase tracking-wide text-ink-3">
                    <th className="pb-2 pr-3 font-medium">Controller</th>
                    <th className="pb-2 pr-3 text-right font-medium">Chờ TB</th>
                    <th className="pb-2 pr-3 text-right font-medium">Tiết kiệm chờ</th>
                    <th className="pb-2 pr-3 text-right font-medium">Lưu lượng ±</th>
                    <th className="pb-2 pr-3 text-right font-medium">Cấp cứu tiết kiệm</th>
                    <th className="pb-2 pr-3 text-right font-medium">Xe buýt tiết kiệm</th>
                    <th className="pb-2 pr-3 text-right font-medium">Xe tải tiết kiệm</th>
                    <th className="pb-2 font-medium">Nhận xét</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: CompareRow) => (
                    <tr key={row.controller_id} className="border-b border-hairline">
                      <td className="py-2.5 pr-3">
                        <span className="flex items-center gap-2 font-medium text-ink">
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ background: controllerColor(row.controller_id) }}
                            aria-hidden
                          />
                          {controllerLabel(row.controller_id)}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink">
                        {formatSeconds(row.average_waiting_time_seconds)}
                      </td>
                      <td className="py-2.5 pr-3 text-right">
                        <span className="tabular-nums text-ink-2">
                          {formatSeconds(row.waiting_time_saved_vs_fixed_seconds)}
                        </span>{" "}
                        {row.controller_id !== "fixed_time" && (
                          <DeltaChip
                            value={row.waiting_time_saved_vs_fixed_seconds}
                            lowerBetter
                          />
                        )}
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                        {row.throughput_gain_vs_fixed >= 0 ? "+" : ""}
                        {formatInt(row.throughput_gain_vs_fixed)}
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                        {formatSeconds(row.emergency_delay_saved_vs_fixed_seconds)}
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                        {row.bus_passenger_delay_saved_vs_fixed_seconds === null
                          ? "Không khả dụng"
                          : formatSeconds(row.bus_passenger_delay_saved_vs_fixed_seconds)}
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                        {formatSeconds(row.truck_delay_saved_vs_fixed_seconds)}
                      </td>
                      <td className="py-2.5 text-ink-3">{row.interpretation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
