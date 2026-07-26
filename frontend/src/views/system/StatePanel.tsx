import { CheckStatusBadge } from "../../components/StatusBadge";
import { Card } from "../../components/ui";
import type { SystemStateResponse } from "../../lib/types";

export default function StatePanel({ data }: { data: SystemStateResponse }) {
  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <p className="text-sm font-medium text-ink">{data.summary}</p>
          <div className="ml-auto flex items-center gap-5 text-xs">
            <span className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: "var(--color-status-good)" }}
              />
              <span className="tabular-nums text-ink">{data.ok_count}</span>
              <span className="text-ink-3">đạt</span>
            </span>
            <span className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: "var(--color-status-warning)" }}
              />
              <span className="tabular-nums text-ink">{data.warn_count}</span>
              <span className="text-ink-3">cảnh báo</span>
            </span>
            <span className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: "var(--color-status-critical)" }}
              />
              <span className="tabular-nums text-ink">{data.fail_count}</span>
              <span className="text-ink-3">lỗi</span>
            </span>
          </div>
        </div>
      </Card>

      <Card
        title="Kiểm tra sẵn sàng"
        subtitle="Trạng thái runtime, gói phụ thuộc và dữ liệu cần cho backend"
      >
        <ul className="divide-y divide-hairline">
          {data.checks.map((check) => (
            <li key={check.name} className="flex items-center gap-3 py-2.5 text-xs">
              <CheckStatusBadge status={check.status} />
              <span className="font-medium text-ink">{check.name}</span>
              <span className="ml-auto max-w-[60%] truncate text-right font-mono text-[10px] text-ink-3">
                {check.detail}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
