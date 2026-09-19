"""Backend introspection: pipeline, RL, data, readiness, and district registry.

Everything surfaced here reflects the *real* repository state (reward-profile
TOML, training gate, module availability, run store) rather than demo numbers.
When a subsystem is a scaffold, it is labelled as such instead of being faked.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai_quantum_hvtc.rl import (
    RewardProfile,
    RewardProfileError,
    load_reward_profile,
    training_blockers,
)
from ai_quantum_hvtc.rl.contracts import ACTION_SPACE_V1, OBSERVATION_SPACE_V1
from ai_quantum_hvtc.simulation.domain import DistrictSpec

from .config import DashboardConfig
from .store import RunStore

StageStatus = Literal["implemented", "partial", "scaffold", "planned"]
CheckStatus = Literal["ok", "warn", "fail"]


# --------------------------------------------------------------------------- #
# Response models
# --------------------------------------------------------------------------- #
class PipelineStage(BaseModel):
    id: str
    name: str
    layer: str
    status: StageStatus
    summary: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)


class PipelineResponse(BaseModel):
    layers: list[str]
    stages: list[PipelineStage]
    status_legend: dict[str, str]


class RewardWeightRow(BaseModel):
    key: str
    weight: float


class HardConstraintModel(BaseModel):
    id: str
    type: str
    enforcement: str
    status: str
    vehicle_types: list[str]
    notes: str = ""


class RewardProfileModel(BaseModel):
    profile_id: str
    status: str
    owner: str
    description: str
    source_path: str
    loaded: bool
    base_weights: list[RewardWeightRow]
    vehicle_type_weights: list[RewardWeightRow]
    trip_purpose_weights: list[RewardWeightRow]
    scenario_weights: list[RewardWeightRow]
    route_priority_weights: list[dict[str, Any]]
    time_window_weights: list[dict[str, Any]]
    hard_constraints: list[HardConstraintModel]


class RLResponse(BaseModel):
    policy_trained: bool
    policy_note: str
    training_ready: bool
    blockers: list[str]
    reward_profile: RewardProfileModel | None
    reward_profile_error: str | None
    observation_space: dict[str, Any]
    action_space: dict[str, Any]
    training_config: dict[str, Any]


class DataStream(BaseModel):
    id: str
    name: str
    status: StageStatus
    summary: str
    location: str


class ConfigFile(BaseModel):
    name: str
    path: str
    present: bool


class DataResponse(BaseModel):
    run_store: dict[str, Any]
    streams: list[DataStream]
    dvc: dict[str, Any]
    configs: list[ConfigFile]


class ReadinessCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class SystemStateResponse(BaseModel):
    summary: str
    ok_count: int
    warn_count: int
    fail_count: int
    checks: list[ReadinessCheck]


class DistrictRegistryModel(BaseModel):
    district_id: str
    name: str
    status: str
    source_kind: str
    note: str
    active: bool


class DistrictsResponse(BaseModel):
    active_district_id: str
    districts: list[DistrictRegistryModel]


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
_STATUS_LEGEND: dict[str, str] = {
    "implemented": "Đã hoạt động và có test/kiểm chứng.",
    "partial": "Có nền tảng nhưng chưa đầy đủ cho bản cuối.",
    "scaffold": "Mới là khung; chưa có kết quả thật (vd chưa train).",
    "planned": "Chưa bắt đầu; chừa chỗ cho bước sau.",
}

_PIPELINE_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage(
        id="map_source",
        name="Nguồn map & spec",
        layer="Nguồn dữ liệu",
        status="implemented",
        summary=(
            "District spec JSON (hoặc SUMO .net.xml + semantic overlay) là đầu vào chuẩn. "
            "Hiện chạy trên fixture toy; map thật để chừa chỗ trong registry."
        ),
        inputs=["district_spec.json", "sumo .net.xml", "semantic_overlay.json"],
        outputs=["DistrictSpec"],
        modules=["ai_quantum_hvtc.simulation.specs", "ai_quantum_hvtc.simulation.maps"],
    ),
    PipelineStage(
        id="engine",
        name="Engine mô phỏng",
        layer="Điều khiển giao thông",
        status="implemented",
        summary=(
            "SUMO là engine chính (đã verify cục bộ); engine tham chiếu chỉ dùng để kiểm "
            "tra nhanh schema/tài chính."
        ),
        inputs=["DistrictSpec", "scenario_id", "controller_id"],
        outputs=["SimulationResult", "trace.jsonl"],
        modules=["ai_quantum_hvtc.simulation.engines.sumo", "…engines.reference"],
    ),
    PipelineStage(
        id="controllers",
        name="Controller đèn",
        layer="Điều khiển giao thông",
        status="partial",
        summary=(
            "fixed_time và rule_based đã chạy làm baseline. rl_policy mới là khung, "
            "chưa có policy đã train."
        ),
        inputs=["SimulationResult"],
        outputs=["controller metrics"],
        modules=["ai_quantum_hvtc.simulation.controllers"],
    ),
    PipelineStage(
        id="metrics_trace",
        name="Metrics & trace",
        layer="Đo lường",
        status="implemented",
        summary="Xuất metric tổng hợp + trace từng bước để chấm điểm và replay.",
        inputs=["SimulationResult"],
        outputs=["metrics_summary", "simulation_trace_frame.v1"],
        modules=["ai_quantum_hvtc.simulation.metrics", "…reports.export"],
    ),
    PipelineStage(
        id="scoring",
        name="Chấm điểm giá trị công",
        layer="Tài chính công",
        status="implemented",
        summary=(
            "So run controller với baseline để quy đổi thời gian tiết kiệm thành giá trị công. "
            "Giả định tài chính vẫn là placeholder chờ nhóm Kinh tế duyệt."
        ),
        inputs=["baseline metrics", "alternative metrics", "finance_assumptions"],
        outputs=["CandidateScore[]"],
        modules=["ai_quantum_hvtc.public_finance.scoring"],
    ),
    PipelineStage(
        id="optimizer",
        name="Tối ưu đầu tư",
        layer="Tài chính công",
        status="implemented",
        summary="Chọn tập nút giao dưới ngân sách bằng exact/greedy; xuất QUBO cho lượng tử.",
        inputs=["CandidateScore[]", "budget_vnd"],
        outputs=["selected candidates", "QUBO matrix"],
        modules=["ai_quantum_hvtc.policy.algorithms.investment"],
    ),
    PipelineStage(
        id="rl",
        name="RL đa tác tử",
        layer="Điều khiển giao thông",
        status="scaffold",
        summary=(
            "Khung reward/observation/action đã có; reward profile đang draft và bị chốt "
            "chặn training. Chưa có policy."
        ),
        inputs=["observation_space.v1", "reward_profile"],
        outputs=["(chưa có policy)"],
        modules=["ai_quantum_hvtc.rl"],
    ),
    PipelineStage(
        id="sensor",
        name="Cảm biến hình học / CV",
        layer="Cảm biến",
        status="partial",
        summary=(
            "Có geometry camera suy ra tầm nhìn từ pose+kích thước xe. YOLO/CV mới là "
            "khung, chưa có dataset/model."
        ),
        inputs=["vehicle_trace.v2", "camera_calibration.v1"],
        outputs=["visibility_trace", "(YOLO labels — kế hoạch)"],
        modules=["ai_quantum_hvtc.sensors.geometry_camera", "…sensors.synthetic_cv"],
    ),
    PipelineStage(
        id="render",
        name="Render Unreal Engine",
        layer="Render",
        status="partial",
        summary=(
            "UE replay trace SUMO; pipeline xuất frame/video còn cần triển khai ở "
            "nhánh render/sensor, không phải simulator."
        ),
        inputs=["vehicle trace", "SUMO net", "semantic overlay"],
        outputs=["frames/video", "(synthetic CV dataset — kế hoạch)"],
        modules=["render_unreal/ (Unreal project)"],
    ),
    PipelineStage(
        id="data_workflow",
        name="Data & artifact workflow",
        layer="Dữ liệu",
        status="implemented",
        summary="Tách code (Git) khỏi dữ liệu lớn (DVC + Google Drive Data Hub) theo stream.",
        inputs=["runs", "datasets", "checkpoints"],
        outputs=["DVC pointers", "Drive artifacts", "registry"],
        modules=["scripts/cloud", "scripts/artifacts", "dvc"],
    ),
)


def build_pipeline() -> PipelineResponse:
    layers: list[str] = []
    for stage in _PIPELINE_STAGES:
        if stage.layer not in layers:
            layers.append(stage.layer)
    return PipelineResponse(
        layers=layers,
        stages=list(_PIPELINE_STAGES),
        status_legend=_STATUS_LEGEND,
    )


# --------------------------------------------------------------------------- #
# RL
# --------------------------------------------------------------------------- #
def _weight_rows(weights: Any) -> list[RewardWeightRow]:
    return [RewardWeightRow(key=str(key), weight=float(value)) for key, value in weights.items()]


def _reward_profile_model(profile: RewardProfile, source_path: Path) -> RewardProfileModel:
    return RewardProfileModel(
        profile_id=profile.profile_id,
        status=profile.status,
        owner=profile.owner,
        description=profile.description,
        source_path=str(source_path),
        loaded=True,
        base_weights=_weight_rows(profile.base_weights),
        vehicle_type_weights=_weight_rows(profile.vehicle_type_weights),
        trip_purpose_weights=_weight_rows(profile.trip_purpose_weights),
        scenario_weights=_weight_rows(profile.scenario_weights),
        route_priority_weights=[
            {"flow_id": row.flow_id, "weight": row.weight, "description": row.description}
            for row in profile.route_priority_weights
        ],
        time_window_weights=[
            {
                "label": row.label,
                "start": row.start,
                "end": row.end,
                "weight": row.weight,
                "flow_ids": list(row.flow_ids),
                "trip_purposes": list(row.trip_purposes),
            }
            for row in profile.time_window_weights
        ],
        hard_constraints=[
            HardConstraintModel(
                id=row.constraint_id,
                type=row.constraint_type,
                enforcement=row.enforcement,
                status=row.status,
                vehicle_types=list(row.vehicle_types),
                notes=row.notes,
            )
            for row in profile.hard_constraints
        ],
    )


def build_rl(*, config: DashboardConfig, spec: DistrictSpec, models_dir: Path) -> RLResponse:
    reward_model: RewardProfileModel | None = None
    reward_error: str | None = None
    blockers: list[str] = []

    reward_path = config.reward_profile_path
    if reward_path.is_file():
        try:
            profile = load_reward_profile(reward_path)
            reward_model = _reward_profile_model(profile, reward_path)
            blockers = training_blockers(profile, spec)
        except (RewardProfileError, OSError, ValueError) as exc:
            reward_error = f"Không đọc được reward profile: {exc}"
    else:
        reward_error = f"Chưa có reward profile tại {reward_path}"
        blockers = ["reward profile chưa tồn tại"]

    policy_files = _policy_artifacts(models_dir)
    policy_trained = len(policy_files) > 0

    return RLResponse(
        policy_trained=policy_trained,
        policy_note=(
            f"Tìm thấy {len(policy_files)} checkpoint trong {models_dir}"
            if policy_trained
            else f"Chưa có policy đã train (thư mục {models_dir} trống)."
        ),
        training_ready=not blockers and reward_error is None,
        blockers=blockers,
        reward_profile=reward_model,
        reward_profile_error=reward_error,
        observation_space={
            "version": OBSERVATION_SPACE_V1.version,
            "feature_groups": list(OBSERVATION_SPACE_V1.feature_groups),
            "source_document": OBSERVATION_SPACE_V1.source_document,
        },
        action_space={
            "version": ACTION_SPACE_V1.version,
            "action_type": ACTION_SPACE_V1.action_type,
            "caveat": ACTION_SPACE_V1.caveat,
        },
        training_config=_training_config(config.rl_training_config_path),
    )


def _policy_artifacts(models_dir: Path) -> list[str]:
    if not models_dir.is_dir():
        return []
    return sorted(
        path.name
        for path in models_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".zip", ".pt", ".pth", ".onnx"}
    )


def _training_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "path": str(path)}
    config: dict[str, Any] = {"present": True, "path": str(path)}
    # Lightweight, dependency-free parse of the flat example YAML.
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        if ":" in stripped and not line.startswith(" "):
            key, _, value = stripped.partition(":")
            value = value.strip().strip('"')
            if value:
                config[key.strip()] = value
    return config


# --------------------------------------------------------------------------- #
# Data & artifacts
# --------------------------------------------------------------------------- #
_DATA_STREAMS: tuple[DataStream, ...] = (
    DataStream(
        id="sumo",
        name="SUMO mạng/route/trace",
        status="implemented",
        summary="Net, route, tripinfo, edge/lane, FCD trace — nguồn ground truth mô phỏng.",
        location="DVC + Drive: 03_Training_Runs / artifacts",
    ),
    DataStream(
        id="rl_sumo",
        name="RL training runs",
        status="scaffold",
        summary="Checkpoint PPO/sb3 sẽ nằm ở đây sau khi reward được duyệt và train.",
        location="Drive: 03_Training_Runs/rl",
    ),
    DataStream(
        id="yolo",
        name="Synthetic CV / YOLO",
        status="planned",
        summary="Frame/nhãn render từ Unreal Engine + model YOLO — chưa sinh dataset thật.",
        location="Drive: 03_Training_Runs/yolo",
    ),
    DataStream(
        id="finance",
        name="Public-finance outputs",
        status="implemented",
        summary="Bảng điểm ứng viên, danh mục chọn, ma trận QUBO xuất từ optimizer.",
        location="artifacts/ + reports",
    ),
)

_DVC_INFO: dict[str, Any] = {
    "remote": "drive_desktop -> D:\\AIQ_HVTC_DVC_STORE",
    "data_hub": "02_CS_Workspace/00_Data_Management",
    "registry_sheet": "00_Data_Model_Run_Registry",
    "principle": "Git giữ code + pointer; DVC/Drive giữ file lớn (net, trace, dataset, checkpoint).",  # noqa: E501
}


def build_data(*, config: DashboardConfig, store: RunStore) -> DataResponse:
    metas = store.list_runs()
    scenarios = sorted({meta.scenario_id for meta in metas})
    controllers = sorted({meta.controller_id for meta in metas})
    engines = sorted({meta.engine_id for meta in metas})
    run_store = {
        "run_count": len(metas),
        "scenarios": scenarios,
        "controllers": controllers,
        "engines": engines,
        "directory": str(store.runs_dir),
    }
    config_names = [
        "drive_paths.example.json",
        "training/rl_reward_profile_v0.example.toml",
        "training/rl_sumo_v0.example.yaml",
        "training/yolo_v0.example.yaml",
        "training/finance_optimizer_v0.example.yaml",
    ]
    configs = [
        ConfigFile(
            name=name,
            path=str(config.configs_dir / name),
            present=(config.configs_dir / name).is_file(),
        )
        for name in config_names
    ]
    return DataResponse(
        run_store=run_store,
        streams=list(_DATA_STREAMS),
        dvc=_DVC_INFO,
        configs=configs,
    )


# --------------------------------------------------------------------------- #
# Readiness state
# --------------------------------------------------------------------------- #
def build_state(
    *, config: DashboardConfig, spec: DistrictSpec, store: RunStore
) -> SystemStateResponse:
    checks: list[ReadinessCheck] = []

    py_ok = sys.version_info[:2] == (3, 12)
    checks.append(
        ReadinessCheck(
            name="Python 3.12",
            status="ok" if py_ok else "warn",
            detail=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )

    sumo_bin = shutil.which("sumo")
    checks.append(
        ReadinessCheck(
            name="SUMO runtime",
            status="ok" if sumo_bin else "warn",
            detail=sumo_bin or "chưa có sumo trên PATH; engine tham chiếu vẫn chạy",
        )
    )

    for package in ("sumo_rl", "stable_baselines3", "gymnasium"):
        available = importlib.util.find_spec(package) is not None
        checks.append(
            ReadinessCheck(
                name=f"gói {package}",
                status="ok" if available else "warn",
                detail="đã cài" if available else "chưa cài (chỉ cần khi train RL)",
            )
        )

    reward_ok = config.reward_profile_path.is_file()
    checks.append(
        ReadinessCheck(
            name="Reward profile",
            status="ok" if reward_ok else "warn",
            detail=str(config.reward_profile_path) if reward_ok else "chưa có file reward profile",
        )
    )

    spec_ok = config.spec_path.is_file()
    checks.append(
        ReadinessCheck(
            name="District spec",
            status="ok" if spec_ok else "fail",
            detail=f"{spec.metadata.district_id} ({config.spec_path})",
        )
    )

    run_count = len(store.list_runs())
    checks.append(
        ReadinessCheck(
            name="Kho run dashboard",
            status="ok" if run_count > 0 else "warn",
            detail=f"{run_count} run đã lưu",
        )
    )

    ok_count = sum(1 for check in checks if check.status == "ok")
    warn_count = sum(1 for check in checks if check.status == "warn")
    fail_count = sum(1 for check in checks if check.status == "fail")
    if fail_count:
        summary = "Có mục lỗi cần xử lý trước khi chạy."
    elif warn_count:
        summary = "Chạy được; một số mục tuỳ chọn chưa sẵn sàng."
    else:
        summary = "Tất cả kiểm tra đều đạt."
    return SystemStateResponse(
        summary=summary,
        ok_count=ok_count,
        warn_count=warn_count,
        fail_count=fail_count,
        checks=checks,
    )


# --------------------------------------------------------------------------- #
# District registry
# --------------------------------------------------------------------------- #
def build_districts(config: DashboardConfig) -> DistrictsResponse:
    entries = config.resolved_districts()
    active_id = next(
        (entry.district_id for entry in entries if entry.status == "active"),
        entries[0].district_id if entries else "",
    )
    return DistrictsResponse(
        active_district_id=active_id,
        districts=[
            DistrictRegistryModel(
                district_id=entry.district_id,
                name=entry.name,
                status=entry.status,
                source_kind=entry.source_kind,
                note=entry.note,
                active=entry.status == "active",
            )
            for entry in entries
        ],
    )
