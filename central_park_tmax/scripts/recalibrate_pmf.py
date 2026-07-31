#!/usr/bin/env python3
"""Recalibrate the integer PMF against realised frequencies — and retest the edge.

REAL_PRICE_BACKTEST.md found the bucket probabilities are overconfident: the model says
6% where the truth is 20%, and 93% where it is 86%. Because "edge" is defined as
``model_p - price``, that miscalibration manufactures edge as an artifact. This script
fits the correction and then asks the only question that matters: **does anything survive
once the probabilities are honest?**

Method:

  * **Isotonic regression** (monotone, non-parametric) mapping raw model probability ->
    realised frequency, fitted per city. Isotonic is the standard choice here because it
    assumes only that "higher model probability means higher true probability" — it does
    not impose a shape, and it can fix the asymmetric over-extremity we measured.
  * **Day-blocked K-fold.** Folds are split by DATE, never by row. A single day supplies
    up to 4 buckets x 6 hours of near-identical observations, so a row-wise split would put
    the same day on both sides and report a fantasy improvement. Every number below is
    out-of-sample in the sense that matters: the calibrator never saw that day.
  * Scored with **Brier** (mean squared probability error) and **log loss**, against two
    baselines: the raw model, and the MARKET PRICE. The market is the real benchmark —
    beating zero is not the bar, beating the price is.

Finally the trading test is re-run with calibrated probabilities, with the same day-
clustered bootstrap, to see whether the apparent +6.8% ROI was miscalibration residue.

Output: backtest_datasets/recalibration.json (+ printed summary).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backtest_datasets"
TRADES = OUT / "real_price_backtest_trades.csv"
N_FOLDS = 5
EPS = 1e-6


def fee_cents(price: float) -> float:
    return math.ceil(0.07 * price * (1 - price) * 100) / 100.0


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def logloss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def day_folds(dates: pd.Series, n: int = N_FOLDS) -> np.ndarray:
    """Assign each row a fold determined by its DATE, so no day straddles folds."""
    uniq = np.array(sorted(dates.unique()))
    rng = np.random.default_rng(7)
    assign = {d: i for d, i in zip(uniq, rng.permutation(len(uniq)) % n)}
    return dates.map(assign).to_numpy()


def main() -> int:
    if not TRADES.exists():
        print(f"missing {TRADES}; run scripts/real_price_backtest.py first")
        return 1
    df = pd.read_csv(TRADES)
    df["won"] = df["won"].astype(int)
    results: dict = {"n": int(len(df)), "per_city": {}, "fitted_curves": {}}

    calibrated = np.full(len(df), np.nan)

    print("=== CALIBRATION QUALITY (day-blocked out-of-sample) ===")
    print(f"{'city':12} {'n':>6} {'Brier raw':>10} {'Brier cal':>10} {'Brier mkt':>10} "
          f"{'LL raw':>8} {'LL cal':>8} {'LL mkt':>8}")
    for series, sub in df.groupby("series"):
        idx = sub.index.to_numpy()
        folds = day_folds(sub["date"], N_FOLDS)
        oof = np.full(len(sub), np.nan)
        for k in range(N_FOLDS):
            tr, te = folds != k, folds == k
            if tr.sum() < 50 or te.sum() == 0:
                continue
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(sub.loc[sub.index[tr], "model_p"], sub.loc[sub.index[tr], "won"])
            oof[te] = iso.predict(sub.loc[sub.index[te], "model_p"])
        ok = ~np.isnan(oof)
        y = sub["won"].to_numpy()[ok]
        raw = sub["model_p"].to_numpy()[ok]
        mkt = sub["price"].to_numpy()[ok]
        cal = oof[ok]
        calibrated[idx[ok]] = cal
        rec = {"n": int(ok.sum()),
               "brier_raw": round(brier(raw, y), 4),
               "brier_calibrated": round(brier(cal, y), 4),
               "brier_market": round(brier(mkt, y), 4),
               "logloss_raw": round(logloss(raw, y), 4),
               "logloss_calibrated": round(logloss(cal, y), 4),
               "logloss_market": round(logloss(mkt, y), 4)}
        results["per_city"][series] = rec
        print(f"{series:12} {rec['n']:6d} {rec['brier_raw']:10.4f} "
              f"{rec['brier_calibrated']:10.4f} {rec['brier_market']:10.4f} "
              f"{rec['logloss_raw']:8.4f} {rec['logloss_calibrated']:8.4f} "
              f"{rec['logloss_market']:8.4f}")

        # Full-sample curve, for shipping into the live model.
        iso_full = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso_full.fit(sub["model_p"], sub["won"])
        grid = np.round(np.arange(0, 1.001, 0.02), 3)
        results["fitted_curves"][series] = {
            "grid": [float(g) for g in grid],
            "calibrated": [round(float(v), 4) for v in iso_full.predict(grid)]}

    df["model_p_cal"] = calibrated
    df = df.dropna(subset=["model_p_cal"]).copy()
    df["edge_cal"] = df["model_p_cal"] - df["price"]
    df["cluster"] = df["series"] + "_" + df["date"]

    print("\n=== CALIBRATION TABLE AFTER CORRECTION ===")
    print(f"{'bin':12} {'n':>6} {'raw p':>8} {'cal p':>8} {'actual':>8} {'market':>8}")
    results["calibration_after"] = []
    for lo in np.arange(0.0, 1.0, 0.2):
        s = df[(df["model_p"] >= lo) & (df["model_p"] < lo + 0.2)]
        if len(s) < 20:
            continue
        row = {"bin": f"{lo:.1f}-{lo+0.2:.1f}", "n": int(len(s)),
               "raw": round(float(s["model_p"].mean()), 3),
               "calibrated": round(float(s["model_p_cal"].mean()), 3),
               "actual": round(float(s["won"].mean()), 3),
               "market": round(float(s["price"].mean()), 3)}
        results["calibration_after"].append(row)
        print(f"{row['bin']:12} {row['n']:6d} {row['raw']:8.3f} {row['calibrated']:8.3f} "
              f"{row['actual']:8.3f} {row['market']:8.3f}")

    def roi_boot(sub: pd.DataFrame, iters: int = 4000) -> dict:
        if sub.empty:
            return {"n": 0}
        cost = sub["price"] + sub["price"].map(fee_cents)
        pnl = sub["won"] - cost
        w = sub.assign(_c=cost, _p=pnl).set_index("cluster")
        clusters = sub["cluster"].unique()
        rng = np.random.default_rng(0)
        boots = [
            (lambda s: s["_p"].sum() / s["_c"].sum() * 100)(
                w.loc[rng.choice(clusters, size=len(clusters), replace=True)])
            for _ in range(iters)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        return {"n": int(len(sub)), "n_city_days": int(len(clusters)),
                "hit_rate": round(float(sub["won"].mean()), 4),
                "roi_pct": round(float(pnl.sum() / cost.sum() * 100), 2),
                "roi_ci95": [round(float(lo), 2), round(float(hi), 2)],
                "p_roi_le_0": round(float((np.array(boots) <= 0).mean()), 3)}

    print("\n=== TRADING TEST WITH CALIBRATED PROBABILITIES (real prices, net of fees) ===")
    results["trading_calibrated"] = {}
    for thr in (0.05, 0.10, 0.15):
        r_raw = roi_boot(df[df["edge"] >= thr])
        r_cal = roi_boot(df[df["edge_cal"] >= thr])
        results["trading_calibrated"][str(thr)] = {"raw": r_raw, "calibrated": r_cal}
        print(f"  edge >= {thr:.0%}")
        for lab, r in (("raw      ", r_raw), ("calibrated", r_cal)):
            if r.get("n"):
                print(f"    {lab}: ROI {r['roi_pct']:+6.2f}%  CI {r['roi_ci95']}  "
                      f"P(<=0)={r['p_roi_le_0']:.2f}  n={r['n']} over {r['n_city_days']} days")
            else:
                print(f"    {lab}: no qualifying trades")

    (OUT / "recalibration.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'recalibration.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
