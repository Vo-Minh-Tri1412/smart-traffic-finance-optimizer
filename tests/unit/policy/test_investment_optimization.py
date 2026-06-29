from __future__ import annotations

from ai_quantum_hvtc.policy import (
    InvestmentOption,
    optimize_exact,
    optimize_greedy,
    qubo_matrix,
)


def test_exact_optimizer_finds_best_known_subset() -> None:
    options = [
        InvestmentOption("A", cost_vnd=6, value_vnd=12, source_row={}),
        InvestmentOption("B", cost_vnd=4, value_vnd=7, source_row={}),
        InvestmentOption("C", cost_vnd=5, value_vnd=9, source_row={}),
    ]

    selected = optimize_exact(options, budget_vnd=10)

    assert {option.candidate_id for option in selected} == {"A", "B"}


def test_greedy_skips_negative_value_options() -> None:
    options = [
        InvestmentOption("A", cost_vnd=5, value_vnd=-1, source_row={}),
        InvestmentOption("B", cost_vnd=4, value_vnd=8, source_row={}),
    ]

    selected = optimize_greedy(options, budget_vnd=10)

    assert [option.candidate_id for option in selected] == ["B"]


def test_qubo_export_contains_candidate_ids() -> None:
    options = [
        InvestmentOption("A", cost_vnd=5, value_vnd=10, source_row={}),
        InvestmentOption("B", cost_vnd=4, value_vnd=6, source_row={}),
    ]

    matrix = qubo_matrix(options, budget_vnd=7)

    assert set(matrix) == {"A", "B"}
    assert "B" in matrix["A"]
