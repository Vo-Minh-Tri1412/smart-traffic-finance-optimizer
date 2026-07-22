import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, Calculator, CircleAlert, Landmark, PiggyBank, Sigma } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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
import DistrictMap from "../components/DistrictMap";
import { Card, EmptyState, ErrorState, LoadingState, Select, StatTile } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { controllerLabel, scenarioLabel } from "../lib/domain";
import { formatNumber, formatVnd } from "../lib/format";
import type { EngineId, FinanceOptimizeResponse, OptimizerAlgorithm } from "../lib/types";

const BUDGET_MIN = 500_000;
const BUDGET_MAX = 6_000_000;
const BUDGET_STEP = 100_000;

export default function FinanceView() {
  const district = useQuery({ queryKey: ["district"], queryFn: api.district });
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: api.coverage });

  const [engineId] = useState<EngineId>("reference");
  const [budget, setBudget] = useState(2_000_000);
  const [algorithm, setAlgorithm] = useState<OptimizerAlgorithm>("greedy");
  const [includeQubo, setIncludeQubo] = useState(false);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [controllerId, setControllerId] = useState("rule_based");
  const [result, setResult] = useState<FinanceOptimizeResponse | null>(null);

  const scenarioOptions = useMemo(() => {
    const byScenario = coverage.data?.coverage?.[engineId] ?? {};
    return Object.entries(byScenario)
      .filter(
        ([, controllers]) =>
          "fixed_time" in controllers && Object.keys(controllers).length >= 2,
      )
      .map(([scenario]) => scenario);
  }, [coverage.data, engineId]);

  const activeScenario =
    scenarioId && scenarioOptions.includes(scenarioId) ? scenarioId : scenarioOptions[0] ?? null;

  const controllerOptions = useMemo(() => {
    if (!activeScenario) return [];
    const controllers = coverage.data?.coverage?.[engineId]?.[activeScenario] ?? {};
    return Object.keys(controllers).filter((controller) => controller !== "fixed_time");
  }, [coverage.data, engineId, activeScenario]);

  const activeController = controllerOptions.includes(controllerId)
    ? controllerId
    : controllerOptions[0] ?? "rule_based";

  const optimize = useMutation({
    mutationFn: api.financeOptimize,
    onSuccess: setResult,
  });

  const runOptimize = (overrides?: Partial<{ budget: number }>) => {
    if (!activeScenario) return;
    optimize.mutate({
      budget_vnd: overrides?.budget ?? budget,
      algorithm,
      scenario_id: activeScenario,
      controller_id: activeController,
      engine_id: engineId,
      include_qubo: includeQubo,
    });
  };

  // Run once automatically when scenario data first becomes available.
  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoRan.current && activeScenario && !result && !optimize.isPending) {
      autoRan.current = true;
      runOptimize();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeScenario]);

  const selectedIds = useMemo(
    () => new Set((result?.selected ?? []).map((item) => item.candidate_id)),
    [result],
  );

  const chartData = useMemo(
    () =>
      (result?.scores ?? [])
        .slice()
        .sort((a, b) => b.net_public_value_vnd - a.net_public_value_vnd)
        .map((score) => ({
          candidate: score.candidate_id,
          intersection: score.intersection_id,
          value: score.net_public_value_vnd,
          selected: selectedIds.has(score.candidate_id),
        })),
    [result, selectedIds],
  );

  const selectedIntersections = useMemo(
    () => (result?.selected ?? []).map((item) => item.intersection_id),
    [result],
  );

  if (district.isPending || coverage.isPending) return <LoadingState />;
  if (district.isError || !district.data) {
    return (
      <ErrorState
        title="Không tải được dữ liệu"
        detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
      />
    );
  }

  const candidateIntersections = district.data.investment_candidates.map(
    (item) => item.intersection_id,
  );

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          Tối ưu ngân sách đầu tư
        </h1>
        <p className="mt-1 text-xs text-ink-3">
          Với ngân sách giới hạn, chọn tập nút giao đáng nâng cấp đèn AI nhất theo giá trị công
          ròng — so sánh run controller thay thế với mốc fixed-time.
        </p>
      </header>

      {scenarioOptions.length === 0 ? (
        <EmptyState
          title="Chưa đủ dữ liệu để tối ưu"
          detail="Cần một kịch bản có cả run fixed_time và một controller khác. Sang trang Mô phỏng để chạy."
        />
      ) : (
        <>
          <Card title="Tham số tối ưu">
            <div className="flex flex-wrap items-end gap-x-5 gap-y-4">
              <Select
                label="Kịch bản"
                value={activeScenario ?? ""}
                onChange={setScenarioId}
                options={scenarioOptions.map((scenario) => ({
                  value: scenario,
                  label: scenarioLabel(scenario),
                }))}
              />
              <Select
                label="Controller thay thế"
                value={activeController}
                onChange={setControllerId}
                options={controllerOptions.map((controller) => ({
                  value: controller,
                  label: controllerLabel(controller),
                }))}
              />
              <Select
                label="Thuật toán"
                value={algorithm}
                onChange={(value) => setAlgorithm(value as OptimizerAlgorithm)}
                options={[
                  { value: "greedy", label: "Greedy (tỷ lệ lợi ích/chi phí)" },
                  { value: "exact", label: "Exact (duyệt toàn bộ tập con)" },
                ]}
              />
              <label className="flex items-center gap-2 text-xs text-ink-3">
                <input
                  type="checkbox"
                  checked={includeQubo}
                  onChange={(event) => setIncludeQubo(event.target.checked)}
                  className="accent-(--color-series-4)"
                />
                Xuất ma trận QUBO
              </label>

              <div className="flex min-w-64 flex-1 flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-ink-3">Ngân sách</span>
                  <span className="font-semibold tabular-nums text-ink">
                    {formatVnd(budget)}
                  </span>
                </div>
                <input
                  type="range"
                  min={BUDGET_MIN}
                  max={BUDGET_MAX}
                  step={BUDGET_STEP}
                  value={budget}
                  onChange={(event) => setBudget(Number(event.target.value))}
                  onMouseUp={() => runOptimize()}
                  onTouchEnd={() => runOptimize()}
                  className="accent-(--color-series-1)"
                  aria-label="Ngân sách (VND)"
                />
              </div>

              <button
                type="button"
                onClick={() => runOptimize()}
                disabled={optimize.isPending}
                className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
                style={{ background: "var(--color-series-1)" }}
              >
                <Calculator size={14} aria-hidden />
                {optimize.isPending ? "Đang tối ưu…" : "Tối ưu danh mục"}
              </button>
            </div>
            {optimize.isError && (
              <p className="mt-3 text-xs" style={{ color: "var(--color-status-critical)" }}>
                {optimize.error instanceof ApiError
                  ? optimize.error.message
                  : "Không tối ưu được."}
              </p>
            )}
          </Card>

          {result && (
            <>
              <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
                <StatTile
                  icon={BadgeCheck}
                  label="Ứng viên được chọn"
                  value={`${result.selected.length}/${result.scores.length}`}
                  hint={`Thuật toán ${result.algorithm}`}
                  accent="var(--color-status-good)"
                />
                <StatTile
                  icon={PiggyBank}
                  label="Chi phí sử dụng"
                  value={formatVnd(result.total_cost_vnd)}
                  hint={`còn dư ${formatVnd(Math.max(0, result.budget_vnd - result.total_cost_vnd))}`}
                />
                <StatTile
                  icon={Landmark}
                  label="Giá trị công ròng"
                  value={formatVnd(result.total_net_public_value_vnd)}
                  hint="tổng net public value của tập được chọn"
                  accent="var(--color-series-2)"
                />
                <StatTile
                  icon={Sigma}
                  label="Kịch bản đánh giá"
                  value={scenarioLabel(result.scenario_id)}
                  hint={`${controllerLabel(result.controller_id)} vs fixed-time`}
                  accent="var(--color-series-4)"
                />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
                <Card
                  title="Giá trị công ròng theo ứng viên"
                  subtitle="Cột đậm kèm ✓ = nằm trong danh mục được chọn dưới ngân sách hiện tại"
                >
                  <div className="h-80">
                    <ResponsiveContainer>
                      <BarChart data={chartData} margin={{ top: 24, right: 8 }}>
                        <CartesianGrid vertical={false} strokeDasharray="0" />
                        <XAxis
                          dataKey="candidate"
                          tickLine={false}
                          axisLine={false}
                          tick={{ fontSize: 9 }}
                          interval={0}
                        />
                        <YAxis
                          tickLine={false}
                          axisLine={false}
                          width={58}
                          tickFormatter={(value: number) => formatVnd(value)}
                          tick={{ fontSize: 9 }}
                        />
                        <Tooltip
                          cursor={{ fill: "rgba(255,255,255,0.04)" }}
                          content={({ active, payload }) =>
                            active && payload?.length ? (
                              <ChartTooltipBody
                                title={`${payload[0].payload.candidate} · nút ${payload[0].payload.intersection}`}
                                rows={[
                                  {
                                    color: payload[0].payload.selected
                                      ? "var(--color-series-2)"
                                      : "var(--color-ink-3)",
                                    name: payload[0].payload.selected
                                      ? "Được chọn"
                                      : "Không chọn",
                                    value: formatVnd(Number(payload[0].payload.value)),
                                  },
                                ]}
                              />
                            ) : null
                          }
                        />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={44}>
                          <LabelList
                            dataKey="selected"
                            position="top"
                            formatter={(value) => (value ? "✓" : "")}
                            style={{ fill: "var(--color-status-good)", fontSize: 13 }}
                          />
                          {chartData.map((entry) => (
                            <Cell
                              key={entry.candidate}
                              fill={
                                entry.selected ? "var(--color-series-2)" : "var(--color-surface-3)"
                              }
                              stroke={entry.selected ? undefined : "rgba(255,255,255,0.14)"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card
                  title="Vị trí đầu tư trên bản đồ"
                  subtitle="Vòng xanh quay = nút được chọn; viền vàng = ứng viên"
                >
                  <DistrictMap
                    intersections={district.data.intersections}
                    roads={district.data.roads}
                    zones={district.data.zones}
                    candidateIntersections={candidateIntersections}
                    selectedCandidateIntersections={selectedIntersections}
                    showZoneChips={false}
                  />
                </Card>
              </div>

              <Card title="Bảng điểm ứng viên" subtitle="Điểm so sánh run thay thế với mốc fixed-time">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] text-left text-xs">
                    <thead>
                      <tr className="border-b border-hairline text-[10px] uppercase tracking-wide text-ink-3">
                        <th className="pb-2 pr-3 font-medium">Ứng viên</th>
                        <th className="pb-2 pr-3 font-medium">Nút giao</th>
                        <th className="pb-2 pr-3 font-medium">Loại nâng cấp</th>
                        <th className="pb-2 pr-3 text-right font-medium">Chi phí</th>
                        <th className="pb-2 pr-3 text-right font-medium">Giá trị công</th>
                        <th className="pb-2 pr-3 text-right font-medium">Giá trị ròng</th>
                        <th className="pb-2 pr-3 text-right font-medium">B/C</th>
                        <th className="pb-2 text-center font-medium">Chọn</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.scores.map((score) => {
                        const selected = selectedIds.has(score.candidate_id);
                        return (
                          <tr
                            key={score.candidate_id}
                            className={`border-b border-hairline ${selected ? "bg-surface-2/50" : ""}`}
                          >
                            <td className="py-2.5 pr-3 font-medium text-ink">
                              {score.candidate_id}
                            </td>
                            <td className="py-2.5 pr-3 text-ink-2">{score.intersection_id}</td>
                            <td className="py-2.5 pr-3 text-ink-3">{score.upgrade_type}</td>
                            <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                              {formatVnd(score.capex_vnd + score.annual_maintenance_vnd)}
                            </td>
                            <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                              {formatVnd(score.public_value_vnd)}
                            </td>
                            <td className="py-2.5 pr-3 text-right font-medium tabular-nums text-ink">
                              {formatVnd(score.net_public_value_vnd)}
                            </td>
                            <td className="py-2.5 pr-3 text-right tabular-nums text-ink-2">
                              {formatNumber(score.benefit_cost_ratio)}
                            </td>
                            <td className="py-2.5 text-center">
                              {selected && (
                                <BadgeCheck
                                  size={15}
                                  aria-label="Được chọn"
                                  style={{ color: "var(--color-status-good)" }}
                                />
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>

              {result.qubo && (
                <Card
                  title="Ma trận QUBO"
                  subtitle="Biểu diễn bài toán chọn danh mục dưới dạng tối ưu nhị phân — sẵn sàng cho thí nghiệm QAOA/lượng tử"
                >
                  <div className="overflow-x-auto">
                    <table className="text-[10px] tabular-nums">
                      <thead>
                        <tr>
                          <th className="p-1.5" />
                          {Object.keys(result.qubo).map((key) => (
                            <th key={key} className="p-1.5 text-ink-3">
                              {key.replace("C_", "")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(result.qubo).map(([rowKey, row]) => (
                          <tr key={rowKey}>
                            <th className="p-1.5 text-left text-ink-3">
                              {rowKey.replace("C_", "")}
                            </th>
                            {Object.keys(result.qubo!).map((colKey) => {
                              const value = row[colKey];
                              return (
                                <td
                                  key={colKey}
                                  className="p-1.5 text-center text-ink-2"
                                  style={{
                                    background:
                                      value !== undefined && value < 0
                                        ? "color-mix(in srgb, var(--color-series-4) 22%, transparent)"
                                        : "transparent",
                                  }}
                                >
                                  {value !== undefined ? value.toExponential(1) : ""}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              <Card>
                <div className="flex gap-3">
                  <CircleAlert
                    size={18}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--color-status-warning)" }}
                    aria-hidden
                  />
                  <div>
                    <p className="text-xs font-semibold text-ink">Lưu ý quan trọng</p>
                    <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-2">
                      {result.caveats.map((caveat, index) => (
                        <li key={index}>{caveat}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
