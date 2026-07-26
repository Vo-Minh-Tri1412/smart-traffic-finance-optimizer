import { useQuery } from "@tanstack/react-query";
import { Boxes, BrainCircuit, Database, GitBranch, ServerCog } from "lucide-react";
import { useState } from "react";

import { Badge, ErrorState, LoadingState } from "../components/ui";
import { api } from "../lib/api";
import DataPanel from "./system/DataPanel";
import PipelinePanel from "./system/PipelinePanel";
import RLPanel from "./system/RLPanel";
import StatePanel from "./system/StatePanel";

type TabId = "pipeline" | "rl" | "data" | "state";

const TABS: { id: TabId; label: string; icon: typeof GitBranch }[] = [
  { id: "pipeline", label: "Pipeline", icon: GitBranch },
  { id: "rl", label: "RL & Reward", icon: BrainCircuit },
  { id: "data", label: "Dữ liệu & Map", icon: Database },
  { id: "state", label: "Trạng thái", icon: ServerCog },
];

export default function SystemView() {
  const [tab, setTab] = useState<TabId>("pipeline");

  const pipeline = useQuery({ queryKey: ["pipeline"], queryFn: api.pipeline });
  const rl = useQuery({ queryKey: ["rl"], queryFn: api.rl });
  const systemData = useQuery({ queryKey: ["system-data"], queryFn: api.systemData });
  const systemState = useQuery({ queryKey: ["system-state"], queryFn: api.systemState });
  const districts = useQuery({ queryKey: ["districts"], queryFn: api.districts });

  const activeDistrict = districts.data?.districts.find((entry) => entry.active);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-ink">
            <ServerCog size={20} aria-hidden />
            Hệ thống backend
          </h1>
          <p className="mt-1 text-xs text-ink-3">
            Quản lý pipeline, RL, dữ liệu và trạng thái các hệ thống con — phản ánh mức độ thật,
            không phải số liệu demo.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {activeDistrict && (
            <Badge color="var(--color-series-1)">
              <Boxes size={11} aria-hidden />
              {activeDistrict.name}
            </Badge>
          )}
          {districts.data && (
            <Badge color="var(--color-ink-3)">
              {districts.data.districts.filter((entry) => !entry.active).length} map dự kiến
            </Badge>
          )}
        </div>
      </header>

      <div className="flex flex-wrap gap-1.5 border-b border-hairline">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 rounded-t-lg border-b-2 px-4 py-2.5 text-xs font-medium transition ${
              tab === id
                ? "border-accent text-ink"
                : "border-transparent text-ink-3 hover:text-ink-2"
            }`}
          >
            <Icon size={15} aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {tab === "pipeline" &&
        (pipeline.isPending ? (
          <LoadingState />
        ) : pipeline.isError || !pipeline.data ? (
          <ErrorState
            title="Không tải được pipeline"
            detail="Khởi động backend: python -m ai_quantum_hvtc dashboard"
          />
        ) : (
          <PipelinePanel data={pipeline.data} />
        ))}

      {tab === "rl" &&
        (rl.isPending ? (
          <LoadingState />
        ) : rl.isError || !rl.data ? (
          <ErrorState title="Không tải được trạng thái RL" />
        ) : (
          <RLPanel data={rl.data} />
        ))}

      {tab === "data" &&
        (systemData.isPending ? (
          <LoadingState />
        ) : systemData.isError || !systemData.data ? (
          <ErrorState title="Không tải được dữ liệu & artifact" />
        ) : (
          <DataPanel data={systemData.data} districts={districts.data} />
        ))}

      {tab === "state" &&
        (systemState.isPending ? (
          <LoadingState />
        ) : systemState.isError || !systemState.data ? (
          <ErrorState title="Không tải được trạng thái hệ thống" />
        ) : (
          <StatePanel data={systemState.data} />
        ))}
    </div>
  );
}
