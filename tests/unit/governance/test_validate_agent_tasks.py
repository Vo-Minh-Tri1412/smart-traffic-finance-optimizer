from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from scripts.admin.validate_agent_tasks import ValidationError, validate_manifest_path


def write_manifest(
    tmp_path: Path,
    *,
    owner: str = "worker",
    allowed_paths: tuple[str, ...] = ("work/example/**",),
) -> Path:
    manifest = tmp_path / "TASK-001.toml"
    allowed_lines = "\n".join(f'              "{path}",' for path in allowed_paths)
    manifest.write_text(
        dedent(
            f"""
            id = "TASK-001"
            owner = "{owner}"
            branch = "codex/example"
            base_commit = "HEAD"
            allowed_paths = [
{allowed_lines}
            ]
            dependencies = []
            acceptance_commands = [
              "uv run pytest",
            ]
            status = "planned"

            [handoff]
            summary = ""
            validation = []
            risks = []
            next_steps = []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_validator_accepts_changed_file_inside_allowed_paths(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)

    result = validate_manifest_path(manifest, changed_files=["work/example/module.py"])

    assert result.changed_file_count == 1


def test_validator_rejects_changed_file_outside_allowed_paths(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)

    with pytest.raises(ValidationError, match="outside allowed_paths"):
        validate_manifest_path(manifest, changed_files=["other/module.py"])


def test_validator_rejects_shared_file_for_non_integrator(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, allowed_paths=("scripts/**",))

    with pytest.raises(ValidationError, match="shared files require owner"):
        validate_manifest_path(manifest, changed_files=["scripts/validate_agent_tasks.py"])
