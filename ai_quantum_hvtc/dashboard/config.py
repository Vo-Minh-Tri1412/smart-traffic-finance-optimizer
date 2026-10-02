from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SPEC_PATH = REPO_ROOT / "tests" / "fixtures" / "specs" / "toy_public_district_v1.json"
DEFAULT_RUNS_DIR = REPO_ROOT / "artifacts" / "dashboard" / "runs"
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

DEFAULT_REWARD_PROFILE_PATH = (
    REPO_ROOT / "configs" / "training" / "rl_reward_profile_v0.example.toml"
)
DEFAULT_RL_TRAINING_CONFIG_PATH = REPO_ROOT / "configs" / "training" / "rl_sumo_v0.example.yaml"
DEFAULT_MODELS_DIR = REPO_ROOT / "models"
DEFAULT_CONFIGS_DIR = REPO_ROOT / "configs"

DEMO_SEED_SCENARIOS = (
    "normal_weekday",
    "morning_school_work",
    "hospital_emergency",
    "industrial_logistics_peak",
)
DEMO_SEED_CONTROLLERS = ("fixed_time", "rule_based")


@dataclass(frozen=True)
class DistrictRegistryEntry:
    """A district/map slot in the dashboard.

    Only ``active`` entries are backed by a loadable spec today. ``planned``
    entries reserve a place in the UI and API for future real maps (e.g. the
    District 7 SUMO net) without wiring them in yet.
    """

    district_id: str
    name: str
    status: str  # "active" | "planned"
    source_kind: str  # "district_spec" | "sumo_net" | "reserved"
    note: str = ""
    spec_path: Path | None = None


def default_district_registry(spec_path: Path) -> tuple[DistrictRegistryEntry, ...]:
    """Active toy district plus reserved slots for future real maps.

    The reserved slots are intentionally not loaded — they mark where a real
    SUMO/OSM district (and its scenarios) will plug in later.
    """

    return (
        DistrictRegistryEntry(
            district_id="toy_public_district_v1",
            name="Toy Public-Service District (fixture)",
            status="active",
            source_kind="district_spec",
            note="Fixture tổng hợp dùng cho CI/demo; không phải map thật cuối cùng.",
            spec_path=spec_path,
        ),
        DistrictRegistryEntry(
            district_id="district7_sumo_net",
            name="Quận 7 (OSM/SUMO net)",
            status="planned",
            source_kind="sumo_net",
            note="Chỗ dành sẵn cho map thật từ simulation_projects/map_intake; chưa nạp.",
            spec_path=None,
        ),
        DistrictRegistryEntry(
            district_id="reviewed_roi_100_signals",
            name="ROI ~100 nút đèn (đã review)",
            status="planned",
            source_kind="reserved",
            note="Mục tiêu chiến lược theo README; chờ demand/overlay được duyệt.",
            spec_path=None,
        ),
    )


@dataclass(frozen=True)
class DashboardConfig:
    """Runtime configuration for the dashboard backend service."""

    spec_path: Path = DEFAULT_SPEC_PATH
    runs_dir: Path = DEFAULT_RUNS_DIR
    frontend_dist: Path = DEFAULT_FRONTEND_DIST
    reward_profile_path: Path = DEFAULT_REWARD_PROFILE_PATH
    rl_training_config_path: Path = DEFAULT_RL_TRAINING_CONFIG_PATH
    models_dir: Path = DEFAULT_MODELS_DIR
    configs_dir: Path = DEFAULT_CONFIGS_DIR
    seed_demo_runs: bool = True
    demo_seed_scenarios: tuple[str, ...] = DEMO_SEED_SCENARIOS
    demo_seed_controllers: tuple[str, ...] = DEMO_SEED_CONTROLLERS
    districts: tuple[DistrictRegistryEntry, ...] = field(default_factory=tuple)
    experiments_dir: Path | None = None

    def resolved_districts(self) -> tuple[DistrictRegistryEntry, ...]:
        return self.districts or default_district_registry(self.spec_path)


def config_from_env() -> DashboardConfig:
    """Build config from environment overrides, falling back to repo defaults."""

    spec_path = Path(os.environ.get("AIQ_DASHBOARD_SPEC", str(DEFAULT_SPEC_PATH)))
    runs_dir = Path(os.environ.get("AIQ_DASHBOARD_RUNS_DIR", str(DEFAULT_RUNS_DIR)))
    frontend_dist = Path(os.environ.get("AIQ_DASHBOARD_FRONTEND_DIST", str(DEFAULT_FRONTEND_DIST)))
    reward_profile_path = Path(
        os.environ.get("AIQ_DASHBOARD_REWARD_PROFILE", str(DEFAULT_REWARD_PROFILE_PATH))
    )
    rl_training_config_path = Path(
        os.environ.get("AIQ_DASHBOARD_RL_CONFIG", str(DEFAULT_RL_TRAINING_CONFIG_PATH))
    )
    models_dir = Path(os.environ.get("AIQ_DASHBOARD_MODELS_DIR", str(DEFAULT_MODELS_DIR)))
    configs_dir = Path(os.environ.get("AIQ_DASHBOARD_CONFIGS_DIR", str(DEFAULT_CONFIGS_DIR)))
    experiments_value = os.environ.get("AIQ_DASHBOARD_EXPERIMENTS_DIR")
    experiments_dir = Path(experiments_value) if experiments_value else None
    seed_demo = os.environ.get("AIQ_DASHBOARD_SEED_DEMO", "1") not in {"0", "false", "no"}
    return DashboardConfig(
        spec_path=spec_path,
        runs_dir=runs_dir,
        frontend_dist=frontend_dist,
        reward_profile_path=reward_profile_path,
        rl_training_config_path=rl_training_config_path,
        models_dir=models_dir,
        configs_dir=configs_dir,
        experiments_dir=experiments_dir,
        seed_demo_runs=seed_demo,
    )
