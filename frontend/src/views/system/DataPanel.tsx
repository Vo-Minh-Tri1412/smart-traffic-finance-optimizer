import { Check, Database, FileCog, HardDrive, X } from "lucide-react";

import { StageStatusBadge } from "../../components/StatusBadge";
import { Badge, Card } from "../../components/ui";
import type { DataResponse, DistrictsResponse } from "../../lib/types";

export default function DataPanel({
  data,
  districts,
}: {
  data: DataResponse;
  districts?: DistrictsResponse;
}) {
  const store = data.run_store;
  return (
    <div className="space-y-5">
      {districts && (
        <Card
          title="Registry map / district"
          subtitle="District đang hoạt động và các chỗ dành sẵn cho map thật sau này"
        >
          <div className="grid gap-3 md:grid-cols-3">
            {districts.districts.map((entry) => (
              <div
                key={entry.district_id}
                className="rounded-xl border border-hairline bg-surface-2 p-3.5"
                style={
                  entry.active
                    ? { borderColor: "color-mix(in srgb, var(--color-series-1) 45%, transparent)" }
                    : undefined
                }
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">{entry.name}</p>
                  <Badge
                    color={entry.active ? "var(--color-status-good)" : "var(--color-ink-3)"}
                  >
                    {entry.active ? "đang dùng" : "dự kiến"}
                  </Badge>
                </div>
                <p className="mt-1 font-mono text-[10px] text-ink-3">{entry.district_id}</p>
                <p className="mt-2 text-[11px] leading-relaxed text-ink-3">{entry.note}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Card
          title={
            <span className="flex items-center gap-2">
              <Database size={14} aria-hidden />
              Kho run dashboard
            </span>
          }
          subtitle={store.directory}
        >
          <div className="mb-3 text-3xl font-semibold tabular-nums text-ink">
            {store.run_count}
            <span className="ml-2 text-xs font-normal text-ink-3">run đã lưu</span>
          </div>
          <div className="space-y-2 text-[11px]">
            <div>
              <p className="text-ink-3">Kịch bản</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {store.scenarios.length > 0 ? (
                  store.scenarios.map((scenario) => (
                    <Badge key={scenario} color="var(--color-series-1)">
                      {scenario}
                    </Badge>
                  ))
                ) : (
                  <span className="text-ink-3">chưa có</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-ink-3">Controller</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {store.controllers.length > 0 ? (
                  store.controllers.map((controller) => (
                    <Badge key={controller} color="var(--color-series-2)">
                      {controller}
                    </Badge>
                  ))
                ) : (
                  <span className="text-ink-3">chưa có</span>
                )}
              </div>
            </div>
          </div>
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <HardDrive size={14} aria-hidden />
              Luồng dữ liệu & artifact
            </span>
          }
          subtitle="Code trên Git, file lớn trên DVC + Google Drive Data Hub"
        >
          <div className="space-y-2.5">
            {data.streams.map((stream) => (
              <div key={stream.id} className="rounded-lg bg-surface-2 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-ink">{stream.name}</span>
                  <StageStatusBadge status={stream.status} />
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-ink-3">{stream.summary}</p>
                <p className="mt-1.5 font-mono text-[10px] text-ink-3">{stream.location}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Cấu hình DVC / Drive" subtitle="Nguyên tắc tách code khỏi dữ liệu lớn">
          <dl className="space-y-2 text-[11px]">
            {Object.entries(data.dvc).map(([key, value]) => (
              <div key={key} className="flex flex-col gap-0.5">
                <dt className="text-ink-3">{key}</dt>
                <dd className="font-mono text-ink-2 break-all">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <FileCog size={14} aria-hidden />
              File cấu hình
            </span>
          }
          subtitle="Config ví dụ trong configs/ — nguồn tham số cho các stream"
        >
          <ul className="space-y-1.5">
            {data.configs.map((config) => (
              <li
                key={config.name}
                className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-[11px]"
              >
                {config.present ? (
                  <Check size={13} style={{ color: "var(--color-status-good)" }} aria-hidden />
                ) : (
                  <X size={13} style={{ color: "var(--color-status-critical)" }} aria-hidden />
                )}
                <span className="font-mono text-ink-2">{config.name}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
