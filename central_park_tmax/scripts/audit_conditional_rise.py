#!/usr/bin/env python3
"""Offline annual walk-forward experiment; hourly-snapshot maxima, NOT settlement.

At 13:00 use only reports stamped <=13:00, never observations later in that hour.
Archive timestamps are observation times; reception latency is NOT known here.
Require broad day coverage and a recent pair of observations. Models use fixed
physical state bins and shrink small cells toward their time-of-day climatology.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.models.conditional_rise import ConditionalRemainingRise, THRESHOLDS


def build_snapshots(raw):
    df = raw.copy()
    df["valid"] = pd.to_datetime(df.valid, utc=True, errors="raise")
    df["tmpf"] = pd.to_numeric(df.tmpf, errors="coerce")
    df = df[df.tmpf.between(-40, 130)].sort_values("valid").drop_duplicates("valid", keep="last")
    df["local"] = df.valid.dt.tz_convert("America/New_York")
    df["date"] = df.local.dt.date
    rows = []
    for day, obs in df.groupby("date"):
        # Restrict to observed warm-season data, avoid partial first/last days.
        if day.month not in (5, 6, 7, 8, 9):
            continue
        if obs.local.dt.hour.nunique() < 20 or obs.local.dt.hour.min() > 1 or obs.local.dt.hour.max() < 23:
            continue
        final = float(obs.tmpf.max())
        for hour in range(13, 19):
            cutoff = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=hour)
            known = obs[obs.local <= cutoff]
            if len(known) < 2:
                continue
            last, previous = known.iloc[-1], known.iloc[-2]
            age = (cutoff - last.local).total_seconds() / 3600
            step = (last.local - previous.local).total_seconds() / 3600
            if age > 1.5 or not 0.1 <= step <= 2:
                continue
            omax = float(known.tmpf.max())
            rows.append({"date": pd.Timestamp(day), "hour": hour,
                         "last_observation_utc": last.valid, "cutoff_utc": cutoff.tz_convert("UTC"),
                         "observed_max": omax, "drop_from_max": omax - float(last.tmpf),
                         "slope": (float(last.tmpf) - float(previous.tmpf)) / step,
                         "remaining_rise": max(0.0, final - omax)})
    return pd.DataFrame(rows)


def evaluate(frame):
    rows, folds = [], []
    for year in sorted(frame.date.dt.year.unique()):
        train = frame[frame.date.dt.year < year]
        test = frame[frame.date.dt.year == year].copy()
        if train.date.nunique() < 200 or test.date.nunique() < 30:
            continue
        model = ConditionalRemainingRise(prior_strength=30).fit(train)
        outcomes = (test.remaining_rise.to_numpy()[:, None] <= THRESHOLDS)
        for name, flag in (("hour_only", False), ("conditional", True)):
            cdf, mean = model.predict(test, conditional=flag)
            test[name + "_cdf_brier"] = ((cdf - outcomes)**2).mean(axis=1)
            test[name + "_no_rise_brier"] = (cdf[:, 0] - outcomes[:, 0])**2
            test[name + "_abs_error"] = abs(mean - test.remaining_rise.to_numpy())
        test["train_end"] = train.date.max()
        folds.append({"year": int(year), "train_days": train.date.nunique(),
                      "test_days": test.date.nunique(), "scores": summarize(test)})
        rows.append(test)
    if not rows:
        raise ValueError("Not enough data for annual walk-forward evaluation.")
    predictions = pd.concat(rows, ignore_index=True)
    return predictions, folds


def summarize(frame):
    columns = [c for c in frame.columns if c.endswith(("_cdf_brier", "_no_rise_brier", "_abs_error"))]
    return frame.groupby("date")[columns].mean().mean().to_dict()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=ROOT / "backtest_datasets/knyc_hourly_2019_2026.csv")
    p.add_argument("--output-dir", type=Path, default=ROOT / "reports/model_audit")
    args = p.parse_args()
    frame = build_snapshots(pd.read_csv(args.input))
    pred, folds = evaluate(frame)
    # Paired bootstrap by contiguous seven-observed-day blocks WITHIN each year,
    # never across winter gaps. Still exploratory, not a prospective test.
    delta = pred.assign(delta=pred.conditional_cdf_brier - pred.hour_only_cdf_brier).groupby("date").delta.mean()
    years = [g.to_numpy() for _, g in delta.groupby(delta.index.year)]
    rng = np.random.default_rng(20260916)
    draws = []
    for _ in range(2000):
        sampled = []
        for vals in years:
            indices = ((rng.integers(0, len(vals), int(np.ceil(len(vals)/7)))[:, None] + np.arange(7)) % len(vals)).ravel()[:len(vals)]
            sampled.extend(vals[indices])
        draws.append(float(np.mean(sampled)))
    report = {"input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
              "target": "remaining rise in hourly sampled maximum, NOT official settlement",
              "n_days": pred.date.nunique(), "n_snapshots": len(pred),
              "test_dates": [str(pred.date.min().date()), str(pred.date.max().date())],
              "thresholds_f": THRESHOLDS.tolist(), "prior_strength": 30,
              "scores": summarize(pred), "folds": folds,
              "paired_cdf_brier_difference": {"mean": float(delta.mean()),
                                               "ci95": np.quantile(draws, [.025,.975]).tolist(),
                                               "bootstrap": "7-observed-day blocks within year"},
              "limitations": ["Hourly snapshots are not the continuous high or CLI settlement.",
                              "Observation timestamps do not establish real-time receipt times.",
                              "Missing-day coverage filters and missing observations may bias results.",
                              "Previously available research data; no untouched prospective holdout.",
                              "No market price comparison and no alpha claim; research-only model."]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pred.to_csv(args.output_dir / "conditional_rise_predictions.csv", index=False)
    (args.output_dir / "conditional_rise_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
