from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

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
    ok: bool
    detail: str


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
    ok = sys.version_info[:2] == (3, 12)
    detail = f"Python {version}"
    if not ok:
        detail += " (expected Python 3.12)"
    return CheckResult("python", ok, detail)


def check_git_root(root: Path) -> CheckResult:
    detected = _run_git_root(root)
    if detected is None:
        return CheckResult("git-root", False, "not inside a Git repository")
    ok = detected == root.resolve()
    detail = str(detected)
    if not ok:
        detail += f" (expected {root.resolve()})"
    return CheckResult("git-root", ok, detail)


def check_codex_config(root: Path) -> CheckResult:
    path = root / ".codex" / "config.toml"
    if not path.exists():
        return CheckResult("codex-config", False, "missing .codex/config.toml")

    try:
        config = _read_toml(path)
    except tomllib.TOMLDecodeError as exc:
        return CheckResult("codex-config", False, f"TOML error: {exc}")

    agents = config.get("agents")
    if not isinstance(agents, dict):
        return CheckResult("codex-config", False, "missing [agents] table")

    if agents.get("max_threads") != 6:
        return CheckResult("codex-config", False, "agents.max_threads must be 6")
    if agents.get("max_depth") != 1:
        return CheckResult("codex-config", False, "agents.max_depth must be 1")
    if agents.get("write_tasks_require_manifest") is not True:
        return CheckResult("codex-config", False, "write_tasks_require_manifest must be true")

    return CheckResult("codex-config", True, ".codex/config.toml")


def check_agent_files(root: Path) -> CheckResult:
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
        return CheckResult("agent-files", False, "; ".join(failures))
    return CheckResult("agent-files", True, f"{len(EXPECTED_AGENTS)} custom agents")


def check_skill_files(root: Path) -> CheckResult:
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
        return CheckResult("skill-files", False, "; ".join(failures))
    return CheckResult("skill-files", True, f"{len(EXPECTED_SKILLS)} repo skills")


def check_task_manifests(root: Path) -> CheckResult:
    script = root / "scripts" / "validate_agent_tasks.py"
    tasks_dir = root / "coordination" / "tasks"
    if not script.exists():
        return CheckResult("task-manifests", False, "missing task validator")
    if not tasks_dir.exists():
        return CheckResult("task-manifests", False, "missing coordination/tasks")

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
        return CheckResult("task-manifests", False, detail)
    return CheckResult("task-manifests", True, result.stdout.strip())


def run_checks(root: Path | None = None) -> list[CheckResult]:
    actual_root = (root or Path.cwd()).resolve()
    return [
        check_python(),
        check_git_root(actual_root),
        check_codex_config(actual_root),
        check_agent_files(actual_root),
        check_skill_files(actual_root),
        check_task_manifests(actual_root),
    ]


def print_results(results: Sequence[CheckResult]) -> None:
    for result in results:
        marker = "OK" if result.ok else "FAIL"
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
