import type { ReactNode } from "react";

export interface TooltipRow {
  color?: string;
  name: ReactNode;
  value: ReactNode;
}

/**
 * Shared tooltip body for Recharts charts: dark raised surface, ink text,
 * a colored chip per series (identity via mark, not colored text).
 */
export function ChartTooltipBody({ title, rows }: { title?: ReactNode; rows: TooltipRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="min-w-40 rounded-xl border border-hairline bg-surface-2/95 px-3 py-2.5 shadow-xl backdrop-blur">
      {title && <p className="mb-1.5 text-[11px] font-semibold text-ink">{title}</p>}
      <div className="space-y-1">
        {rows.map((row, index) => (
          <div key={index} className="flex items-center justify-between gap-4 text-[11px]">
            <span className="flex items-center gap-1.5 text-ink-3">
              {row.color && (
                <span
                  className="h-2 w-2 rounded-[3px]"
                  style={{ background: row.color }}
                  aria-hidden
                />
              )}
              {row.name}
            </span>
            <span className="font-medium tabular-nums text-ink">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
