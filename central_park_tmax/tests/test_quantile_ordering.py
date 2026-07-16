import numpy as np

from central_park_tmax.models.quantiles import EmpiricalResidualQuantiles, enforce_monotone
from central_park_tmax.evaluation.diagnostics import DataQualityError, check_quantiles_ordered


def test_enforce_monotone_sorts_rows():
    mat = np.array([[3.0, 1.0, 2.0], [9.0, 8.0, 10.0]])
    out = enforce_monotone(mat)
    assert np.all(np.diff(out, axis=1) >= 0)


def test_empirical_residual_quantiles_ordered():
    q = EmpiricalResidualQuantiles(quantiles=[0.1, 0.25, 0.5, 0.75, 0.9])
    q.fit(np.random.default_rng(0).normal(0, 2, 5000))
    out = q.predict_quantiles(np.array([88.0, 90.0]))
    for _, row in out.iterrows():
        assert np.all(np.diff(row.to_numpy()) >= 0)


def test_check_quantiles_ordered_raises_on_crossing():
    import pytest
    with pytest.raises(DataQualityError):
        check_quantiles_ordered(np.array([85.0, 84.0, 90.0]))


def test_check_quantiles_ordered_passes_when_sorted():
    check_quantiles_ordered(np.array([80.0, 85.0, 90.0]))  # should not raise
