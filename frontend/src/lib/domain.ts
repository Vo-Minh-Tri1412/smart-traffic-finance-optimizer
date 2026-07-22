import {
  Ambulance,
  Building2,
  Bus,
  DoorOpen,
  Factory,
  GraduationCap,
  Home,
  Hospital,
  Landmark,
  MoonStar,
  PartyPopper,
  ShoppingBasket,
  Truck,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

/**
 * Color follows the entity: each controller keeps its slot everywhere
 * (charts, map, legends), regardless of which controllers are visible.
 */
export const CONTROLLER_COLORS: Record<string, string> = {
  fixed_time: "var(--color-series-1)",
  rule_based: "var(--color-series-2)",
  rl_policy: "var(--color-series-3)",
};

export const CONTROLLER_FALLBACK_COLOR = "var(--color-series-4)";

export function controllerColor(controllerId: string): string {
  return CONTROLLER_COLORS[controllerId] ?? CONTROLLER_FALLBACK_COLOR;
}

export const CONTROLLER_LABELS: Record<string, string> = {
  fixed_time: "Đèn chu kỳ cố định",
  rule_based: "Luật thích ứng",
  rl_policy: "RL policy",
};

export function controllerLabel(controllerId: string): string {
  return CONTROLLER_LABELS[controllerId] ?? controllerId;
}

export const SCENARIO_LABELS: Record<string, string> = {
  normal_weekday: "Ngày thường",
  morning_school_work: "Cao điểm sáng (trường + công sở)",
  industrial_shift_in: "Vào ca khu công nghiệp",
  industrial_logistics_peak: "Cao điểm logistics",
  hospital_emergency: "Cấp cứu giờ ùn tắc",
  nightlife_spike: "Cao điểm giải trí tối",
  incident_bottleneck: "Sự cố chặn nút cổ chai",
  limited_budget_rollout: "Triển khai ngân sách hạn chế",
};

export function scenarioLabel(scenarioId: string): string {
  return SCENARIO_LABELS[scenarioId] ?? scenarioId;
}

export const ENGINE_LABELS: Record<string, string> = {
  reference: "Engine tham chiếu",
  sumo: "SUMO",
};

export function engineLabel(engineId: string): string {
  return ENGINE_LABELS[engineId] ?? engineId;
}

interface ZoneStyle {
  icon: LucideIcon;
  label: string;
}

export const ZONE_STYLES: Record<string, ZoneStyle> = {
  HOSPITAL: { icon: Hospital, label: "Bệnh viện" },
  SCHOOL: { icon: GraduationCap, label: "Trường học" },
  BUS_TERMINAL: { icon: Bus, label: "Bến xe buýt" },
  RESIDENTIAL_HIGH_DENSITY: { icon: Home, label: "Khu dân cư" },
  PUBLIC_ADMIN: { icon: Landmark, label: "Hành chính công" },
  EVENT_VENUE: { icon: PartyPopper, label: "Nhà sự kiện" },
  MARKET: { icon: ShoppingBasket, label: "Chợ" },
  CITY_GATE: { icon: DoorOpen, label: "Cửa ngõ" },
  LOGISTICS_DEPOT: { icon: Warehouse, label: "Kho vận" },
  ENTERTAINMENT_NIGHTLIFE: { icon: MoonStar, label: "Giải trí đêm" },
  INDUSTRIAL_ZONE: { icon: Factory, label: "Khu công nghiệp" },
};

export const ZONE_FALLBACK_STYLE: ZoneStyle = { icon: Building2, label: "Khu vực" };

export function zoneStyle(zoneType: string): ZoneStyle {
  return ZONE_STYLES[zoneType] ?? ZONE_FALLBACK_STYLE;
}

export const VEHICLE_LABELS: Record<string, string> = {
  MOTORBIKE: "Xe máy",
  PRIVATE_CAR: "Ô tô cá nhân",
  TAXI_RIDE_HAILING: "Taxi / xe công nghệ",
  DELIVERY_BIKE: "Xe giao hàng",
  BUS: "Xe buýt",
  SCHOOL_BUS: "Xe đưa đón học sinh",
  WORKER_SHUTTLE: "Xe đưa đón công nhân",
  AMBULANCE: "Xe cấp cứu",
  LIGHT_TRUCK: "Xe tải nhẹ",
  HEAVY_TRUCK: "Xe tải nặng",
};

export const EMERGENCY_ICON = Ambulance;
export const TRUCK_ICON = Truck;

/** Traffic-light trace states → status color + Vietnamese label. */
export function trafficLightStatus(state: string): { color: string; label: string } {
  if (state.startsWith("GREEN")) {
    return { color: "var(--color-status-good)", label: "Xanh" };
  }
  if (state.startsWith("YELLOW")) {
    return { color: "var(--color-status-warning)", label: "Vàng" };
  }
  if (state.startsWith("RED")) {
    return { color: "var(--color-status-critical)", label: "Đỏ" };
  }
  return { color: "var(--color-ink-3)", label: state };
}

/**
 * Sequential blue ramp (ordinal, dark-mode-legal steps) for queue magnitude.
 * Light step = near zero queue, dark step = heavy queue.
 */
const QUEUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"];

export function queueRampColor(value: number, max: number): string {
  if (max <= 0) return QUEUE_RAMP[0];
  const t = Math.min(1, Math.max(0, value / max));
  const index = Math.min(QUEUE_RAMP.length - 1, Math.floor(t * QUEUE_RAMP.length));
  return QUEUE_RAMP[index];
}

interface StatusStyle {
  label: string;
  color: string;
}

/** Stage/stream status → status color + Vietnamese label (never color alone). */
export const STAGE_STATUS_STYLES: Record<string, StatusStyle> = {
  implemented: { label: "Đã hoạt động", color: "var(--color-status-good)" },
  partial: { label: "Một phần", color: "var(--color-status-warning)" },
  scaffold: { label: "Khung", color: "var(--color-series-4)" },
  planned: { label: "Dự kiến", color: "var(--color-ink-3)" },
};

export function stageStatusStyle(status: string): StatusStyle {
  return STAGE_STATUS_STYLES[status] ?? { label: status, color: "var(--color-ink-3)" };
}

export const CHECK_STATUS_STYLES: Record<string, StatusStyle> = {
  ok: { label: "Đạt", color: "var(--color-status-good)" },
  warn: { label: "Cảnh báo", color: "var(--color-status-warning)" },
  fail: { label: "Lỗi", color: "var(--color-status-critical)" },
};

export function checkStatusStyle(status: string): StatusStyle {
  return CHECK_STATUS_STYLES[status] ?? { label: status, color: "var(--color-ink-3)" };
}

/** RL layer label for a subsystem/stage layer name (already Vietnamese from API). */
export const LAYER_ORDER = [
  "Nguồn dữ liệu",
  "Điều khiển giao thông",
  "Đo lường",
  "Tài chính công",
  "Cảm biến",
  "Render",
  "Dữ liệu",
];

export const METRIC_LABELS: Record<string, string> = {
  average_waiting_time_seconds: "Chờ trung bình",
  total_waiting_time_seconds: "Tổng thời gian chờ",
  throughput: "Lưu lượng hoàn thành",
  max_queue_vehicles: "Hàng đợi tối đa",
  emergency_delay_seconds: "Trễ xe cấp cứu",
  bus_passenger_delay_seconds: "Trễ khách xe buýt",
  truck_delay_seconds: "Trễ xe tải",
  stopped_vehicles: "Xe phải dừng",
};
