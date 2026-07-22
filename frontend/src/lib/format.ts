const numberFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });
const intFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
const compactFormat = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

export function formatInt(value: number): string {
  return intFormat.format(value);
}

export function formatCompact(value: number): string {
  return compactFormat.format(value);
}

export function formatVnd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${numberFormat.format(value / 1_000_000_000)} tỷ ₫`;
  if (abs >= 1_000_000) return `${numberFormat.format(value / 1_000_000)} triệu ₫`;
  if (abs >= 1_000) return `${numberFormat.format(value / 1_000)} nghìn ₫`;
  return `${intFormat.format(value)} ₫`;
}

export function formatSeconds(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 3600) return `${numberFormat.format(value / 3600)} giờ`;
  if (abs >= 60) return `${numberFormat.format(value / 60)} phút`;
  return `${numberFormat.format(value)} giây`;
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(hh)}:${pad(mm)}:${pad(ss)}`;
}

export function formatDateTime(iso: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

export function formatPercent(value: number): string {
  return `${numberFormat.format(value)}%`;
}
