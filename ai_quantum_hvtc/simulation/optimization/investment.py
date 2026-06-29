"""Compatibility wrapper for policy investment optimization.

New code should import from :mod:`ai_quantum_hvtc.policy`.
"""

from __future__ import annotations

from ai_quantum_hvtc.policy.algorithms.investment import (
    InvestmentOption,
    optimize_exact,
    optimize_greedy,
    qubo_matrix,
)

__all__ = ["InvestmentOption", "optimize_exact", "optimize_greedy", "qubo_matrix"]
