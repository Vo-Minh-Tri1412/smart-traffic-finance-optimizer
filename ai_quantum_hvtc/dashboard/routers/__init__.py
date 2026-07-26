from __future__ import annotations

from .compare import router as compare_router
from .district import router as district_router
from .finance import router as finance_router
from .introspect import router as introspect_router
from .runs import router as runs_router
from .system import router as system_router

__all__ = [
    "compare_router",
    "district_router",
    "finance_router",
    "introspect_router",
    "runs_router",
    "system_router",
]
