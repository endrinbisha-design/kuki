from central_park_tmax.contracts import nhigh_rules as R
from central_park_tmax.contracts.probabilities import (probability_between_inclusive,
                                                       probability_exactly,
                                                       probability_greater_than,
                                                       probability_greater_than_or_equal,
                                                       probability_less_than,
                                                       probability_less_than_or_equal)


def test_90_not_greater_than_90():
    assert R.satisfies_greater_than(90, 90) is False


def test_90_between_88_and_90_inclusive():
    assert R.satisfies_between_inclusive(90, 88, 90) is True
    assert R.satisfies_between_inclusive(88, 88, 90) is True
    assert R.satisfies_between_inclusive(87, 88, 90) is False


def test_90_not_less_than_90():
    assert R.satisfies_less_than(90, 90) is False


def test_ge_and_le_boundaries():
    assert R.satisfies_greater_than_or_equal(90, 90) is True
    assert R.satisfies_less_than_or_equal(90, 90) is True
    assert R.satisfies_exactly(90, 90) is True
    assert R.satisfies_exactly(91, 90) is False


def test_probabilities_use_strict_and_inclusive_correctly():
    pmf = {88: 0.2, 89: 0.3, 90: 0.4, 91: 0.1}
    assert abs(probability_greater_than(pmf, 90) - 0.1) < 1e-9         # only 91
    assert abs(probability_greater_than_or_equal(pmf, 90) - 0.5) < 1e-9  # 90 + 91
    assert abs(probability_less_than(pmf, 90) - 0.5) < 1e-9            # 88 + 89
    assert abs(probability_less_than_or_equal(pmf, 90) - 0.9) < 1e-9   # 88+89+90
    assert abs(probability_between_inclusive(pmf, 88, 90) - 0.9) < 1e-9
    assert abs(probability_exactly(pmf, 90) - 0.4) < 1e-9


def test_gt_plus_le_equals_one():
    pmf = {85: 0.1, 88: 0.2, 90: 0.4, 92: 0.3}
    assert abs(probability_greater_than(pmf, 90) + probability_less_than_or_equal(pmf, 90) - 1.0) < 1e-9
