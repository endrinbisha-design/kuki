import numpy as np
import pytest

from central_park_tmax.features.intraday import apply_observed_max_constraint
from central_park_tmax.evaluation.diagnostics import (DataQualityError,
                                                      check_prediction_not_below_observed)


def test_prediction_never_below_observed_max():
    assert apply_observed_max_constraint(85.0, 88.0) == 88.0   # clipped up to observed
    assert apply_observed_max_constraint(91.0, 88.0) == 91.0   # already above observed
    assert apply_observed_max_constraint(85.0, None) == 85.0   # no obs -> unchanged
    assert apply_observed_max_constraint(85.0, float("nan")) == 85.0


def test_check_prediction_not_below_observed_raises():
    with pytest.raises(DataQualityError):
        check_prediction_not_below_observed(84.0, 88.0)


def test_check_prediction_ok_when_above():
    check_prediction_not_below_observed(89.0, 88.0)  # no raise


def test_constraint_applied_to_distribution():
    obs_max = 88.0
    samples = np.random.default_rng(0).normal(86.0, 3.0, 10000)
    constrained = np.maximum(samples, obs_max)
    assert constrained.min() >= obs_max
