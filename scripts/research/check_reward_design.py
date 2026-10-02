"""Arithmetic checks for the R0/R1 research proposal, NOT a SUMO evaluator.

All numbers are fictional examples, not calibrated local economic parameters.
These tests do not establish learning performance, feasibility or causal benefit.
Run: python scripts/research/check_reward_design.py
"""

import unittest


def time_cost(seconds, hourly_value):
    return seconds * hourly_value / 3600


def schedule_cost(arrival, earliest, latest, early_rate, late_rate):
    return (early_rate * max(earliest - arrival, 0) + late_rate * max(arrival - latest, 0)) / 3600


def empirical_cvar(values, alpha):
    """Equal-mass finite distribution; hinge minimum handles quantile ties."""
    if not values or not 0 <= alpha < 1:
        raise ValueError("Require nonempty observations and 0 <= alpha < 1")
    return min(
        eta + sum(max(z - eta, 0) for z in values) / ((1 - alpha) * len(values)) for eta in values
    )


class RewardArithmeticChecks(unittest.TestCase):
    def test_baseline_recovery(self):
        ledger = [0, 3, 9, 12]
        scale = 6
        rewards = [-(b - a) / scale for a, b in zip(ledger[:-1], ledger[1:], strict=True)]
        self.assertAlmostEqual(sum(rewards), -ledger[-1] / scale)

    def test_person_vehicle_accounting(self):
        self.assertEqual(3 * time_cost(600, 36000), sum(time_cost(600, 36000) for _ in range(3)))
        self.assertEqual(time_cost(600, 36000), 6000)

    def test_equal_travel_different_schedule(self):
        self.assertEqual(schedule_cost(900, 800, 1000, 18000, 72000), 0)
        self.assertEqual(schedule_cost(900, 500, 600, 18000, 72000), 6000)

    def test_early_arrival_is_not_automatically_better(self):
        self.assertGreater(
            schedule_cost(600, 900, 1000, 18000, 72000), schedule_cost(900, 900, 1000, 18000, 72000)
        )

    def test_lateness_accrues_before_arrival_and_stops_after(self):
        arrival, deadline, rate = 900, 600, 72000
        ledger = [
            rate * max(min(t, arrival) - deadline, 0) / 3600 for t in [0, 600, 700, 900, 1000]
        ]
        self.assertGreater(ledger[2], 0)
        self.assertEqual(ledger[-1], ledger[-2])
        self.assertEqual(
            sum(b - a for a, b in zip(ledger[:-1], ledger[1:], strict=True)),
            schedule_cost(arrival, 0, deadline, 0, rate),
        )

    def test_pending_insertion_is_not_free(self):
        planned, inserted, arrival = 0, 120, 600
        self.assertEqual(
            time_cost(arrival - planned, 36000),
            time_cost(inserted - planned, 36000) + time_cost(arrival - inserted, 36000),
        )

    def test_equal_mean_different_tail(self):
        self.assertEqual(sum([10, 10]), sum([0, 20]))
        self.assertEqual(empirical_cvar([10, 10], 0.5), 10)
        self.assertEqual(empirical_cvar([0, 20], 0.5), 20)

    def test_cvar_quantile_ties(self):
        self.assertEqual(empirical_cvar([0, 0, 0, 10], 0.5), 5)
        with self.assertRaises(ValueError):
            empirical_cvar([], 0.5)

    def test_shaping_discounted_telescoping(self):
        potentials = [-4, -8, -1, 0]
        for gamma in [1, 0.9]:
            total = sum(
                gamma**t * (gamma * b - a)
                for t, (a, b) in enumerate(zip(potentials[:-1], potentials[1:], strict=True))
            )
            self.assertAlmostEqual(total, -potentials[0])
        # A nonzero terminal potential would leave a policy-dependent remainder.
        self.assertNotEqual(-potentials[0] + (-3), -potentials[0])

    def test_complete_episode_lagrangian_identity(self):
        ledger, potentials = [0, 4, 12], [-4, -2, 0]
        scale, kappa = 6, 0.25
        # One violation and one slack constraint, with fixed dual variables.
        penalty = 2 * (20 - 10) / 10 + 3 * (2 - 4) / 4
        total = sum(
            -(b - a) / scale + kappa * (q - p)
            for a, b, p, q in zip(
                ledger[:-1], ledger[1:], potentials[:-1], potentials[1:], strict=True
            )
        )
        total -= penalty
        self.assertAlmostEqual(total, -ledger[-1] / scale - penalty - kappa * potentials[0])

    def test_qubo_pair_accounting_preserves_negative_interaction(self):
        base, first, second, pair = 100, 90, 92, 85
        benefit_first, benefit_second = base - first, base - second
        interaction = first + second - pair - base
        self.assertEqual(interaction, -3)
        self.assertEqual(benefit_first + benefit_second + interaction, base - pair)


if __name__ == "__main__":
    unittest.main(verbosity=2)
