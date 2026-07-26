import { useMemo, useState } from "react";

import { queueRampColor, trafficLightStatus, zoneStyle } from "../lib/domain";
import type { DistrictIntersection, DistrictRoad, DistrictZone } from "../lib/types";

const VIEW_W = 760;
const VIEW_H = 600;
const PAD_X = 90;
const PAD_TOP = 64;
const PAD_BOTTOM = 96;

export interface DistrictMapProps {
  intersections: DistrictIntersection[];
  roads: DistrictRoad[];
  zones?: DistrictZone[];
  closedRoads?: string[];
  lightStates?: Record<string, string>;
  queues?: Record<string, number>;
  candidateIntersections?: string[];
  selectedCandidateIntersections?: string[];
  selectedId?: string | null;
  onSelect?: (intersectionId: string | null) => void;
  showZoneChips?: boolean;
}

interface Point {
  x: number;
  y: number;
}

export default function DistrictMap({
  intersections,
  roads,
  zones = [],
  closedRoads = [],
  lightStates,
  queues,
  candidateIntersections = [],
  selectedCandidateIntersections = [],
  selectedId = null,
  onSelect,
  showZoneChips = true,
}: DistrictMapProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const positions = useMemo(() => {
    const xs = intersections.map((item) => item.x);
    const ys = intersections.map((item) => item.y);
    const minX = Math.min(...xs, 0);
    const maxX = Math.max(...xs, 1);
    const minY = Math.min(...ys, 0);
    const maxY = Math.max(...ys, 1);
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const map = new Map<string, Point>();
    for (const item of intersections) {
      map.set(item.id, {
        x: PAD_X + ((item.x - minX) / spanX) * (VIEW_W - PAD_X * 2),
        y: PAD_TOP + ((item.y - minY) / spanY) * (VIEW_H - PAD_TOP - PAD_BOTTOM),
      });
    }
    return map;
  }, [intersections]);

  const roadPairs = useMemo(() => {
    const seen = new Map<
      string,
      { road: DistrictRoad; from: Point; to: Point; closed: boolean }
    >();
    const closedSet = new Set(closedRoads);
    for (const road of roads) {
      const from = positions.get(road.from);
      const to = positions.get(road.to);
      if (!from || !to) continue;
      const key = [road.from, road.to].sort().join("~");
      const closed = closedSet.has(road.id);
      const existing = seen.get(key);
      if (!existing) {
        seen.set(key, { road, from, to, closed });
      } else if (closed) {
        existing.closed = true;
      }
    }
    return [...seen.values()];
  }, [roads, positions, closedRoads]);

  const maxQueue = useMemo(() => {
    if (!queues) return 0;
    return Math.max(0, ...Object.values(queues));
  }, [queues]);

  const candidateSet = useMemo(() => new Set(candidateIntersections), [candidateIntersections]);
  const selectedCandidateSet = useMemo(
    () => new Set(selectedCandidateIntersections),
    [selectedCandidateIntersections],
  );

  const zoneChips = useMemo(() => {
    if (!showZoneChips) return [];
    return zones
      .map((zone) => {
        const anchor = positions.get(zone.intersection_ids[0] ?? "");
        if (!anchor) return null;
        return { zone, anchor };
      })
      .filter((item): item is { zone: DistrictZone; anchor: Point } => item !== null);
  }, [zones, positions, showZoneChips]);

  return (
    <div className="relative w-full">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full"
        role="img"
        aria-label="Bản đồ mô phỏng quận: nút giao và tuyến đường"
        onClick={() => onSelect?.(null)}
      >
        {/* subtle city-block grid */}
        <defs>
          <pattern id="city-grid" width="38" height="38" patternUnits="userSpaceOnUse">
            <path
              d="M 38 0 L 0 0 0 38"
              fill="none"
              stroke="var(--color-grid)"
              strokeWidth="0.5"
              opacity="0.5"
            />
          </pattern>
        </defs>
        <rect width={VIEW_W} height={VIEW_H} fill="url(#city-grid)" rx="18" />

        {/* roads */}
        {roadPairs.map(({ road, from, to, closed }) => {
          const width = road.lanes >= 2 ? 7 : 4;
          return (
            <g key={road.id}>
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={closed ? "var(--color-status-critical)" : "#2c3550"}
                strokeWidth={width}
                strokeLinecap="round"
                strokeDasharray={closed ? "3 8" : undefined}
                opacity={closed ? 0.9 : 1}
              />
              {!closed && (
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke="#414d6e"
                  strokeWidth={1}
                  strokeDasharray="6 10"
                  strokeLinecap="round"
                  opacity={0.8}
                />
              )}
              <title>
                {`${road.id} · ${road.lanes} làn · ${road.length_km} km · ${road.speed_kph} km/h${road.truck_allowed ? " · cho xe tải" : ""}${closed ? " · ĐANG ĐÓNG" : ""}`}
              </title>
            </g>
          );
        })}

        {/* intersections */}
        {intersections.map((item) => {
          const point = positions.get(item.id);
          if (!point) return null;
          const queue = queues?.[item.id] ?? 0;
          const isHovered = hoveredId === item.id;
          const isSelected = selectedId === item.id;
          const isCandidate = candidateSet.has(item.id);
          const isChosen = selectedCandidateSet.has(item.id);
          const light = lightStates?.[item.id];
          const lightInfo = light ? trafficLightStatus(light) : null;

          const baseRadius = queues ? 9 + Math.min(9, (queue / Math.max(maxQueue, 1)) * 9) : 10;
          const fill = queues
            ? queueRampColor(queue, maxQueue)
            : isSelected || isHovered
              ? "var(--color-series-1)"
              : "var(--color-surface-3)";

          return (
            <g
              key={item.id}
              transform={`translate(${point.x} ${point.y})`}
              className="cursor-pointer"
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(isSelected ? null : item.id);
              }}
              onMouseEnter={() => setHoveredId(item.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {/* enlarged hit target */}
              <circle r={20} fill="transparent" />
              {(isSelected || isHovered) && (
                <circle
                  r={baseRadius + 7}
                  fill="none"
                  stroke="var(--color-series-1)"
                  strokeWidth={1.5}
                  opacity={0.6}
                />
              )}
              {isChosen && (
                <circle
                  r={baseRadius + 10}
                  fill="none"
                  stroke="var(--color-status-good)"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                >
                  <animateTransform
                    attributeName="transform"
                    type="rotate"
                    from="0"
                    to="360"
                    dur="14s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
              <circle
                r={baseRadius}
                fill={fill}
                stroke={isCandidate ? "var(--color-series-3)" : "rgba(255,255,255,0.25)"}
                strokeWidth={isCandidate ? 2 : 1}
              />
              {lightInfo && (
                <circle
                  cx={baseRadius * 0.85}
                  cy={-baseRadius * 0.85}
                  r={4.5}
                  fill={lightInfo.color}
                  stroke="var(--color-bg)"
                  strokeWidth={1.5}
                />
              )}
              <text
                y={baseRadius + 16}
                textAnchor="middle"
                className="pointer-events-none select-none"
                fill={isSelected || isHovered ? "var(--color-ink)" : "var(--color-ink-3)"}
                fontSize="10.5"
                fontWeight={isSelected ? 600 : 500}
              >
                {item.id}
              </text>
              <title>
                {`${item.name}${queues ? ` · hàng đợi ${queue.toFixed(1)} xe` : ""}${lightInfo ? ` · đèn ${lightInfo.label}` : ""}`}
              </title>
            </g>
          );
        })}
      </svg>

      {/* zone chips as HTML overlay (crisp icons + labels) */}
      {zoneChips.map(({ zone, anchor }) => {
        const { icon: Icon, label } = zoneStyle(zone.type);
        return (
          <div
            key={zone.id}
            className="pointer-events-none absolute flex -translate-x-1/2 items-center gap-1 rounded-full border border-hairline bg-surface-2/90 px-2 py-0.5 text-[10px] font-medium text-ink-2 backdrop-blur"
            style={{
              left: `${(anchor.x / VIEW_W) * 100}%`,
              top: `calc(${(anchor.y / VIEW_H) * 100}% - 34px)`,
            }}
            title={`${zone.name} — ${zone.economic_role}`}
          >
            <Icon size={11} aria-hidden style={{ color: "var(--color-series-1)" }} />
            {label}
          </div>
        );
      })}
    </div>
  );
}
