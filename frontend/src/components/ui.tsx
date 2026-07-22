import { motion } from "framer-motion";
import { AlertTriangle, Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className={`rounded-2xl border border-hairline bg-surface/90 shadow-[0_8px_30px_rgba(0,0,0,0.25)] backdrop-blur ${className}`}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </motion.section>
  );
}

export function StatTile({
  icon: Icon,
  label,
  value,
  hint,
  accent = "var(--color-accent)",
}: {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  accent?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="rounded-2xl border border-hairline bg-surface/90 p-4"
    >
      <div className="flex items-center gap-2 text-xs font-medium text-ink-3">
        <span
          className="grid h-7 w-7 place-items-center rounded-lg"
          style={{ background: "color-mix(in srgb, currentColor 0%, transparent)" }}
        >
          <Icon size={16} style={{ color: accent }} aria-hidden />
        </span>
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-3">{hint}</div>}
    </motion.div>
  );
}

export function Badge({
  children,
  color = "var(--color-ink-3)",
}: {
  children: ReactNode;
  color?: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-hairline px-2.5 py-0.5 text-[11px] font-medium text-ink-2"
      style={{ background: "rgba(255,255,255,0.03)" }}
    >
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: color }}
        aria-hidden
      />
      {children}
    </span>
  );
}

export function Select({
  value,
  onChange,
  options,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label?: string;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-ink-3">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-hairline bg-surface-2 px-2.5 py-1.5 text-xs font-medium text-ink outline-none transition hover:border-white/20 focus:border-accent"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function LoadingState({ label = "Đang tải dữ liệu…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-3">
      <Loader2 className="animate-spin" size={16} aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <AlertTriangle size={22} style={{ color: "var(--color-status-warning)" }} aria-hidden />
      <p className="text-sm font-medium text-ink">{title}</p>
      {detail && <p className="max-w-md text-xs text-ink-3">{detail}</p>}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-14 text-center">
      <p className="text-sm font-medium text-ink-2">{title}</p>
      {detail && <p className="max-w-md text-xs text-ink-3">{detail}</p>}
    </div>
  );
}
