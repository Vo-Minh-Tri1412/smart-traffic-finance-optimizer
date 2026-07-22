import { CheckCircle2, CircleDashed, CircleDot, TriangleAlert, XCircle } from "lucide-react";

import { checkStatusStyle, stageStatusStyle } from "../lib/domain";

const STAGE_ICON = {
  implemented: CheckCircle2,
  partial: CircleDot,
  scaffold: CircleDashed,
  planned: CircleDashed,
} as const;

export function StageStatusBadge({ status }: { status: string }) {
  const { label, color } = stageStatusStyle(status);
  const Icon = STAGE_ICON[status as keyof typeof STAGE_ICON] ?? CircleDashed;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
      style={{
        color,
        background: "color-mix(in srgb, currentColor 12%, transparent)",
      }}
    >
      <Icon size={12} aria-hidden />
      {label}
    </span>
  );
}

const CHECK_ICON = {
  ok: CheckCircle2,
  warn: TriangleAlert,
  fail: XCircle,
} as const;

export function CheckStatusBadge({ status }: { status: string }) {
  const { label, color } = checkStatusStyle(status);
  const Icon = CHECK_ICON[status as keyof typeof CHECK_ICON] ?? CircleDot;
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium" style={{ color }}>
      <Icon size={13} aria-hidden />
      {label}
    </span>
  );
}
