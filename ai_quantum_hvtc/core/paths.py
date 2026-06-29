from __future__ import annotations

from pathlib import Path


def ensure_parent_dir(path: Path) -> Path:
    """Create the parent directory for an output path and return the path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    return path
