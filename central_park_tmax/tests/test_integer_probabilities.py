import numpy as np

from central_park_tmax.models.discrete_outcomes import (integer_report_distribution,
                                                        simulate_from_quantiles,
                                                        simulate_from_residuals)
from central_park_tmax.models.reporting_convention import apply_reporting_convention


def test_integer_probabilities_sum_to_one():
    rng = np.random.default_rng(0)
    samples = rng.normal(88.5, 2.0, 50000)
    dist = integer_report_distribution(samples, convention="round_half_up")
    assert abs(dist.total() - 1.0) < 1e-9


def test_integer_probabilities_reasonable_mode():
    rng = np.random.default_rng(1)
    samples = rng.normal(89.0, 1.0, 50000)
    dist = integer_report_distribution(samples, convention="round_half_up")
    assert dist.mode() == 89


def test_reporting_convention_variants():
    assert apply_reporting_convention(89.5, "round_half_up") == 90
    assert apply_reporting_convention(89.4, "round_half_up") == 89
    assert apply_reporting_convention(89.9, "truncate") == 89
    assert apply_reporting_convention(89.1, "ceil") == 90
    assert apply_reporting_convention(90.0, "max_of_rounded", [88.6, 89.4, 90.2]) == 90


def test_simulate_from_residuals_centered():
    resid = np.array([-1.0, 0.0, 1.0])
    samples = simulate_from_residuals(88.0, resid, 30000, np.random.default_rng(2))
    assert abs(np.mean(samples) - 88.0) < 0.1


def test_simulate_from_quantiles_monotone_support():
    samples = simulate_from_quantiles([0.1, 0.5, 0.9], [85.0, 88.0, 91.0], 20000,
                                      np.random.default_rng(3))
    assert samples.min() < 88 < samples.max()
    dist = integer_report_distribution(samples)
    assert abs(dist.total() - 1.0) < 1e-9
    # support has no interior gaps
    keys = sorted(dist.pmf.keys())
    assert keys == list(range(keys[0], keys[-1] + 1))
