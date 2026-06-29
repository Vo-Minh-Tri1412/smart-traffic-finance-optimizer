from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class InvestmentOption:
    candidate_id: str
    cost_vnd: float
    value_vnd: float
    source_row: dict[str, str]


def optimize_exact(options: list[InvestmentOption], budget_vnd: float) -> list[InvestmentOption]:
    best_value = float("-inf")
    best_subset: list[InvestmentOption] = []
    for size in range(len(options) + 1):
        for subset_tuple in combinations(options, size):
            subset = list(subset_tuple)
            cost = sum(option.cost_vnd for option in subset)
            if cost > budget_vnd:
                continue
            value = sum(option.value_vnd for option in subset)
            if value > best_value:
                best_value = value
                best_subset = subset
    return best_subset


def optimize_greedy(options: list[InvestmentOption], budget_vnd: float) -> list[InvestmentOption]:
    selected: list[InvestmentOption] = []
    remaining_budget = budget_vnd
    sorted_options = sorted(
        options,
        key=lambda option: option.value_vnd / option.cost_vnd if option.cost_vnd > 0 else 0.0,
        reverse=True,
    )
    for option in sorted_options:
        if option.value_vnd <= 0:
            continue
        if option.cost_vnd <= remaining_budget:
            selected.append(option)
            remaining_budget -= option.cost_vnd
    return selected


def qubo_matrix(
    options: list[InvestmentOption],
    *,
    budget_vnd: float,
    penalty: float = 1e-12,
) -> dict[str, dict[str, float]]:
    """Export a simple budget-constrained QUBO matrix.

    The represented minimization objective is:
    -value*x + penalty*(cost*x - budget)^2.
    """

    matrix: dict[str, dict[str, float]] = {}
    for i, left in enumerate(options):
        row: dict[str, float] = {}
        for j, right in enumerate(options):
            if j < i:
                continue
            value_term = -left.value_vnd if i == j else 0.0
            budget_term = penalty * left.cost_vnd * right.cost_vnd * (2.0 if i != j else 1.0)
            linear_budget_term = -2.0 * penalty * budget_vnd * left.cost_vnd if i == j else 0.0
            row[right.candidate_id] = round(value_term + budget_term + linear_budget_term, 6)
        matrix[left.candidate_id] = row
    return matrix
