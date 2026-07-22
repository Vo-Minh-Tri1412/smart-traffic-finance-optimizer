import { ArrowRight } from "lucide-react";
import { useMemo } from "react";

import { StageStatusBadge } from "../../components/StatusBadge";
import { Card } from "../../components/ui";
import { LAYER_ORDER, stageStatusStyle } from "../../lib/domain";
import type { PipelineResponse, PipelineStage } from "../../lib/types";

function StageCard({ stage }: { stage: PipelineStage }) {
  const { color } = stageStatusStyle(stage.status);
  return (
    <div
      className="rounded-xl border border-hairline bg-surface-2 p-3.5"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-ink">{stage.name}</p>
        <StageStatusBadge status={stage.status} />
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">{stage.summary}</p>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[10px] text-ink-3">
        <span className="rounded bg-surface-3 px-1.5 py-0.5">{stage.inputs.join(", ")}</span>
        <ArrowRight size={11} aria-hidden />
        <span
          className="rounded px-1.5 py-0.5 font-medium"
          style={{ background: "color-mix(in srgb, var(--color-series-2) 14%, transparent)" }}
        >
          {stage.outputs.join(", ")}
        </span>
      </div>
      {stage.modules.length > 0 && (
        <p className="mt-2 font-mono text-[10px] text-ink-3">{stage.modules.join(" · ")}</p>
      )}
    </div>
  );
}

export default function PipelinePanel({ data }: { data: PipelineResponse }) {
  const stagesByLayer = useMemo(() => {
    const map = new Map<string, PipelineStage[]>();
    for (const stage of data.stages) {
      const list = map.get(stage.layer) ?? [];
      list.push(stage);
      map.set(stage.layer, list);
    }
    const orderedLayers = [
      ...LAYER_ORDER.filter((layer) => map.has(layer)),
      ...data.layers.filter((layer) => !LAYER_ORDER.includes(layer)),
    ];
    return orderedLayers.map((layer) => ({ layer, stages: map.get(layer) ?? [] }));
  }, [data]);

  return (
    <div className="space-y-5">
      <Card
        title="Luồng pipeline hệ thống"
        subtitle="Từ nguồn map tới quyết định đầu tư, kèm nhánh cảm biến và render — nhãn trạng thái phản ánh mức độ thật của từng lớp"
      >
        <div className="flex flex-wrap gap-3">
          {Object.entries(data.status_legend).map(([status, description]) => (
            <div key={status} className="flex items-center gap-2 text-[11px] text-ink-3">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: stageStatusStyle(status).color }}
                aria-hidden
              />
              <span className="font-medium text-ink-2">{stageStatusStyle(status).label}</span>
              <span className="hidden md:inline">— {description}</span>
            </div>
          ))}
        </div>
      </Card>

      <div className="space-y-4">
        {stagesByLayer.map(({ layer, stages }) => (
          <div key={layer}>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-3">
                {layer}
              </span>
              <span className="h-px flex-1 bg-hairline" />
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {stages.map((stage) => (
                <StageCard key={stage.id} stage={stage} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
