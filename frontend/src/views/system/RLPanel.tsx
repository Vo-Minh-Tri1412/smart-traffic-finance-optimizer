import { Ban, BrainCircuit, CheckCircle2, ShieldAlert, Sparkles } from "lucide-react";
import { useMemo } from "react";

import { Badge, Card } from "../../components/ui";
import { VEHICLE_LABELS } from "../../lib/domain";
import { formatNumber } from "../../lib/format";
import type { RewardWeightRow, RLResponse } from "../../lib/types";

/** Sequential blue magnitude bars for reward weights (one hue, light→dark). */
function WeightBars({
  rows,
  labels,
  max,
}: {
  rows: RewardWeightRow[];
  labels?: Record<string, string>;
  max?: number;
}) {
  const peak = max ?? Math.max(1, ...rows.map((row) => row.weight));
  const sorted = [...rows].sort((a, b) => b.weight - a.weight);
  return (
    <div className="space-y-1.5">
      {sorted.map((row) => {
        const pct = Math.max(3, (row.weight / peak) * 100);
        return (
          <div key={row.key} className="flex items-center gap-2 text-[11px]">
            <span className="w-40 shrink-0 truncate text-ink-2" title={row.key}>
              {labels?.[row.key] ?? row.key}
            </span>
            <div className="h-3 flex-1 overflow-hidden rounded bg-surface-3">
              <div
                className="h-full rounded"
                style={{
                  width: `${pct}%`,
                  background: "var(--color-series-1)",
                }}
              />
            </div>
            <span className="w-10 shrink-0 text-right tabular-nums text-ink">
              {formatNumber(row.weight)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function RLPanel({ data }: { data: RLResponse }) {
  const profile = data.reward_profile;

  const trainingConfigRows = useMemo(
    () =>
      Object.entries(data.training_config).filter(
        ([key]) => key !== "present" && key !== "path",
      ),
    [data.training_config],
  );

  return (
    <div className="space-y-5">
      {/* readiness banner */}
      <Card>
        <div className="flex flex-wrap items-start gap-4">
          <div
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl"
            style={{
              background: data.training_ready
                ? "color-mix(in srgb, var(--color-status-good) 18%, transparent)"
                : "color-mix(in srgb, var(--color-status-warning) 16%, transparent)",
            }}
          >
            {data.training_ready ? (
              <CheckCircle2 size={22} style={{ color: "var(--color-status-good)" }} aria-hidden />
            ) : (
              <ShieldAlert size={22} style={{ color: "var(--color-status-warning)" }} aria-hidden />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-ink">
                {data.training_ready ? "Sẵn sàng train RL" : "RL chưa đủ điều kiện train"}
              </h3>
              <Badge color={data.policy_trained ? "var(--color-status-good)" : "var(--color-series-4)"}>
                {data.policy_trained ? "Đã có policy" : "Chưa có policy"}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-ink-3">{data.policy_note}</p>

            {data.blockers.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {data.blockers.map((blocker, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-[11px] text-ink-2"
                  >
                    <Ban
                      size={13}
                      className="mt-0.5 shrink-0"
                      style={{ color: "var(--color-status-critical)" }}
                      aria-hidden
                    />
                    {blocker}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>

      {data.reward_profile_error && (
        <Card>
          <p className="text-xs" style={{ color: "var(--color-status-warning)" }}>
            {data.reward_profile_error}
          </p>
        </Card>
      )}

      {profile && (
        <>
          <Card
            title={
              <span className="flex items-center gap-2">
                <Sparkles size={14} aria-hidden />
                Reward profile: {profile.profile_id}
              </span>
            }
            subtitle={profile.description}
            actions={
              <div className="flex items-center gap-2">
                <Badge
                  color={
                    profile.status === "approved"
                      ? "var(--color-status-good)"
                      : "var(--color-status-warning)"
                  }
                >
                  {profile.status}
                </Badge>
                <Badge>{profile.owner}</Badge>
              </div>
            }
          >
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                  Trọng số nền (base)
                </p>
                <WeightBars rows={profile.base_weights} />
                <p className="mb-2 mt-5 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                  Trọng số theo mục đích chuyến
                </p>
                <WeightBars rows={profile.trip_purpose_weights} />
              </div>
              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                  Trọng số theo loại xe
                </p>
                <WeightBars rows={profile.vehicle_type_weights} labels={VEHICLE_LABELS} />
              </div>
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Ưu tiên tuyến & khung giờ" subtitle="Nhân thêm trọng số cho luồng/giờ trọng điểm">
              <div className="space-y-2">
                {profile.route_priority_weights.map((route) => (
                  <div
                    key={route.flow_id}
                    className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2 text-[11px]"
                  >
                    <span className="min-w-0">
                      <span className="font-medium text-ink">{route.flow_id}</span>
                      <span className="ml-2 text-ink-3">{route.description}</span>
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums text-ink">
                      ×{formatNumber(route.weight)}
                    </span>
                  </div>
                ))}
                {profile.time_window_weights.map((window) => (
                  <div
                    key={window.label}
                    className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2 text-[11px]"
                  >
                    <span className="min-w-0">
                      <span className="font-medium text-ink">{window.label}</span>
                      <span className="ml-2 text-ink-3">
                        {Math.round(window.start / 60)}–{Math.round(window.end / 60)} phút
                      </span>
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums text-ink">
                      ×{formatNumber(window.weight)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            <Card
              title="Ràng buộc cứng"
              subtitle="Không phải reward — cần lớp lọc/ghi đè hành động trước khi train"
            >
              {profile.hard_constraints.length === 0 ? (
                <p className="text-xs text-ink-3">Không có ràng buộc cứng nào.</p>
              ) : (
                <div className="space-y-2.5">
                  {profile.hard_constraints.map((constraint) => (
                    <div key={constraint.id} className="rounded-lg bg-surface-2 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-ink">{constraint.id}</span>
                        <Badge
                          color={
                            constraint.status === "implemented"
                              ? "var(--color-status-good)"
                              : "var(--color-status-critical)"
                          }
                        >
                          {constraint.status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[11px] text-ink-3">
                        {constraint.enforcement} · {constraint.vehicle_types.join(", ")}
                      </p>
                      {constraint.notes && (
                        <p className="mt-1.5 text-[10px] italic leading-relaxed text-ink-3">
                          {constraint.notes}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card
          title={
            <span className="flex items-center gap-2">
              <BrainCircuit size={14} aria-hidden />
              Observation space
            </span>
          }
          subtitle={`Phiên bản ${data.observation_space.version}`}
        >
          <div className="flex flex-wrap gap-1.5">
            {data.observation_space.feature_groups.map((group) => (
              <Badge key={group} color="var(--color-series-1)">
                {group}
              </Badge>
            ))}
          </div>
          <p className="mt-3 font-mono text-[10px] text-ink-3">
            {data.observation_space.source_document}
          </p>
        </Card>

        <Card title="Action space" subtitle={`Phiên bản ${data.action_space.version}`}>
          <p className="text-xs font-medium text-ink">{data.action_space.action_type}</p>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
            {data.action_space.caveat}
          </p>
        </Card>

        <Card title="Cấu hình training" subtitle="Từ file config ví dụ (chưa chạy)">
          {data.training_config.present ? (
            <dl className="space-y-1 text-[11px]">
              {trainingConfigRows.map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="text-ink-3">{key}</dt>
                  <dd className="text-right font-medium text-ink-2">{String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-xs text-ink-3">Chưa có file cấu hình training.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
