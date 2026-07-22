import { useQuery } from "@tanstack/react-query";
import { CircleDollarSign, Info, MapPin, Route as RouteIcon } from "lucide-react";
import { useMemo, useState } from "react";

import DistrictMap from "../components/DistrictMap";
import { Badge, Card, ErrorState, LoadingState } from "../components/ui";
import { api } from "../lib/api";
import { scenarioLabel, zoneStyle } from "../lib/domain";
import { formatVnd } from "../lib/format";

export default function DistrictView() {
  const district = useQuery({ queryKey: ["district"], queryFn: api.district });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const data = district.data;

  const selected = useMemo(() => {
    if (!data || !selectedId) return null;
    const intersection = data.intersections.find((item) => item.id === selectedId);
    if (!intersection) return null;
    const zones = data.zones.filter((zone) => zone.intersection_ids.includes(selectedId));
    const roads = data.roads.filter(
      (road) => road.from === selectedId || road.to === selectedId,
    );
    const candidate = data.investment_candidates.find(
      (item) => item.intersection_id === selectedId,
    );
    return { intersection, zones, roads, candidate };
  }, [data, selectedId]);

  if (district.isPending) return <LoadingState label="Đang tải bản đồ quận…" />;
  if (district.isError || !data) {
    return (
      <ErrorState
        title="Không tải được dữ liệu quận"
        detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
      />
    );
  }

  const candidateIntersections = data.investment_candidates.map((item) => item.intersection_id);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Bản đồ quận</h1>
        <p className="mt-1 text-xs text-ink-3">
          {data.metadata.name} — bấm vào nút giao để xem phân khu, tuyến đường và phương án đầu tư.
          Viền vàng = ứng viên đầu tư đèn AI.
        </p>
      </header>

      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <Card className="min-w-0">
          <DistrictMap
            intersections={data.intersections}
            roads={data.roads}
            zones={data.zones}
            candidateIntersections={candidateIntersections}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </Card>

        <div className="space-y-5">
          <Card
            title={
              selected ? (
                <span className="flex items-center gap-2">
                  <MapPin size={14} aria-hidden />
                  {selected.intersection.name}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Info size={14} aria-hidden />
                  Chi tiết nút giao
                </span>
              )
            }
            subtitle={selected ? `Mã: ${selected.intersection.id}` : "Chưa chọn nút giao nào"}
          >
            {!selected ? (
              <p className="text-xs leading-relaxed text-ink-3">
                Chọn một nút giao trên bản đồ. Mỗi nút giao thuộc về một hoặc nhiều phân khu công
                cộng (bệnh viện, trường học, khu công nghiệp…) — đây là căn cứ để tính giá trị công
                khi tối ưu ngân sách.
              </p>
            ) : (
              <div className="space-y-4 text-xs">
                {selected.zones.length > 0 && (
                  <div>
                    <p className="mb-1.5 font-semibold text-ink-2">Phân khu</p>
                    <div className="space-y-2">
                      {selected.zones.map((zone) => {
                        const { icon: Icon, label } = zoneStyle(zone.type);
                        return (
                          <div key={zone.id} className="rounded-xl bg-surface-2 p-3">
                            <p className="flex items-center gap-2 font-medium text-ink">
                              <Icon
                                size={13}
                                aria-hidden
                                style={{ color: "var(--color-series-1)" }}
                              />
                              {zone.name} · {label}
                            </p>
                            <p className="mt-1 leading-relaxed text-ink-3">
                              {zone.economic_role}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div>
                  <p className="mb-1.5 flex items-center gap-1.5 font-semibold text-ink-2">
                    <RouteIcon size={13} aria-hidden />
                    Tuyến kết nối ({selected.roads.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.roads.map((road) => (
                      <Badge key={road.id} color="#414d6e">
                        {road.id} · {road.lanes} làn
                      </Badge>
                    ))}
                  </div>
                </div>

                {selected.candidate && (
                  <div
                    className="rounded-xl border p-3"
                    style={{
                      borderColor: "color-mix(in srgb, var(--color-series-3) 50%, transparent)",
                      background: "color-mix(in srgb, var(--color-series-3) 8%, transparent)",
                    }}
                  >
                    <p className="flex items-center gap-2 font-semibold text-ink">
                      <CircleDollarSign
                        size={14}
                        aria-hidden
                        style={{ color: "var(--color-series-3)" }}
                      />
                      Ứng viên đầu tư: {selected.candidate.id}
                    </p>
                    <dl className="mt-2 space-y-1 text-ink-2">
                      <div className="flex justify-between">
                        <dt className="text-ink-3">Loại nâng cấp</dt>
                        <dd>{selected.candidate.upgrade_type}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-ink-3">CAPEX</dt>
                        <dd className="tabular-nums">
                          {formatVnd(selected.candidate.capex_vnd)}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-ink-3">Bảo trì/năm</dt>
                        <dd className="tabular-nums">
                          {formatVnd(selected.candidate.annual_maintenance_vnd)}
                        </dd>
                      </div>
                    </dl>
                    <p className="mt-2 text-[10px] italic leading-relaxed text-ink-3">
                      {selected.candidate.caveat}
                    </p>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card title="Phân khu công cộng" subtitle={`${data.zones.length} khu chức năng`}>
            <ul className="space-y-1.5">
              {data.zones.map((zone) => {
                const { icon: Icon, label } = zoneStyle(zone.type);
                return (
                  <li key={zone.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(zone.intersection_ids[0] ?? null)}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-xs text-ink-2 transition hover:bg-surface-2"
                    >
                      <Icon size={14} aria-hidden style={{ color: "var(--color-series-1)" }} />
                      <span className="font-medium text-ink">{zone.name}</span>
                      <span className="ml-auto text-[10px] text-ink-3">{label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      </div>

      <Card
        title="Kịch bản mô phỏng"
        subtitle="Mỗi kịch bản thay đổi lưu lượng và năng lực tuyến đường để kiểm tra controller trong điều kiện khác nhau"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {data.scenarios.map((scenario) => (
            <div key={scenario.id} className="rounded-xl bg-surface-2 p-3.5">
              <p className="text-xs font-semibold text-ink">{scenarioLabel(scenario.id)}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-3">
                {scenario.description}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.keys(scenario.flow_multipliers).length > 0 && (
                  <Badge color="var(--color-series-2)">
                    {Object.keys(scenario.flow_multipliers).length} luồng thay đổi
                  </Badge>
                )}
                {scenario.closed_roads.length > 0 && (
                  <Badge color="var(--color-status-critical)">
                    Đóng {scenario.closed_roads.join(", ")}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
