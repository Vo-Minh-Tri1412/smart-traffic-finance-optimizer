from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EXPECTED_AGENTS = {
    "evidence-researcher": "read-only",
    "system-architect": "read-only",
    "implementation-worker": "workspace-write",
    "verification-auditor": "read-only",
}

EXPECTED_SKILLS = {
    "coordinate-agent-task",
    "research-source-evidence",
    "handoff-agent-work",
    "audit-reproducibility",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Literal["ok", "warn", "fail"]
    detail: str

    @property
    def ok(self) -> bool:
        return self.status != "fail"


def ok(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "ok", detail)


def warn(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "warn", detail)


def fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "fail", detail)


def _run_git_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def check_python() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    is_expected = sys.version_info[:2] == (3, 12)
    detail = f"Python {version}"
    if not is_expected:
        detail += " (expected Python 3.12)"
        return fail("python", detail)
    return ok("python", detail)


def check_git_root(root: Path) -> CheckResult:
    detected = _run_git_root(root)
    if detected is None:
        return fail("git-root", "not inside a Git repository")
    is_expected = detected == root.resolve()
    detail = str(detected)
    if not is_expected:
        detail += f" (expected {root.resolve()})"
        return fail("git-root", detail)
    return ok("git-root", detail)


def check_codex_config(root: Path) -> CheckResult:
    path = root / ".codex" / "config.toml"
    if not path.exists():
        return warn(
            "codex-config",
            ".codex/config.toml not present; legacy Codex governance disabled",
        )

    try:
        config = _read_toml(path)
    except tomllib.TOMLDecodeError as exc:
        return fail("codex-config", f"TOML error: {exc}")

    agents = config.get("agents")
    if not isinstance(agents, dict):
        return fail("codex-config", "missing [agents] table")

    if agents.get("max_threads") != 6:
        return fail("codex-config", "agents.max_threads must be 6")
    if agents.get("max_depth") != 1:
        return fail("codex-config", "agents.max_depth must be 1")

    return ok("codex-config", ".codex/config.toml")


def check_agent_files(root: Path) -> CheckResult:
    agents_dir = root / ".codex" / "agents"
    if not agents_dir.exists():
        return warn("agent-files", ".codex/agents not present; legacy custom agents disabled")

    failures: list[str] = []
    for name, expected_sandbox in EXPECTED_AGENTS.items():
        path = root / ".codex" / "agents" / f"{name}.toml"
        if not path.exists():
            failures.append(f"missing {path.relative_to(root)}")
            continue
        try:
            data = _read_toml(path)
        except tomllib.TOMLDecodeError as exc:
            failures.append(f"{path.relative_to(root)} TOML error: {exc}")
            continue
        if data.get("name") != name:
            failures.append(f"{path.relative_to(root)} has wrong name")
        if data.get("sandbox_mode") != expected_sandbox:
            failures.append(f"{path.relative_to(root)} sandbox_mode must be {expected_sandbox}")

    if failures:
        return fail("agent-files", "; ".join(failures))
    return ok("agent-files", f"{len(EXPECTED_AGENTS)} custom agents")


def check_skill_files(root: Path) -> CheckResult:
    skills_dir = root / ".codex" / "skills"
    if not skills_dir.exists():
        return warn("skill-files", ".codex/skills not present; legacy repo skills disabled")

    failures: list[str] = []
    for name in sorted(EXPECTED_SKILLS):
        path = root / ".codex" / "skills" / name / "SKILL.md"
        if not path.exists():
            failures.append(f"missing {path.relative_to(root)}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            failures.append(f"{path.relative_to(root)} missing YAML frontmatter")
        if f"name: {name}" not in text and f'name: "{name}"' not in text:
            failures.append(f"{path.relative_to(root)} missing matching name")
        if "description:" not in text:
            failures.append(f"{path.relative_to(root)} missing description")

    if failures:
        return fail("skill-files", "; ".join(failures))
    return ok("skill-files", f"{len(EXPECTED_SKILLS)} repo skills")


def check_project_direction(root: Path) -> CheckResult:
    required_docs = [
        root / "docs" / "README.md",
        root / "docs" / "01_PROJECT_BRIEF" / "SMART_TRAFFIC_PUBLIC_FINANCE.md",
        root / "docs" / "02_ARCHITECTURE" / "SIMULATION_BACKEND_ARCHITECTURE.md",
        root / "docs" / "02_ARCHITECTURE" / "GODOT_RENDER_ARCHITECTURE.md",
        root / "docs" / "02_ARCHITECTURE" / "SUMO_RL_SYSTEM_DESIGN.md",
        root / "docs" / "03_COMPETITION" / "AI_QUANTUM_HVTC_FACTS.md",
    ]
    missing = [path.relative_to(root).as_posix() for path in required_docs if not path.exists()]
    if missing:
        return fail("project-direction", f"missing docs: {', '.join(missing)}")
    return ok("project-direction", "SUMO-RL traffic public finance docs")


def check_python_packages() -> CheckResult:
    missing: list[str] = []
    for package_name in ("sumo_rl", "gymnasium", "stable_baselines3", "streamlit"):
        if importlib.util.find_spec(package_name) is None:
            missing.append(package_name)
    if missing:
        return fail("python-packages", f"missing packages: {', '.join(missing)}")
    return ok("python-packages", "sumo_rl, gymnasium, stable_baselines3, streamlit")


def check_sumo_binary() -> CheckResult:
    sumo = shutil.which("sumo")
    sumo_gui = shutil.which("sumo-gui")
    sumo_home = os.environ.get("SUMO_HOME")
    missing: list[str] = []
    if sumo is None:
        missing.append("sumo")
    if sumo_gui is None:
        missing.append("sumo-gui")
    if not sumo_home:
        missing.append("SUMO_HOME")

    if missing:
        return warn(
            "sumo-binary",
            "missing external SUMO runtime: "
            + ", ".join(missing)
            + "; install SUMO before running simulations",
        )
    return ok("sumo-binary", f"sumo={sumo}; sumo-gui={sumo_gui}; SUMO_HOME={sumo_home}")


def check_task_manifests(root: Path) -> CheckResult:
    script = root / "scripts" / "admin" / "validate_agent_tasks.py"
    tasks_dir = root / "coordination" / "tasks"
    if not script.exists():
        return fail("task-manifests", "missing task validator")
    if not tasks_dir.exists():
        return fail("task-manifests", "missing coordination/tasks")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--tasks-dir",
            str(tasks_dir),
            "--skip-diff",
        ],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return fail("task-manifests", detail)
    return ok("task-manifests", result.stdout.strip())


def run_checks(root: Path | None = None) -> list[CheckResult]:
    actual_root = (root or Path.cwd()).resolve()
    return [
        check_python(),
        check_git_root(actual_root),
        check_codex_config(actual_root),
        check_agent_files(actual_root),
        check_skill_files(actual_root),
        check_project_direction(actual_root),
        check_python_packages(),
        check_sumo_binary(),
        check_task_manifests(actual_root),
    ]


def print_results(results: Sequence[CheckResult]) -> None:
    for result in results:
        marker = result.status.upper()
        print(f"[{marker}] {result.name}: {result.detail}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ai_quantum_hvtc")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Check local scaffold health.")

    args = parser.parse_args(argv)
    if args.command != "doctor":
        parser.error(f"unknown command: {args.command}")

    results = run_checks()
    print_results(results)
    return 0 if all(result.ok for result in results) else 1
