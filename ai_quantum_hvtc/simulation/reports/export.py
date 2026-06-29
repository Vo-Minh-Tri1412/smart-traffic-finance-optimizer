"""Compatibility wrapper for report exports.

New code should import from :mod:`ai_quantum_hvtc.reports`.
"""

from __future__ import annotations

from ai_quantum_hvtc.reports.export import (
    candidate_scores_to_csv,
    load_candidate_options_from_csv,
    result_to_json,
    result_to_trace_jsonl,
    selected_options_to_csv,
    write_markdown_report,
)

__all__ = [
    "candidate_scores_to_csv",
    "load_candidate_options_from_csv",
    "result_to_json",
    "result_to_trace_jsonl",
    "selected_options_to_csv",
    "write_markdown_report",
]
