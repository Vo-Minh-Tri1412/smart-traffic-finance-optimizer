import { useQuery } from "@tanstack/react-query";
import { Archive, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { Badge, Card, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import { api } from "../lib/api";
import { formatInt, formatNumber, formatSeconds } from "../lib/format";
import type { RuntimeTripAccountingView } from "../lib/types";

const NO_DATA = "Chưa có dữ liệu";

const STATE_LABELS: Record<string, string> = {
  verified: "verified · Manifest đã xác minh",
  outputs_verified: "outputs_verified · Đầu ra đã xác minh",
  unsealed: "unsealed · Run chưa seal",
  verification_failed: "verification_failed · Xác minh thất bại",
  unavailable: "unavailable · Không khả dụng",
  not_found: "not_found · Không tìm thấy",
  not_configured: "not_configured · Chưa cấu hình",
  available: "available · Có dữ liệu",
  partial: "partial · Dữ liệu một phần",
};

function stateLabel(state: string | null | undefined): string {
  if (state == null || state === "") return NO_DATA;
  return STATE_LABELS[state] ?? state;
}

function StateBadge({ state }: { state: string | null | undefined }) {
  const color =
    state === "verified" || state === "outputs_verified" || state === "available"
      ? "var(--color-status-good)"
      : state === "unsealed" || state === "unavailable" || state === "not_configured" || state === "partial"
        ? "var(--color-status-warning)"
        : "var(--color-status-critical)";

  return <Badge color={color}>{stateLabel(state)}</Badge>;
}

function displayValue(value: string | number | boolean | null | undefined): string {
  if (value == null) return NO_DATA;
  if (typeof value === "boolean") return value ? "Có" : "Không";
  if (typeof value === "number") {
    return Number.isFinite(value)
      ? Number.isInteger(value)
        ? formatInt(value)
        : formatNumber(value)
      : NO_DATA;
  }
  return value || NO_DATA;
}

function ValueRow({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-hairline/70 py-2 last:border-0">
      <dt className="text-[11px] text-ink-3">{label}</dt>
      <dd className="max-w-[65%] break-words text-right text-[11px] font-medium tabular-nums text-ink-2">
        {displayValue(value)}
      </dd>
    </div>
  );
}

function RuntimeAccounting({ accounting }: { accounting: RuntimeTripAccountingView }) {
  const demand = accounting.demand_accounting;
  const aggregate = accounting.aggregate_simulation_accounting;
  const summary = aggregate.summary;
  const statistic = aggregate.statistic;
  const demandCounts = Object.entries(demand.status_counts ?? {}).sort(([left], [right]) =>
    left.localeCompare(right),
  );

  return (
    <div className="space-y-5">
      <div
        className="flex items-start gap-3 rounded-xl border px-4 py-3 text-xs text-ink-2"
        style={{
          borderColor: "color-mix(in srgb, var(--color-status-warning) 35%, transparent)",
          background: "color-mix(in srgb, var(--color-status-warning) 8%, transparent)",
        }}
      >
        <ShieldAlert size={16} className="mt-0.5 shrink-0" style={{ color: "var(--color-status-warning)" }} aria-hidden />
        <p className="leading-relaxed">
          Bằng chứng chỉ thuộc managed debug runtime accounting; không chứng minh action safety hoặc
          chấp nhận nghiên cứu. Số va chạm của simulator không chứng minh đầy đủ an toàn hành động.
        </p>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card
          title="Demand accounting"
          subtitle="Đếm theo requested vehicle trip; không quy đổi thành người hoặc occupancy"
        >
          <div className="mb-3 flex flex-wrap gap-2">
            <StateBadge state={demand.status} />
            <Badge>{demand.scope}</Badge>
          </div>
          <dl>
            <ValueRow label="Lý do" value={demand.reason} />
            <ValueRow label="Intended trip count" value={demand.intended_trip_count} />
            <ValueRow label="Số dòng ledger thô" value={demand.raw_ledger_row_count} />
            <ValueRow label="TripInfo đã quan sát" value={demand.tripinfo_observed_count} />
            <ValueRow label="Đã yêu cầu TripInfo unfinished" value={demand.tripinfo_unfinished_requested} />
          </dl>
          <div className="mt-4 border-t border-hairline pt-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-3">
              Trạng thái từng trip
            </p>
            {demandCounts.length ? (
              <dl>
                {demandCounts.map(([status, count]) => (
                  <ValueRow key={status} label={status} value={count} />
                ))}
              </dl>
            ) : (
              <p className="text-[11px] text-ink-3">{NO_DATA}</p>
            )}
          </div>
        </Card>

        <Card
          title="Aggregate simulation accounting"
          subtitle="Counter ở phạm vi toàn mô phỏng; giữ nguyên null nếu nguồn thiếu dữ liệu"
        >
          <div className="mb-3 flex flex-wrap gap-2">
            <StateBadge state={aggregate.status} />
            <Badge>{aggregate.scope}</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <section className="rounded-xl bg-surface-2 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold text-ink">Summary</h3>
                <StateBadge state={summary.status} />
              </div>
              <dl>
                <ValueRow
                  label="Thời điểm cuối"
                  value={
                    summary.final_step_time_seconds == null
                      ? null
                      : formatSeconds(summary.final_step_time_seconds)
                  }
                />
                <ValueRow label="Loaded" value={summary.loaded} />
                <ValueRow label="Inserted" value={summary.inserted} />
                <ValueRow label="Waiting" value={summary.waiting} />
                <ValueRow label="Arrived" value={summary.arrived} />
                <ValueRow label="Running" value={summary.running} />
                <ValueRow label="Ended" value={summary.ended} />
              </dl>
            </section>
            <section className="rounded-xl bg-surface-2 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold text-ink">Statistic</h3>
                <StateBadge state={statistic.status} />
              </div>
              <dl>
                <ValueRow label="Teleports" value={statistic.total_teleports} />
                <ValueRow label="Safety collisions" value={statistic.safety_collisions} />
              </dl>
            </section>
          </div>
          <div className="mt-4 space-y-1 border-t border-hairline pt-3">
            {(aggregate.limitations ?? []).map((limitation) => (
              <p key={limitation} className="text-[10px] leading-relaxed text-ink-3">
                {limitation}
              </p>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function ExperimentsView() {
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const experimentsQuery = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const experiments = experimentsQuery.data?.experiments ?? [];
  const selectedExperiment =
    experiments.find((item) => item.experiment_id === selectedExperimentId) ?? experiments[0];
  const discoveredRunIds = selectedExperiment?.discovered_run_ids ?? [];
  const activeRunId = discoveredRunIds.includes(selectedRunId)
    ? selectedRunId
    : (discoveredRunIds[0] ?? "");
  const hasSelection = Boolean(selectedExperiment && activeRunId);

  const runQuery = useQuery({
    queryKey: ["experiment-run", selectedExperiment?.experiment_id, activeRunId],
    queryFn: () => api.experimentRun(selectedExperiment!.experiment_id, activeRunId),
    enabled: hasSelection,
  });
  const accountingQuery = useQuery({
    queryKey: ["experiment-runtime-accounting", selectedExperiment?.experiment_id, activeRunId],
    queryFn: () => api.experimentRuntimeAccounting(selectedExperiment!.experiment_id, activeRunId),
    enabled: hasSelection,
  });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-ink">
            <Archive size={20} aria-hidden />
            Experiments
          </h1>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-3">
            Duyệt manifest và runtime accounting đã được xác minh. Trang này chỉ đọc artifact; không
            chạy mô phỏng hoặc tính lại metric, reward hay finance.
          </p>
        </div>
        {experimentsQuery.data && <StateBadge state={experimentsQuery.data.status} />}
      </header>

      {experimentsQuery.isPending ? (
        <Card title="Danh sách experiments">
          <LoadingState />
        </Card>
      ) : experimentsQuery.isError || !experimentsQuery.data ? (
        <Card title="Danh sách experiments">
          <ErrorState title="Không tải được danh sách experiments" detail="API chỉ đọc hiện không khả dụng." />
        </Card>
      ) : experimentsQuery.data.status !== "available" ? (
        <Card title="Danh sách experiments">
          <div className="flex flex-wrap items-center gap-3">
            <StateBadge state={experimentsQuery.data.status} />
            <p className="text-xs text-ink-3">
              {experimentsQuery.data.status === "not_configured"
                ? "Backend chưa cấu hình thư mục experiments. Không dùng dữ liệu fixture thay thế."
                : "Không thể đọc thư mục experiments đã cấu hình."}
            </p>
          </div>
        </Card>
      ) : (
        <Card
          title="Experiments đã phát hiện"
          subtitle={`${experiments.length} experiment · run IDs bên dưới chỉ là thư mục được phát hiện, chưa được xác minh`}
        >
          {experiments.length === 0 ? (
            <EmptyState title="Chưa có experiment nào" detail="Backend không trả về experiment trong thư mục đã cấu hình." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-xs">
                <thead>
                  <tr className="border-b border-hairline text-[10px] uppercase tracking-wide text-ink-3">
                    <th className="pb-2 pr-3 font-medium">Experiment ID</th>
                    <th className="pb-2 pr-3 font-medium">Trạng thái</th>
                    <th className="pb-2 pr-3 font-medium">Mode</th>
                    <th className="pb-2 pr-3 font-medium">Project ID</th>
                    <th className="pb-2 font-medium">Run IDs phát hiện · chưa xác minh</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.map((item) => (
                    <tr
                      key={item.experiment_id}
                      className={`border-b border-hairline/70 align-top transition hover:bg-surface-2/50 ${
                        selectedExperiment?.experiment_id === item.experiment_id ? "bg-surface-2/40" : ""
                      }`}
                    >
                      <td className="py-3 pr-3 font-mono text-ink">{item.experiment_id}</td>
                      <td className="py-3 pr-3"><StateBadge state={item.state} /></td>
                      <td className="py-3 pr-3 text-ink-2">{displayValue(item.mode)}</td>
                      <td className="py-3 pr-3 font-mono text-ink-2">{displayValue(item.project_id)}</td>
                      <td className="py-3">
                        {item.discovered_run_ids.length ? (
                          <div className="flex flex-wrap gap-1.5">
                            {item.discovered_run_ids.map((runId) => (
                              <code key={runId} className="rounded bg-surface-3 px-1.5 py-1 text-[10px] text-ink-2">
                                {runId} · chưa xác minh
                              </code>
                            ))}
                          </div>
                        ) : (
                          <span className="text-ink-3">{NO_DATA}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {experimentsQuery.data?.status === "available" && experiments.length > 0 && (
        <Card title="Chọn run để xác minh" subtitle="API tải trạng thái manifest/output và accounting riêng cho run đã chọn">
          <div className="flex flex-wrap items-end gap-4">
            <Select
              label="Experiment"
              value={selectedExperiment?.experiment_id ?? ""}
              onChange={(value) => {
                setSelectedExperimentId(value);
                setSelectedRunId("");
              }}
              options={experiments.map((item) => ({
                value: item.experiment_id,
                label: `${item.experiment_id} · ${stateLabel(item.state)}`,
              }))}
            />
            <Select
              label="Run ID (discovered)"
              value={activeRunId}
              onChange={setSelectedRunId}
              options={[
                { value: "", label: "Chọn run ID" },
                ...discoveredRunIds.map((runId) => ({
                  value: runId,
                  label: `${runId} · chưa xác minh`,
                })),
              ]}
            />
            {!discoveredRunIds.length && (
              <p className="pb-1 text-xs text-ink-3">Experiment này chưa có run directory được phát hiện.</p>
            )}
          </div>
        </Card>
      )}

      {hasSelection && (
        <>
          <Card title="Run verification" subtitle={`${selectedExperiment?.experiment_id} / ${activeRunId}`}>
            {runQuery.isPending ? (
              <LoadingState label="Đang xác minh run…" />
            ) : runQuery.isError || !runQuery.data ? (
              <ErrorState title="Không tải được trạng thái xác minh run" detail="API xác minh run hiện không khả dụng." />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <StateBadge state={runQuery.data.state} />
                  <span className="font-mono text-[11px] text-ink-3">
                    {displayValue(runQuery.data.content_sha256)}
                  </span>
                </div>
                <dl className="grid gap-x-6 md:grid-cols-2">
                  <ValueRow label="Mode" value={runQuery.data.mode} />
                  <ValueRow label="Case ID" value={runQuery.data.case_id} />
                  <ValueRow label="Split" value={runQuery.data.split} />
                  <ValueRow label="Seed" value={runQuery.data.seed} />
                  <ValueRow label="Controller ID" value={runQuery.data.controller_id} />
                </dl>
                <div>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-3">
                    Expected outputs
                  </p>
                  {runQuery.data.outputs.length ? (
                    <div className="space-y-2">
                      {runQuery.data.outputs.map((output) => (
                        <div key={output.role} className="rounded-xl bg-surface-2 px-3 py-2.5">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <code className="text-[11px] text-ink">{output.role}</code>
                            <StateBadge state={output.state} />
                          </div>
                          <p className="mt-1 break-all font-mono text-[10px] text-ink-3">
                            SHA-256: {displayValue(output.sha256)} · {displayValue(output.bytes)} bytes
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-ink-3">{NO_DATA}</p>
                  )}
                </div>
              </div>
            )}
          </Card>

          <Card title="Runtime accounting" subtitle="Chỉ đọc khi output đã seal và được hash-verify">
            {accountingQuery.isPending ? (
              <LoadingState label="Đang xác minh runtime accounting…" />
            ) : accountingQuery.isError || !accountingQuery.data ? (
              <ErrorState title="Không tải được runtime accounting" detail="API accounting hiện không khả dụng." />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <StateBadge state={accountingQuery.data.state} />
                  <span className="text-[11px] text-ink-3">
                    {accountingQuery.data.state === "unsealed"
                      ? "Payload chưa được đọc vì run chưa seal."
                      : accountingQuery.data.state === "unavailable"
                        ? "Run không khai báo runtime_accounting output."
                        : null}
                  </span>
                </div>
                {accountingQuery.data.state === "available" && accountingQuery.data.accounting ? (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <StateBadge state={accountingQuery.data.accounting.execution_status} />
                      <Badge>{accountingQuery.data.accounting.evidence_scope}</Badge>
                    </div>
                    <RuntimeAccounting accounting={accountingQuery.data.accounting} />
                  </>
                ) : (
                  <p className="text-xs text-ink-3">Runtime accounting: {stateLabel(accountingQuery.data.state)}.</p>
                )}
              </div>
            )}
          </Card>
        </>
      )}

      {experimentsQuery.data?.status === "available" && experiments.length > 0 && !hasSelection && (
        <Card title="Runtime accounting">
          <EmptyState title="Chưa chọn được run" detail="Chọn một run ID đã phát hiện để xem trạng thái xác minh." />
        </Card>
      )}
    </div>
  );
}
