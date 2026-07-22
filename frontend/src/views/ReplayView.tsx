import { useQuery } from "@tanstack/react-query";
import { Gauge, Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltipBody } from "../components/ChartTooltip";
import DistrictMap from "../components/DistrictMap";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import { api } from "../lib/api";
import { controllerLabel, engineLabel, scenarioLabel } from "../lib/domain";
import { formatClock, formatNumber } from "../lib/format";

const SPEED_OPTIONS = [0.5, 1, 2, 4];
const BASE_FRAME_MS = 700;

export default function ReplayView() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.runs });
  const district = useQuery({ queryKey: ["district"], queryFn: api.district });

  const replayableRuns = useMemo(
    () => (runsQuery.data?.runs ?? []).filter((run) => run.trace_frames > 0),
    [runsQuery.data],
  );

  const activeRunId = runId ?? replayableRuns[0]?.run_id ?? null;
  const activeRun = replayableRuns.find((run) => run.run_id === activeRunId) ?? null;

  const traceQuery = useQuery({
    queryKey: ["trace", activeRunId],
    queryFn: () => api.runTrace(activeRunId!),
    enabled: activeRunId !== null,
    staleTime: Infinity,
  });

  const frames = useMemo(() => traceQuery.data?.frames ?? [], [traceQuery.data]);

  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset playback when switching runs.
  useEffect(() => {
    setFrameIndex(0);
    setPlaying(false);
  }, [activeRunId]);

  useEffect(() => {
    if (!playing || frames.length === 0) return;
    timerRef.current = setInterval(() => {
      setFrameIndex((current) => {
        if (current >= frames.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, BASE_FRAME_MS / speed);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [playing, speed, frames.length]);

  const frame = frames[Math.min(frameIndex, Math.max(frames.length - 1, 0))];

  const queues = useMemo(() => {
    const map: Record<string, number> = {};
    for (const item of frame?.intersection_queues ?? []) {
      map[item.intersection_id] = item.queue_vehicles;
    }
    return map;
  }, [frame]);

  const chartData = useMemo(
    () =>
      frames.map((item, index) => ({
        index,
        time: item.time_seconds,
        totalQueue:
          item.intersection_queues?.reduce((sum, queue) => sum + queue.queue_vehicles, 0) ?? 0,
        avgWait: item.metrics?.average_waiting_time_seconds ?? 0,
      })),
    [frames],
  );

  const eventsUpToNow = useMemo(() => {
    const list: { time: number; text: string }[] = [];
    frames.slice(0, frameIndex + 1).forEach((item) => {
      for (const event of item.events ?? []) {
        if (event.type === "scenario_start") continue;
        list.push({ time: item.time_seconds, text: String(event.type) });
      }
    });
    return list.slice(-6).reverse();
  }, [frames, frameIndex]);

  if (runsQuery.isPending || district.isPending) return <LoadingState />;
  if (runsQuery.isError || district.isError || !district.data) {
    return (
      <ErrorState
        title="Không tải được dữ liệu replay"
        detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
      />
    );
  }
  if (replayableRuns.length === 0) {
    return (
      <EmptyState
        title="Chưa có run nào kèm trace"
        detail="Chạy một mô phỏng trong trang Mô phỏng để tạo trace replay."
      />
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Replay mô phỏng</h1>
          <p className="mt-1 text-xs text-ink-3">
            Phát lại trace tổng hợp theo từng bước thời gian: trạng thái đèn, hàng đợi và sự kiện.
          </p>
        </div>
        <Select
          label="Run"
          value={activeRunId ?? ""}
          onChange={(value) => navigate(`/replay/${value}`)}
          options={replayableRuns.map((run) => ({
            value: run.run_id,
            label: `${scenarioLabel(run.scenario_id)} · ${controllerLabel(run.controller_id)} · seed ${run.seed}`,
          }))}
        />
      </header>

      {activeRun && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge color="var(--color-series-1)">{scenarioLabel(activeRun.scenario_id)}</Badge>
          <Badge color="var(--color-series-2)">{controllerLabel(activeRun.controller_id)}</Badge>
          <Badge>{engineLabel(activeRun.engine_id)}</Badge>
          <Badge>seed {activeRun.seed}</Badge>
          <Badge>{activeRun.trace_frames} khung</Badge>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <Card className="min-w-0">
          {traceQuery.isPending ? (
            <LoadingState label="Đang tải trace…" />
          ) : (
            <>
              <DistrictMap
                intersections={district.data.intersections}
                roads={district.data.roads}
                zones={district.data.zones}
                lightStates={frame?.traffic_lights}
                queues={queues}
                showZoneChips={false}
              />

              {/* playback controls */}
              <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-surface-2 px-4 py-3">
                <button
                  type="button"
                  onClick={() => setPlaying(!playing)}
                  className="grid h-9 w-9 place-items-center rounded-full text-white transition hover:brightness-110"
                  style={{ background: "var(--color-series-1)" }}
                  aria-label={playing ? "Tạm dừng" : "Phát"}
                >
                  {playing ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setFrameIndex(0);
                    setPlaying(false);
                  }}
                  className="grid h-8 w-8 place-items-center rounded-full border border-hairline text-ink-3 transition hover:bg-surface-3 hover:text-ink"
                  aria-label="Về đầu"
                >
                  <RotateCcw size={14} />
                </button>

                <input
                  type="range"
                  min={0}
                  max={Math.max(frames.length - 1, 0)}
                  value={frameIndex}
                  onChange={(event) => {
                    setFrameIndex(Number(event.target.value));
                    setPlaying(false);
                  }}
                  className="min-w-40 flex-1 accent-(--color-series-1)"
                  aria-label="Dòng thời gian"
                />

                <span className="w-20 text-right font-mono text-xs tabular-nums text-ink">
                  {formatClock(frame?.time_seconds ?? 0)}
                </span>

                <label className="flex items-center gap-1.5 text-xs text-ink-3">
                  <Gauge size={13} aria-hidden />
                  <select
                    value={speed}
                    onChange={(event) => setSpeed(Number(event.target.value))}
                    className="rounded-lg border border-hairline bg-surface-3 px-2 py-1 text-xs font-medium text-ink outline-none"
                  >
                    {SPEED_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}×
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {/* legends: identity never by color alone */}
              <div className="mt-3 flex flex-wrap items-center gap-4 text-[10px] text-ink-3">
                <span className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: "var(--color-status-good)" }}
                  />
                  Đèn xanh
                </span>
                <span className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: "var(--color-status-warning)" }}
                  />
                  Đèn vàng
                </span>
                <span className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: "var(--color-status-critical)" }}
                  />
                  Đèn đỏ
                </span>
                <span className="ml-auto flex items-center gap-2">
                  Hàng đợi ít
                  <span
                    className="h-2 w-24 rounded-full"
                    style={{
                      background:
                        "linear-gradient(90deg,#cde2fb,#9ec5f4,#6da7ec,#3987e5,#256abf,#184f95)",
                    }}
                  />
                  nhiều (kích thước nút cũng tăng theo)
                </span>
              </div>
            </>
          )}
        </Card>

        <div className="space-y-5">
          <Card title="Diễn biến toàn mạng" subtitle="Tổng hàng đợi theo thời gian mô phỏng">
            <div className="h-52">
              <ResponsiveContainer>
                <AreaChart data={chartData} margin={{ top: 6, right: 6 }}>
                  <defs>
                    <linearGradient id="queueFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-series-1)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="var(--color-series-1)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} strokeDasharray="0" />
                  <XAxis
                    dataKey="time"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value: number) => formatClock(value)}
                    tick={{ fontSize: 9 }}
                  />
                  <YAxis tickLine={false} axisLine={false} width={34} tick={{ fontSize: 9 }} />
                  <Tooltip
                    content={({ active, payload }) =>
                      active && payload?.length ? (
                        <ChartTooltipBody
                          title={formatClock(Number(payload[0].payload.time))}
                          rows={[
                            {
                              color: "var(--color-series-1)",
                              name: "Tổng hàng đợi",
                              value: `${formatNumber(Number(payload[0].payload.totalQueue))} xe`,
                            },
                          ]}
                        />
                      ) : null
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="totalQueue"
                    stroke="var(--color-series-1)"
                    strokeWidth={2}
                    fill="url(#queueFill)"
                  />
                  {frame && (
                    <ReferenceLine
                      x={frame.time_seconds}
                      stroke="var(--color-ink-2)"
                      strokeDasharray="4 4"
                    />
                  )}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card
            title="Trạng thái đèn hiện tại"
            subtitle={`Khung ${frameIndex + 1}/${frames.length}`}
          >
            {frame?.traffic_lights ? (
              <div className="grid grid-cols-4 gap-1.5">
                {Object.entries(frame.traffic_lights).map(([intersectionId, state]) => {
                  const isGreen = state.startsWith("GREEN");
                  const isYellow = state.startsWith("YELLOW");
                  const color = isGreen
                    ? "var(--color-status-good)"
                    : isYellow
                      ? "var(--color-status-warning)"
                      : "var(--color-status-critical)";
                  return (
                    <div
                      key={intersectionId}
                      className="flex items-center gap-1.5 rounded-lg bg-surface-2 px-2 py-1.5 text-[10px]"
                      title={state}
                    >
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: color }}
                        aria-hidden
                      />
                      <span className="font-medium tabular-nums text-ink-2">
                        {intersectionId}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState title="Khung này không có dữ liệu đèn" />
            )}
          </Card>

          <Card title="Sự kiện" subtitle="Các sự kiện mô phỏng tới thời điểm hiện tại">
            {eventsUpToNow.length === 0 ? (
              <p className="text-xs text-ink-3">Chưa có sự kiện đặc biệt nào.</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {eventsUpToNow.map((event, index) => (
                  <li key={index} className="flex items-center gap-2 text-ink-2">
                    <span className="font-mono text-[10px] tabular-nums text-ink-3">
                      {formatClock(event.time)}
                    </span>
                    {event.text}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
