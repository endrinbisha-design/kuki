#!/usr/bin/env python3
"""Offline, strictly chronological comparison on the committed contract archive.

This evaluates probability transformations conditional on archived input quality.
The archive has candle midpoints, no reception timestamps/depth, incomplete boards,
and a legacy hour-only price join: results CANNOT establish executable alpha.
No trade returns, position sizes, or deployable calibration curves are generated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.models.market_anchor import MarketAnchoredBlend

MODELS = ("raw_weather", "chronological_isotonic", "market", "market_anchor")


def validate_archive(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="raise").dt.normalize()
    mapping = {True: 1, False: 0, "True": 1, "False": 0, "true": 1, "false": 0, 1: 1, 0: 0}
    df["won"] = df["won"].map(mapping)
    for col in ("model_p", "price", "won"):
        if not np.isfinite(df[col]).all() or not df[col].between(0, 1).all():
            raise ValueError(f"Invalid {col}.")
    if df["date"].isna().any() or df.duplicated(["series", "date", "hour", "bucket"]).any():
        raise ValueError("Missing dates or duplicate contract snapshots.")
    if df.groupby(["series", "date", "bucket"])["won"].nunique().gt(1).any():
        raise ValueError("Inconsistent settlement outcomes.")
    return df.sort_values(["date", "series", "hour", "bucket"]).reset_index(drop=True)


def evaluate(df, min_train_dates=30, embargo_days=2, penalty=0.01):
    if min_train_dates < 2 or embargo_days < 1:
        raise ValueError("Require at least two training dates and a positive calendar embargo.")
    df = validate_archive(df)
    outputs = []
    for series, city in df.groupby("series", sort=True):
        for day in sorted(city["date"].unique()):
            # Date-only archive: a two-day delay is an assumption, NOT evidence of
            # settlement availability. Future live work must use resolved_at timestamps.
            train = city[city["date"] <= day - pd.Timedelta(days=embargo_days)]
            test = city[city["date"] == day].copy()
            if train["date"].nunique() < min_train_dates:
                continue
            weights = 1.0 / train["date"].map(train["date"].value_counts())
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            iso.fit(train["model_p"], train["won"], sample_weight=weights)
            model = MarketAnchoredBlend(penalty=penalty, min_dates=min_train_dates).fit(
                train["model_p"], train["price"], train["won"], train["date"])
            test["raw_weather"] = test["model_p"]
            test["chronological_isotonic"] = iso.predict(test["model_p"])
            test["market"] = test["price"]
            test["market_anchor"] = model.predict(test["model_p"], test["price"], forecast_date=day)
            test["weather_weight"] = model.weather_weight
            test["train_end"] = train["date"].max()
            test["train_dates"] = train["date"].nunique()
            outputs.append(test)
    if not outputs:
        raise ValueError("Insufficient dates for chronological evaluation.")
    return pd.concat(outputs, ignore_index=True)


def score(frame):
    result = {}
    for name in MODELS:
        p = frame[name].clip(1e-6, 1 - 1e-6)
        tmp = frame.assign(_brier=(frame[name] - frame["won"]) ** 2,
                           _ll=-(frame["won"] * np.log(p) + (1 - frame["won"]) * np.log(1 - p)))
        # First equal weight to each city-day, then to each calendar date.
        daily = tmp.groupby(["date", "series"])[["_brier", "_ll"]].mean().groupby("date").mean()
        result[name] = {"brier": float(daily._brier.mean()), "log_loss": float(daily._ll.mean())}
    return result


def paired_interval(frame, candidate, block_days=7, draws=2000):
    """Paired circular moving-block bootstrap of loss differences by calendar day.

    Cross-city dependence is preserved. A short, single-season sample still cannot
    provide reliable evidence of regime robustness; this interval is descriptive.
    """
    delta = (frame[candidate] - frame.won) ** 2 - (frame.market - frame.won) ** 2
    d = frame.assign(delta=delta).groupby(["date", "series"]).delta.mean().groupby("date").mean()
    # Do not compress gaps into adjacent days without disclosing the assumption.
    if len(d) > 1 and not (d.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all():
        raise ValueError("Block bootstrap requires contiguous dates in this archive.")
    values = d.to_numpy()
    rng = np.random.default_rng(20260916)
    n = len(values)
    samples = []
    for _ in range(draws):
        starts = rng.integers(0, n, int(np.ceil(n / block_days)))
        indices = ((starts[:, None] + np.arange(block_days)) % n).ravel()[:n]
        samples.append(values[indices].mean())
    return {"mean_brier_difference_vs_market": float(values.mean()),
            "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
            "block_days": block_days, "draws": draws, "negative_is_better": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "backtest_datasets/real_price_backtest_trades.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/model_audit")
    args = parser.parse_args()
    df = pd.read_csv(args.input)
    pred = evaluate(df)
    report = {
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "protocol": {"min_train_dates": 30, "embargo_calendar_days": 2, "penalty": 0.01,
                     "refit": "each day using prior eligible dates only", "parameter_search": False},
        "n_rows": len(pred), "n_calendar_days": pred.date.nunique(),
        "n_city_days": len(pred[["series", "date"]].drop_duplicates()),
        "test_dates": [str(pred.date.min().date()), str(pred.date.max().date())],
        "scores": score(pred),
        "per_city": {s: score(g) for s, g in pred.groupby("series")},
        "paired_brier_vs_market": {m: paired_interval(pred, m) for m in MODELS if m != "market"},
        "mean_weather_weight": float(pred.groupby(["date", "series"]).weather_weight.first().mean()),
        "last_14_days_descriptive_only": score(pred[pred.date >= pred.date.max() - pd.Timedelta(days=13)]),
        "limitations": [
            "Previously examined archive, not a new untouched prospective holdout.",
            "Legacy candle date joins and input-generation provenance have not been reconstructed.",
            "Prices are midpoint/last-trade proxies, not executable prices; no depth or reception times.",
            "Two-day label embargo is assumed; actual resolution timestamps are missing.",
            "Incomplete between-contract boards: binary scores only, no joint PMF renormalization.",
            "Probability improvement is not evidence of tradable alpha; no live model is promoted."]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pred.to_csv(args.output_dir / "chronological_predictions.csv", index=False)
    (args.output_dir / "probability_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
