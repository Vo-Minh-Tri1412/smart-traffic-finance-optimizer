import { useQuery } from "@tanstack/react-query";
import {
  GitCompareArrows,
  FolderOpen,
  LayoutDashboard,
  Map,
  PiggyBank,
  PlayCircle,
  Radio,
  ServerCog,
  TrafficCone,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { api } from "../lib/api";

const NAV_ITEMS = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard, end: true },
  { to: "/district", label: "Bản đồ quận", icon: Map, end: false },
  { to: "/runs", label: "Mô phỏng", icon: TrafficCone, end: false },
  { to: "/experiments", label: "Experiments", icon: FolderOpen, end: false },
  { to: "/replay", label: "Replay", icon: PlayCircle, end: false },
  { to: "/compare", label: "So sánh", icon: GitCompareArrows, end: false },
  { to: "/finance", label: "Ngân sách", icon: PiggyBank, end: false },
  { to: "/system", label: "Hệ thống", icon: ServerCog, end: false },
];

function ConnectionPill() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
    retry: false,
  });

  const online = health.isSuccess;
  const color = online ? "var(--color-status-good)" : "var(--color-status-critical)";
  const label = online ? "Backend trực tuyến" : "Backend ngoại tuyến";

  return (
    <div
      className="flex items-center gap-2 rounded-full border border-hairline px-3 py-1.5 text-[11px] font-medium text-ink-2"
      title={online ? health.data?.spec_path : "Chạy: python -m ai_quantum_hvtc dashboard"}
    >
      <Radio size={13} style={{ color }} aria-hidden />
      <span className="relative flex h-2 w-2">
        {online && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ background: color }}
          />
        )}
        <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: color }} />
      </span>
      {label}
    </div>
  );
}

export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-hairline bg-surface/60 backdrop-blur">
        <div className="flex items-center gap-3 px-5 pb-4 pt-6">
          <div
            className="grid h-10 w-10 place-items-center rounded-xl text-white"
            style={{
              background:
                "linear-gradient(135deg, var(--color-series-1), color-mix(in srgb, var(--color-series-1) 40%, #0b0e14))",
            }}
          >
            <TrafficCone size={20} aria-hidden />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-ink">AIQ HVTC</p>
            <p className="text-[11px] leading-tight text-ink-3">Giao thông · Tài chính công</p>
          </div>
        </div>

        <nav className="mt-2 flex flex-1 flex-col gap-1 px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition ${
                  isActive
                    ? "bg-surface-3 text-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                    : "text-ink-3 hover:bg-surface-2 hover:text-ink-2"
                }`
              }
            >
              <Icon size={17} aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 pb-5">
          <ConnectionPill />
          <p className="mt-3 px-1 text-[10px] leading-relaxed text-ink-3">
            Dashboard replay artifact mô phỏng — không chạy vật lý giao thông trong trình duyệt.
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
