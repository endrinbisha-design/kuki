"""Regression guards for audit findings and new research models."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from central_park_tmax.evaluation.splits import (
    Fold, _validate_non_overlap, train_valid_split, train_tune_calibration_split)
from central_park_tmax.models.features_frame import FeatureMatrix
from central_park_tmax.models.boosting import BoostingResidualModel
from central_park_tmax.models.linear import LinearResidual
from central_park_tmax.models.quantiles import QuantileBoosting
from central_park_tmax.models.market_anchor import MarketAnchoredBlend
from central_park_tmax.models.conditional_rise import ConditionalRemainingRise

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frame(n=60):
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n),
                         "baseline_tmax_f": np.full(n, 50.),
                         "target_report_max_f": 50 + np.sin(np.arange(n)),
                         "signal": np.arange(n, dtype=float),
                         "absent": np.full(n, np.nan)})


def test_matrix_keeps_missingness_and_excludes_custom_target():
    df = frame().rename(columns={"target_report_max_f": "custom_label"})
    fm = FeatureMatrix.from_frame(df, target_col="custom_label")
    assert "custom_label" not in fm.feature_names
    assert fm.X.absent.isna().all()
    with pytest.raises(ValueError, match="target"):
        FeatureMatrix.from_frame(df, target_col="custom_label", feature_names=["custom_label"])


def test_all_requested_features_missing_preserves_rows():
    fm = FeatureMatrix.from_frame(frame(3))
    aligned = fm.X_for(["unavailable"])
    assert aligned.shape == (3, 1)
    assert aligned.unavailable.isna().all()


@pytest.mark.parametrize("kind", ["boosting", "linear", "quantile"])
def test_predictions_are_independent_of_other_test_rows(kind):
    train = frame()
    fm = FeatureMatrix.from_frame(train)
    test = frame(2)
    test["signal"] = [np.nan, 1e9]
    test["absent"] = [np.nan, 1e9]
    one = FeatureMatrix.from_frame(test.iloc[:1])
    batch = FeatureMatrix.from_frame(test)
    if kind == "boosting":
        m = BoostingResidualModel(backend="sklearn", n_estimators=8).fit(fm)
        assert m.imputer.statistics_[0] == 29.5
        assert not m.model.early_stopping
        a, b = m.predict(one), m.predict(batch)
    elif kind == "linear":
        m = LinearResidual(ridge=True).fit(fm)
        a, b = m.predict(one), m.predict(batch)
    else:
        m = QuantileBoosting(quantiles=[.1, .5, .9], n_estimators=5).fit(fm)
        a, b = m.predict_quantiles(one).to_numpy(), m.predict_quantiles(batch).to_numpy()
    np.testing.assert_allclose(a[0], b[0])


def test_live_prediction_preserves_missing_features_for_fitted_imputer():
    from central_park_tmax.pipelines.predict import _feature_matrix_for_predict
    fm = _feature_matrix_for_predict({"date": "2026-01-01"}, ["signal"], 50)
    assert np.isnan(fm.X.signal.iloc[0])


def test_split_keeps_all_same_day_rows_together():
    df = pd.concat([frame(31), frame(31)], ignore_index=True)
    a, b = train_valid_split(df, .17)
    assert a.date.max() < b.date.min()
    core, tune, cal = train_tune_calibration_split(df)
    assert core.date.max() < tune.date.min() < cal.date.min()
    assert len(core) + len(tune) + len(cal) == len(df)


@pytest.mark.parametrize("train,test,end", [("2025-01-01","2025-01-01","2025-02-01"),
                                           ("2024-01-01","2025-03-01","2025-02-01")])
def test_single_or_last_invalid_fold_rejected(train, test, end):
    f = Fold(0, pd.Timestamp(train).date(), pd.Timestamp(test).date(), pd.Timestamp(end).date())
    with pytest.raises(ValueError):
        _validate_non_overlap([f])


def test_calibration_labels_do_not_select_or_fit_point_model(tmp_path, monkeypatch):
    from central_park_tmax.config import load_config
    from central_park_tmax.pipelines.train import train_models
    from central_park_tmax.models.quantiles import QuantileBoosting
    monkeypatch.setattr(QuantileBoosting, "fit", lambda self, fm: self)
    cfg = load_config(project_root=tmp_path)
    cfg.models.boosting.backend = "sklearn"
    cfg.models.boosting.n_estimators = 8
    cfg.models.hyperparameter_search.enabled = False
    df = frame(80)
    first = train_models(cfg, df, save_path=tmp_path / "a.joblib").models["default"]
    changed = df.copy()
    changed.loc[changed.date >= pd.Timestamp(first.calibration_start), "target_report_max_f"] += 100
    second = train_models(cfg, changed, save_path=tmp_path / "b.joblib").models["default"]
    assert first.n_train + first.n_calibration < len(df)
    assert first.train_end < first.tune_start <= first.tune_end < first.calibration_start
    x = FeatureMatrix.from_frame(df)
    np.testing.assert_allclose(first.boosting.predict(x), second.boosting.predict(x))
    np.testing.assert_allclose(second.oos_residuals - first.oos_residuals, 100)


def test_market_anchor_rejects_bad_data_and_unfit_predictions():
    m = MarketAnchoredBlend(min_dates=2)
    with pytest.raises(RuntimeError):
        m.predict([.2], [.3])
    with pytest.raises(ValueError):
        m.fit([np.nan], [.3], [1], ["2025-01-01"])
    with pytest.raises(ValueError):
        m.fit([.2], [.3], [.5], ["2025-01-01"])


def test_market_anchor_learns_zero_weight_for_harmful_model():
    dates = pd.date_range("2025-01-01", periods=30)
    y = np.tile([0, 1], 15)
    market = .1 + .8 * y
    m = MarketAnchoredBlend().fit(1-y, market, y, dates)
    assert m.weather_weight == 0
    np.testing.assert_allclose(m.predict(1-y, market), market)
    with pytest.raises(ValueError, match="after"):
        m.predict([.2], [.3], forecast_date=dates[-1])


def test_market_anchor_preserves_complete_distribution():
    d = pd.date_range("2025-01-01", periods=30)
    y = np.tile([0,1], 15)
    m = MarketAnchoredBlend().fit(.05+.9*y, np.full(30, .5), y, d)
    assert 0 < m.weather_weight <= 1
    out = m.predict([.1,.3,.6], [.2,.3,.5])
    assert out.sum() == pytest.approx(1)


def test_market_fit_does_not_overweight_duplicate_snapshots_per_date():
    d = pd.date_range("2025-01-01", periods=30)
    p, m, y = np.linspace(.1,.9,30), np.full(30,.5), np.tile([0,1],15)
    original = MarketAnchoredBlend().fit(p,m,y,d)
    index = np.r_[np.arange(30), np.repeat(0, 100)]
    dup = MarketAnchoredBlend().fit(p[index],m[index],y[index],d[index])
    assert original.weather_weight == pytest.approx(dup.weather_weight)


def test_probability_evaluation_never_sees_future_labels():
    audit = script("audit_probability_models")
    n = 45
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=n),
                       "series": "test", "hour": 13, "bucket": "80-81",
                       "model_p": np.linspace(.1,.9,n), "price": .4,
                       "won": np.tile([0,1,0],15)})
    first = audit.evaluate(df)
    changed = df.copy()
    changed.loc[changed.date >= "2025-02-08", "won"] = 1-changed.won
    second = audit.evaluate(changed)
    before = first.date < "2025-02-08"
    np.testing.assert_allclose(first.loc[before,list(audit.MODELS)], second.loc[before,list(audit.MODELS)])
    assert (first.train_end <= first.date - pd.Timedelta(days=2)).all()


def test_legacy_recalibration_folds_are_past_only():
    dates = pd.Series(pd.date_range("2025-01-01", periods=68)).repeat(3).reset_index(drop=True)
    folds = list(script("recalibrate_pmf").chronological_folds(dates))
    assert folds
    for tr, te in folds:
        assert dates[tr].max() <= dates[te].min()-pd.Timedelta(days=2)


def test_candle_prices_keep_their_dates(monkeypatch):
    mod = script("real_price_backtest")
    candles = [{"end_period_ts": int(pd.Timestamp(d, tz="UTC").timestamp()),
                "yes_bid": {"close_dollars": str(b)}, "yes_ask": {"close_dollars": str(b+.1)}}
               for d,b in [("2026-06-01 17:00",.1),("2026-06-02 17:00",.8)]]
    monkeypatch.setattr(mod, "_get", lambda url: {"candlesticks": candles})
    result = mod.hourly_prices("s","t","2026-06-02T23:00:00Z",-4)
    assert result[(pd.Timestamp("2026-06-01").date(),13)] == pytest.approx(.15)
    assert result[(pd.Timestamp("2026-06-02").date(),13)] == pytest.approx(.85)


def rise_frame():
    return pd.DataFrame({"date": pd.date_range("2025-01-01",periods=60), "hour":16,
                         "drop_from_max": np.tile([0,4.],30),
                         "slope": np.tile([1.,-1.],30), "remaining_rise":np.tile([3.,0.],30)})


def test_conditional_rise_conditions_probability_and_is_monotone():
    df = rise_frame()
    model = ConditionalRemainingRise().fit(df)
    test = df.iloc[:2].copy()
    test["date"] = pd.Timestamp("2026-01-01")
    cdf, mean = model.predict(test)
    assert cdf[1,0] > cdf[0,0]  # cooling far below peak -> more likely no further rise
    assert mean[1] < mean[0]
    assert (np.diff(cdf,axis=1) >= 0).all()
    assert ((cdf>=0)&(cdf<=1)).all()
    with pytest.raises(ValueError, match="follow"):
        model.predict(df)


def test_rise_builder_excludes_later_observations_in_same_hour():
    audit = script("audit_conditional_rise")
    valid = pd.date_range("2025-07-01 00:51", periods=24, freq="h", tz="America/New_York")
    temps = np.full(24, 70.)
    temps[13] = 95.
    raw = pd.DataFrame({"valid":valid.tz_convert("UTC"),"tmpf":temps})
    out = audit.build_snapshots(raw)
    early = out[out.hour==13].iloc[0]
    late = out[out.hour==14].iloc[0]
    assert early.observed_max==70 and early.remaining_rise==25
    assert late.observed_max==95 and late.remaining_rise==0
    assert (out.last_observation_utc <= out.cutoff_utc).all()


def test_continuous_metrics_pool_by_rows_not_by_folds():
    from central_park_tmax.evaluation.backtest import _aggregate
    rows = [dict(model="m",n=n,mae=e,rmse=e,mean_error=e,pct_within_2f=0,test_year=2025)
            for n,e in [(1,10),(9,0)]]
    out = _aggregate(rows,["m"])["m"]
    assert out["mae"]==1
    assert out["rmse"]==pytest.approx(np.sqrt(10))


def test_previous_evening_cannot_see_that_days_final_daily_aggregate():
    from central_park_tmax.features.build_features import _completed_daily_history
    issue = pd.Timestamp("2025-07-01 19:00", tz="America/New_York")
    history = pd.Series([80.,85.,120.], index=pd.date_range("2025-06-30",periods=3))
    kept = _completed_daily_history(history, issue)
    assert len(kept)==1 and kept.iloc[0]==80
    assert _completed_daily_history(None, issue) is None


def test_mos_previous_evening_lags_by_calendar_days_not_rows():
    mod = script("mos_multiyear_backtest")
    idx = pd.to_datetime(["2025-01-01","2025-01-02","2025-01-04"])
    df = pd.DataFrame({"mos_tmax_f":[50.,50.,50.], "actual_tmax_f":[60.,80.,90.],
                       "error":[10.,30.,40.]},index=idx)
    result = mod.add_features(df)
    assert result.loc["2025-01-04","last_completed_actual"]==80.
    assert np.isnan(result.loc["2025-01-02","last_completed_actual"])
    assert np.isnan(result.loc["2025-01-04","yesterday_mos"])


def test_market_archive_keeps_arrival_time_and_subcent_prices():
    mod = script("archive_kalshi_prices")
    start = pd.Timestamp("2026-09-16 13:52:07.123456",tz="UTC").to_pydatetime()
    received = pd.Timestamp("2026-09-16 13:52:08.654321",tz="UTC").to_pydatetime()
    row = mod.snapshot_row({"ticker":"test","yes_bid_dollars":"0.0125"},"series",start,received)
    assert row["yes_bid_dollars"]=="0.0125"
    assert row["snapshot_utc"]==received.isoformat()
    assert row["yes_ask_dollars"]==""
    assert "v2" in mod.OUT.name
    with pytest.raises(ValueError):
        mod.snapshot_row({"ticker":"test","yes_bid_dollars":"NaN"},"series",start,received)
