import numpy as np
import pandas as pd

from central_park_tmax.models.baselines import RollingBiasBaseline, rolling_bias_series
from central_park_tmax.evaluation.splits import Fold, folds_from_config, rolling_origin_from_dates


def test_rolling_bias_uses_only_prior_errors():
    dates = pd.Series(pd.date_range("2024-01-01", periods=5, freq="D"))
    baseline = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0])
    target = pd.Series([52.0, 54.0, 56.0, 58.0, 60.0])  # actual always above baseline
    corrected = rolling_bias_series(dates, baseline, target, window_days=30)
    # First row has no prior errors -> no correction (equals baseline).
    assert corrected[0] == 50.0
    # Second row's correction uses only row 0's error (+2) -> 52.
    assert abs(corrected[1] - 52.0) < 1e-9
    # Row's own (future) error never leaks: correction < actual for the increasing series.
    assert all(corrected[i] < target[i] for i in range(len(dates)))


def test_rolling_bias_baseline_predict_excludes_current():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=4, freq="D"),
        "baseline_tmax_f": [50.0, 50.0, 50.0, 50.0],
    })
    target = pd.Series([53.0, 53.0, 53.0, 53.0])
    rb = RollingBiasBaseline(30).fit(df, target)
    preds = rb.predict(df)
    # Prediction for the first date uses no history from the same frame beyond earlier dates.
    assert preds[0] == 50.0  # nothing strictly before it in fitted history for that date


def test_folds_non_overlapping_and_ordered():
    from central_park_tmax.config import FoldCfg
    folds = folds_from_config([
        FoldCfg(train_end="2021-12-31", test_start="2022-01-01", test_end="2022-12-31"),
        FoldCfg(train_end="2022-12-31", test_start="2023-01-01", test_end="2023-12-31"),
    ])
    assert folds[0].train_end < folds[0].test_start
    assert folds[1].test_start > folds[0].test_end


def test_overlapping_folds_rejected():
    import pytest
    from central_park_tmax.config import FoldCfg
    with pytest.raises(ValueError):
        folds_from_config([
            FoldCfg(train_end="2021-12-31", test_start="2022-01-01", test_end="2022-12-31"),
            FoldCfg(train_end="2022-06-30", test_start="2022-06-01", test_end="2022-12-31"),
        ])


def test_train_mask_excludes_test_period():
    fold = Fold(0, __import__("datetime").date(2021, 12, 31),
                __import__("datetime").date(2022, 1, 1), __import__("datetime").date(2022, 12, 31))
    dates = pd.Series(pd.to_datetime(["2021-06-01", "2022-03-01"]))
    tr = fold.train_mask(dates).tolist()
    te = fold.test_mask(dates).tolist()
    assert tr == [True, False]
    assert te == [False, True]


def test_auto_folds_from_span_are_chronological():
    from central_park_tmax.evaluation.splits import auto_folds_from_span
    dates = pd.Series(pd.date_range("2024-11-15", "2025-01-31", freq="D").astype(str))
    folds = auto_folds_from_span(dates, n_folds=3)
    assert len(folds) == 3
    for f in folds:
        assert f.train_end < f.test_start
    for a, b in zip(folds, folds[1:]):
        assert b.test_start > a.test_end
    # Training window always precedes its test window; first 40% reserved for training.
    assert folds[0].test_start > pd.Timestamp("2024-12-10").date()
