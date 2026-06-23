from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "id",
    "owner",
    "branch",
    "base_commit",
    "allowed_paths",
    "dependencies",
    "acceptance_commands",
    "status",
    "handoff",
}

STATUS_VALUES = {"planned", "in_progress", "handoff", "done", "blocked"}

SHARED_PATTERNS = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".github/**",
    ".codex/**",
    "coordination/**",
    "scripts/**",
)


class ValidationError(Exception):
    """Raised when a task manifest or diff violates repository governance."""


@dataclass(frozen=True)
class TaskManifest:
    path: Path
    data: dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.data["id"])

    @property
    def owner(self) -> str:
        return str(self.data["owner"])

    @property
    def base_commit(self) -> str:
        return str(self.data["base_commit"])

    @property
    def allowed_paths(self) -> list[str]:
        values = self.data["allowed_paths"]
        if not isinstance(values, list):
            raise ValidationError(f"{self.path}: allowed_paths must be a list")
        return [str(value) for value in values]


@dataclass(frozen=True)
class ValidationResult:
    manifest: Path
    changed_file_count: int


def normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def pattern_matches(pattern: str, candidate: str) -> bool:
    normalized_pattern = normalize_path(pattern)
    normalized_candidate = normalize_path(candidate)
    if normalized_pattern.endswith("/"):
        return normalized_candidate.startswith(normalized_pattern)
    if any(char in normalized_pattern for char in "*?[]"):
        return fnmatch.fnmatchcase(normalized_candidate, normalized_pattern)
    return normalized_candidate == normalized_pattern


def is_allowed(path: str, allowed_paths: Sequence[str]) -> bool:
    return any(pattern_matches(pattern, path) for pattern in allowed_paths)


def is_shared(path: str) -> bool:
    return any(pattern_matches(pattern, path) for pattern in SHARED_PATTERNS)


def load_manifest(path: Path) -> TaskManifest:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"{path}: TOML error: {exc}") from exc
    return TaskManifest(path=path, data=data)


def _require_string(data: dict[str, Any], field: str, path: Path) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{path}: {field} must be a non-empty string")


def _require_string_list(data: dict[str, Any], field: str, path: Path) -> None:
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{path}: {field} must be a list of strings")


def validate_manifest_shape(manifest: TaskManifest) -> None:
    data = manifest.data
    missing = sorted(REQUIRED_FIELDS - set(data))
    if missing:
        raise ValidationError(f"{manifest.path}: missing required fields: {', '.join(missing)}")

    for field in ("id", "owner", "branch", "base_commit", "status"):
        _require_string(data, field, manifest.path)

    for field in ("allowed_paths", "dependencies", "acceptance_commands"):
        _require_string_list(data, field, manifest.path)

    if data["status"] not in STATUS_VALUES:
        allowed = ", ".join(sorted(STATUS_VALUES))
        raise ValidationError(f"{manifest.path}: status must be one of {allowed}")

    if not data["allowed_paths"]:
        raise ValidationError(f"{manifest.path}: allowed_paths must not be empty")

    handoff = data["handoff"]
    if not isinstance(handoff, dict):
        raise ValidationError(f"{manifest.path}: handoff must be a TOML table")


def collect_changed_files(base_commit: str, cwd: Path) -> list[str]:
    specs = (f"{base_commit}...HEAD", f"{base_commit}..HEAD")
    for spec in specs:
        result = subprocess.run(
            ["git", "diff", "--name-only", spec],
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    raise ValidationError(
        "could not collect changed files with git diff; check base_commit and repository state"
    )


def validate_changed_files(manifest: TaskManifest, changed_files: Sequence[str]) -> None:
    allowed_paths = manifest.allowed_paths
    violations: list[str] = []
    shared_violations: list[str] = []

    for changed_file in changed_files:
        normalized = normalize_path(changed_file)
        if not is_allowed(normalized, allowed_paths):
            violations.append(normalized)
        if manifest.owner != "integrator" and is_shared(normalized):
            shared_violations.append(normalized)

    if violations:
        formatted = ", ".join(sorted(violations))
        raise ValidationError(f"{manifest.path}: changed files outside allowed_paths: {formatted}")
    if shared_violations:
        formatted = ", ".join(sorted(shared_violations))
        raise ValidationError(
            f'{manifest.path}: shared files require owner = "integrator": {formatted}'
        )


def validate_manifest_path(
    path: Path,
    *,
    changed_files: Sequence[str] | None = None,
    skip_diff: bool = False,
    cwd: Path | None = None,
) -> ValidationResult:
    manifest = load_manifest(path)
    validate_manifest_shape(manifest)

    actual_changed_files: Sequence[str]
    if skip_diff:
        actual_changed_files = []
    elif changed_files is not None:
        actual_changed_files = changed_files
    else:
        actual_cwd = cwd or Path.cwd()
        actual_changed_files = collect_changed_files(manifest.base_commit, actual_cwd)

    validate_changed_files(manifest, actual_changed_files)
    return ValidationResult(path, len(actual_changed_files))


def discover_manifests(tasks_dir: Path) -> list[Path]:
    return sorted(path for path in tasks_dir.glob("*.toml") if path.is_file())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate multi-agent task manifests.")
    parser.add_argument("--task", action="append", type=Path, help="Task manifest path.")
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=Path("coordination/tasks"),
        help="Directory to scan when --task is not provided.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=None,
        help="Changed file to validate instead of reading git diff.",
    )
    parser.add_argument(
        "--skip-diff",
        action="store_true",
        help="Validate manifest shape without checking changed files.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    task_paths = (
        [Path(path) for path in args.task] if args.task else discover_manifests(args.tasks_dir)
    )
    if not task_paths:
        print(f"No task manifests found in {args.tasks_dir}", file=sys.stderr)
        return 1

    try:
        results = [
            validate_manifest_path(
                path,
                changed_files=args.changed_file,
                skip_diff=args.skip_diff,
                cwd=Path.cwd(),
            )
            for path in task_paths
        ]
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for result in results:
        print(f"validated {result.manifest}: {result.changed_file_count} changed file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
