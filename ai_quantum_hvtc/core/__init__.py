"""Shared infrastructure that is not owned by a domain package."""

from __future__ import annotations

from .paths import ensure_parent_dir

__all__ = ["ensure_parent_dir"]
