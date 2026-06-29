"""Compatibility wrapper for public-finance scoring.

New code should import from :mod:`ai_quantum_hvtc.public_finance`.
"""

from __future__ import annotations

from ai_quantum_hvtc.public_finance.scoring import CandidateScore, score_candidates

__all__ = ["CandidateScore", "score_candidates"]
